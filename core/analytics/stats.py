import pandas as pd
import numpy as np
from datetime import timedelta
from collections import defaultdict

def format_timedelta(td):
    if isinstance(td, (int, float)): td = timedelta(seconds=td)
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours:02}:{minutes:02}:{seconds:02}'

def format_timedelta_hours(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h {minutes}m"

def calculate_detailed_stats(runs_df):
    if runs_df is None or runs_df.empty: return {}
    df = runs_df.sort_values('Timestamp').copy()
    scores = df['Score']
    pb_idx = scores.idxmax()
    
    stats = {
        'count': len(df), 'max': scores.max(), 'avg': scores.mean(),
        'std': scores.std() if len(df) > 1 else 0.0,
        'p50': scores.median(), 'p75': scores.quantile(0.75), 'min': scores.min(),
        'pb_date': df.loc[pb_idx]['Timestamp'],
        'pb_sens': df.loc[pb_idx]['Sens']
    }
    recent = df.tail(min(len(df), 20))
    if not recent.empty: stats['recent_avg'] = recent['Score'].mean()
    pre_pb = df.loc[:pb_idx].iloc[:-1].tail(20)
    stats['launchpad_avg'] = pre_pb['Score'].mean() if not pre_pb.empty else 0.0
    return stats

def calculate_profile_stats(df):
    if df is None or df.empty: return {}
    stats = {
        'total_runs': len(df),
        'active_time': df['Duration'].sum(),
        'unique_scens': df['Scenario'].nunique(),
        'unique_combos': df.groupby(['Scenario', 'Sens']).ngroups,
        'total_pbs': df['Is_PB'].sum()
    }
    ranks = {}
    for col in df.columns:
        if col.startswith('Rank_'):
            ranks[col.replace('Rank_', '')] = df[col].sum()
    stats['ranks'] = ranks
    stats['top_scens'] = df['Scenario'].value_counts().head(10).to_dict()
    return stats

# --- CORE SESSION LOGIC ---

def _get_pb_indices(scores_series, baseline, stack_pbs, count_new):
    """
    Determines which indices in a series of scores are PBs based on rules.
    Returns: Set of integer indices (relative to the series) that are PBs.
    """
    pb_indices = set()
    scores = scores_series.values
    indices = scores_series.index
    
    current_max = baseline
    
    if current_max is None:
        if not count_new: return set()
        if len(scores) > 0:
            current_max = scores[0] 
            start_idx = 1
        else: return set()
    else:
        start_idx = 0

    if not stack_pbs:
        if len(scores) > start_idx:
            valid_scores = scores[start_idx:]
            valid_indices = indices[start_idx:]
            session_best_idx_local = np.argmax(valid_scores)
            session_best_score = valid_scores[session_best_idx_local]
            
            if session_best_score > current_max:
                original_idx = valid_indices[session_best_idx_local]
                pb_indices.add(original_idx)
                
    else:
        for i in range(start_idx, len(scores)):
            score = scores[i]
            if score > current_max:
                pb_indices.add(indices[i])
                current_max = score

    return pb_indices

def analyze_session(session_df, history_df, flow_window=5, stack_pbs=False, count_new=False, summary_only=False):
    """
    Analyzes a session with strict separation of Scenario vs Sensitivity Tracks.
    If summary_only=True, skips graph generation and returns just the PB counts.
    """
    if session_df.empty: return None
    
    # 1. Prepare Snapshots
    session_start = session_df['Timestamp'].min()
    session_df = session_df.sort_values('Timestamp')
    prior_history = history_df[history_df['Timestamp'] < session_start]

    # 2. Establish Baselines
    base_grid_max = {}
    base_scen_max = {}
    
    if not prior_history.empty:
        base_grid_max = prior_history.groupby(['Scenario', 'Sens'])['Score'].max().to_dict()
        base_scen_max = prior_history.groupby('Scenario')['Score'].max().to_dict()
        
    # 3. Calculate PBs
    scen_pb_indices = set()
    for scen, group in session_df.groupby('Scenario'):
        baseline = base_scen_max.get(scen)
        pube_idxs = _get_pb_indices(group['Score'], baseline, stack_pbs, count_new)
        scen_pb_indices.update(pube_idxs)
        
    sens_pb_indices = set()
    for (scen, sens), group in session_df.groupby(['Scenario', 'Sens']):
        baseline = base_grid_max.get((scen, sens))
        pube_idxs = _get_pb_indices(group['Score'], baseline, stack_pbs, count_new)
        sens_pb_indices.update(pube_idxs)

    # --- FAST PATH FOR LIST WIDGET ---
    if summary_only:
        # Calculate counts based on the indices we just found.
        # Note: If stack_pbs=False, _get_pb_indices already only returns the MAX for that group.
        # But we must ensure that for "Unstacked" we count UNIQUE Scenarios/Combos, not total PB rows.
        # However, _get_pb_indices logic for Unstacked ensures only 1 PB per group (the max).
        # So we can just take the length of the indices set?
        # Yes: if Unstacked, _get_pb_indices returns at most 1 index per group.
        # So len(indices) == number of groups that PB'd.
        
        return {
            "scen_pb_count": len(scen_pb_indices),
            "sens_pb_count": len(sens_pb_indices)
        }
    # ---------------------------------
        
    # Averages for Context (Only needed for full report)
    base_grid_avg = prior_history.groupby(['Scenario', 'Sens'])['Score'].mean().to_dict()
    base_scen_avg = prior_history.groupby('Scenario')['Score'].mean().to_dict()
    
    # 4. Build Output Data
    graph_data_grid = []
    graph_data_scen = []
    pbs_list_grid = []
    pbs_list_scen = []
    
    pct_history = []
    prev_pulse = 0.0
    
    accs_grid = defaultdict(lambda: {'sum':0.0, 'count':0, 'min_ts': None})
    accs_scen = defaultdict(lambda: {'sum':0.0, 'count':0, 'min_ts': None})

    for i, row in enumerate(session_df.itertuples()):
        idx = row.Index
        
        is_scen_pb = idx in scen_pb_indices
        is_sens_pb = idx in sens_pb_indices
        
        key_grid = (row.Scenario, row.Sens)
        key_scen = row.Scenario
        
        # Grid Avg
        base_avg_g = base_grid_avg.get(key_grid, 0)
        accs_grid[key_grid]['sum'] += row.Score
        accs_grid[key_grid]['count'] += 1
        if accs_grid[key_grid]['min_ts'] is None: accs_grid[key_grid]['min_ts'] = row.Timestamp
        curr_avg_g = accs_grid[key_grid]['sum'] / accs_grid[key_grid]['count']
        
        # Scen Avg
        accs_scen[key_scen]['sum'] += row.Score
        accs_scen[key_scen]['count'] += 1
        if accs_scen[key_scen]['min_ts'] is None: accs_scen[key_scen]['min_ts'] = row.Timestamp
        
        eff_base = base_avg_g if base_avg_g > 0 else curr_avg_g
        score_pct = ((row.Score - eff_base)/eff_base)*100 if eff_base > 0 else 0
        trend_pct = ((curr_avg_g - eff_base)/eff_base)*100 if eff_base > 0 else 0
        
        pct_history.append(score_pct)
        flow_pct = sum(pct_history[-flow_window:])/len(pct_history[-flow_window:])
        pulse_pct = score_pct if i==0 else (score_pct*0.5)+(prev_pulse*0.5)
        prev_pulse = pulse_pct
        
        g_obj = {
            'time': int(row.Timestamp.timestamp()), 'pct': score_pct,
            'trend_pct': trend_pct, 'flow_pct': flow_pct, 'pulse_pct': pulse_pct,
            'scenario': row.Scenario, 'sens': row.Sens, 'score': row.Score
        }
        graph_data_grid.append(g_obj)
        graph_data_scen.append(g_obj)
        
        def make_pb_obj(baseline_max):
            prev = baseline_max if baseline_max else 0
            return {
                'name': row.Scenario, 'sens': row.Sens, 'score': row.Score, 
                'prev': prev, 'imp': row.Score - prev, 
                'imp_pct': ((row.Score - prev)/prev)*100 if prev > 0 else 0,
                'time': row.Timestamp
            }

        if is_sens_pb:
            base = base_grid_max.get(key_grid, 0)
            pbs_list_grid.append(make_pb_obj(base))
            
        if is_scen_pb:
            base = base_scen_max.get(key_scen, 0)
            pbs_list_scen.append(make_pb_obj(base))

    def build_agg_lists(accs, base_avgs, max_dict):
        played_list = []
        avgs_list = []
        
        for key, data in accs.items():
            scen = key[0] if isinstance(key, tuple) else key
            sens = key[1] if isinstance(key, tuple) else None
            
            if isinstance(key, tuple): grp = session_df[(session_df['Scenario']==scen) & (session_df['Sens']==sens)]
            else: grp = session_df[session_df['Scenario']==scen]
                
            best_score = grp['Score'].max()
            sess_avg = data['sum'] / data['count']
            
            hist_max = max_dict.get(key, 0)
            is_pb_badge = False
            if hist_max == 0: is_pb_badge = True
            elif best_score > hist_max: is_pb_badge = True
            
            played_list.append({
                'name': scen, 'sens': sens, 'count': data['count'], 
                'best': best_score, 'avg': sess_avg, 'is_pb': is_pb_badge,
                'time': data['min_ts']
            })
            
            hist_avg = base_avgs.get(key, 0)
            if hist_avg > 0:
                diff_pct = ((sess_avg - hist_avg) / hist_avg) * 100
                avgs_list.append({
                    'name': scen, 'sens': sens,
                    'sess_avg': sess_avg, 'sess_cnt': data['count'],
                    'all_avg': hist_avg, 'all_cnt': 0, 
                    'diff_pct': diff_pct,
                    'time': data['min_ts']
                })
        return played_list, avgs_list

    played_g, avgs_g = build_agg_lists(accs_grid, base_grid_avg, base_grid_max)
    played_s, avgs_s = build_agg_lists(accs_scen, base_scen_avg, base_scen_max)

    return {
        "meta": {
            "date_str": session_start.strftime('%B %d, %Y'),
            "duration_str": format_timedelta(session_df['Timestamp'].max() - session_start),
            "active_str": format_timedelta(session_df['Duration'].sum()),
            "play_count": len(session_df)
        },
        "grid": {
            "graph_data": graph_data_grid, 
            "lists": {"pbs": pbs_list_grid, "played": played_g, "avgs": avgs_g}, 
            "pb_count": len(pbs_list_grid)
        },
        "scenario": {
            "graph_data": graph_data_scen, 
            "lists": {"pbs": pbs_list_scen, "played": played_s, "avgs": avgs_s}, 
            "pb_count": len(pbs_list_scen)
        }
    }