import os
import pandas as pd
from pathlib import Path
import re
import json
from datetime import datetime, timedelta
import bisect
import numpy as np
from collections import defaultdict

APP_DATA_DIR = Path.home() / '.kovaaks_stats_viewer'
APP_DATA_DIR.mkdir(exist_ok=True) 

CACHE_HISTORY_PATH = APP_DATA_DIR / 'kovaaks_history_cache.pkl'
CACHE_INFO_PATH = APP_DATA_DIR / 'kovaaks_cache_info.json'

def parse_kovaaks_stats_file(file_path):
    try:
        filename = os.path.basename(file_path)
        timestamp_match = re.search(r'(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2})', filename)
        if timestamp_match:
            timestamp_str = timestamp_match.group(1)
            end_time = datetime.strptime(timestamp_str, '%Y.%m.%d-%H.%M.%S')
        else:
            end_time = datetime.fromtimestamp(os.path.getmtime(file_path))
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        data = {'Duration': 60.0} # Default duration
        start_time_str = None
        
        for line in lines:
            if line.startswith('Scenario:'): data['Scenario'] = line.split(',', 1)[1].strip()
            elif line.startswith('Score:'): data['Score'] = float(line.split(',')[1].strip())
            elif line.startswith('Horiz Sens:'): data['Sens'] = float(line.split(',')[1].strip())
            elif line.startswith('Challenge Start:'): start_time_str = line.split(',')[1].strip()
        
        if start_time_str:
            try:
                if '.' in start_time_str and len(start_time_str.split('.')[1]) > 6:
                    start_time_str = start_time_str[:start_time_str.find('.')+7]
                
                parsed_time = datetime.strptime(start_time_str, '%H:%M:%S.%f').time()
                start_time = end_time.replace(hour=parsed_time.hour, minute=parsed_time.minute, 
                                              second=parsed_time.second, microsecond=parsed_time.microsecond)
                
                if start_time > end_time:
                    start_time -= timedelta(days=1)
                
                duration_seconds = (end_time - start_time).total_seconds()
                if 0 < duration_seconds < 600:
                    data['Duration'] = duration_seconds
            except ValueError:
                print(f"Could not parse start time '{start_time_str}' in {filename}. Defaulting duration.")

        if 'Scenario' in data and 'Score' in data and 'Sens' in data:
            data['Timestamp'] = end_time
            return data
        else: return None
    except Exception as e:
        print(f"Error processing file {os.path.basename(file_path)}: {e}")
        return None

def _detect_and_assign_sessions(history_df, session_gap_minutes=30):
    if history_df.empty or 'Timestamp' not in history_df.columns: return history_df
    print(f"--- Detecting sessions with a {session_gap_minutes} minute gap ---")
    df = history_df.copy()
    df.sort_values('Timestamp', inplace=True)
    time_diffs = df['Timestamp'].diff()
    session_starts = time_diffs > pd.Timedelta(minutes=session_gap_minutes)
    session_ids = session_starts.cumsum()
    df['SessionID'] = session_ids
    print(f"--- Found {df['SessionID'].nunique()} sessions ---")
    return df

def find_and_process_stats(stats_folder_path, session_gap_minutes=30):
    path_obj = Path(stats_folder_path)
    if not path_obj.is_dir(): return None
    processed_files_info = {}
    cached_history_df = pd.DataFrame()
    if os.path.exists(CACHE_HISTORY_PATH) and os.path.exists(CACHE_INFO_PATH):
        try:
            print("---- Loading data from cache ----")
            cached_history_df = pd.read_pickle(CACHE_HISTORY_PATH)
            if 'Timestamp' in cached_history_df.columns:
                 cached_history_df['Timestamp'] = pd.to_datetime(cached_history_df['Timestamp'])
            with open(CACHE_INFO_PATH, 'r') as f: processed_files_info = json.load(f)
        except Exception as e:
            print(f"Could not load cache, performing full scan. Error: {e}")
            processed_files_info, cached_history_df = {}, pd.DataFrame()
            
    all_challenge_files = list(path_obj.glob('*- Challenge -*.csv'))
    new_files_to_process = []
    current_files_info = {}
    for file_path in all_challenge_files:
        try:
            mtime = os.path.getmtime(file_path)
            current_files_info[str(file_path)] = mtime
            if str(file_path) not in processed_files_info or mtime > processed_files_info[str(file_path)]:
                new_files_to_process.append(file_path)
        except FileNotFoundError: continue
        
    print(f"---- STARTING SCAN ---- Found {len(all_challenge_files)} total files.")
    print(f"Found {len(new_files_to_process)} new files to process.")

    if new_files_to_process:
        newly_parsed_data = [d for d in (parse_kovaaks_stats_file(fp) for fp in new_files_to_process) if d]
        if newly_parsed_data:
            new_df = pd.DataFrame(newly_parsed_data)
            combined_history_df = pd.concat([cached_history_df, new_df], ignore_index=True)
            combined_history_df.drop_duplicates(subset=['Scenario', 'Sens', 'Timestamp', 'Score'], inplace=True)
        else: combined_history_df = cached_history_df
    else: combined_history_df = cached_history_df
        
    if combined_history_df.empty: return pd.DataFrame()
    
    combined_history_df = _detect_and_assign_sessions(combined_history_df, session_gap_minutes)

    try:
        combined_history_df.to_pickle(CACHE_HISTORY_PATH)
        with open(CACHE_INFO_PATH, 'w') as f: json.dump(current_files_info, f, indent=2)
        print("---- Caches updated successfully ----")
    except Exception as e: print(f"Error saving cache: {e}")
        
    return combined_history_df.reset_index(drop=True)

def aggregate_data(df, period):
    if df.empty:
        return pd.DataFrame()
    if period == 'Session':
        if 'SessionID' not in df.columns:
            return pd.DataFrame()
        agg = df.groupby('SessionID').agg(Score=('Score', 'mean'), Timestamp=('Timestamp', 'first'))
        return agg.reset_index().sort_values('Timestamp')
    else:
        df_resample = df.set_index('Timestamp')
        agg = df_resample['Score'].resample(period).mean().dropna()
        return agg.reset_index()

def get_scenario_family_info(all_runs_df, base_scenario):
    if all_runs_df is None or all_runs_df.empty: return None
    family_df = all_runs_df[all_runs_df['Scenario'].str.startswith(base_scenario)].copy()
    if family_df.empty: return None
    
    memo = {}

    def parse_modifiers(scenario_name):
        if scenario_name in memo:
            return memo[scenario_name]

        modifier_str = scenario_name.replace(base_scenario, '', 1).strip()
        if not modifier_str: return {}
        
        UNIT_MAP = {'s': 'Duration', 'sec': 'Duration', 'm': 'Distance', 'hp': 'Health'}
        token_pattern = re.compile(r'(\d[\d.]*%?[a-zA-Z]*|[A-Za-z]+)')
        tokens = token_pattern.findall(modifier_str)
        
        def is_value(token):
            if re.fullmatch(r'[\d.]+%?', token): return True
            unit_match = re.fullmatch(r'([\d.]+%?)(\w+)', token)
            if unit_match and unit_match.groups()[1] in UNIT_MAP: return True
            return False
            
        modifiers = {}
        consumed = [False] * len(tokens); i = 0
        while i < len(tokens) - 1:
            if not consumed[i] and not consumed[i+1]:
                t1, t2 = tokens[i], tokens[i+1]
                if not is_value(t1) and is_value(t2): modifiers[t1] = (t2, 'word_value'); consumed[i] = consumed[i+1] = True; i += 2; continue
                elif is_value(t1) and not is_value(t2): modifiers[t2] = (t1, 'value_word'); consumed[i] = consumed[i+1] = True; i += 2; continue
            i += 1
        for i, token in enumerate(tokens):
            if not consumed[i]:
                unit_match = re.fullmatch(r'([\d.]+%?)(\w+)', token)
                if unit_match:
                    value, unit = unit_match.groups()
                    if unit in UNIT_MAP: modifiers[UNIT_MAP[unit]] = (token, 'standalone'); consumed[i] = True
                elif '%' in token and is_value(token):
                    modifiers['Percent'] = (token, 'standalone')
                    consumed[i] = True
        if not all(consumed):
             memo[scenario_name] = {}
             return {}
        memo[scenario_name] = modifiers
        return modifiers
        
    family_df['Modifiers'] = family_df['Scenario'].apply(parse_modifiers)
    return family_df

# --- NEW: Helper for enriched analysis ---
# --- NEW: Helper for enriched analysis ---
# --- NEW: Helper for enriched analysis ---
def enrich_history_with_stats(df):
    """
    Calculates PBs and Ranks for every run in the dataframe contextually.
    Updates:
    - Is_PB / Is_PB_Scenario: Only True if improving on PREVIOUS history (First run != PB).
    - Ranks: First run counts as Singularity (Baseline is Peak).
    """
    if df is None or df.empty: return df
    
    # Work on a sorted copy
    df = df.sort_values('Timestamp').copy()
    
    rank_definitions = [
        ("SINGULARITY", 100),
        ("ARCADIA", 95),
        ("UBER", 90),
        ("EXALTED", 82),
        ("BLESSED", 75),
        ("TRANSMUTE", 55)
    ]
    gated_ranks = {"SINGULARITY", "ARCADIA", "UBER"}
    min_runs_for_gate = 10
    
    # Initialize columns
    df['Is_PB'] = False # Combo PB
    df['Is_PB_Scenario'] = False # Global Scenario PB
    
    for r_name, _ in rank_definitions:
        df[f'Rank_{r_name}'] = 0 

    # --- PASS 1: Scenario Global PBs ---
    scen_groups = df.groupby('Scenario')
    updates_scen = []
    
    for _, group in scen_groups:
        scores = group['Score'].values
        indices = group.index.values
        
        current_max = -float('inf')
        
        for i, score in enumerate(scores):
            # STRICTER LOGIC: First run (i==0) is NOT a PB stat.
            # Only count as PB if it improves on previous max.
            is_improvement = (i > 0 and score >= current_max)
            
            if is_improvement:
                updates_scen.append(indices[i])
            
            # Update max AFTER checking
            if score > current_max: current_max = score
            # Note: For first run, current_max becomes score.
    
    if updates_scen:
        df.loc[updates_scen, 'Is_PB_Scenario'] = True

    # --- PASS 2: Combo PBs + Ranks ---
    combo_groups = df.groupby(['Scenario', 'Sens'])
    updates = []
    
    for _, group in combo_groups:
        scores = group['Score'].values
        indices = group.index.values
        
        history = []
        
        for i, score in enumerate(scores):
            idx = indices[i]
            current_run_count = i + 1
            
            row_updates = {}
            
            # Determine Status
            if not history:
                # First Run
                is_pb_stat = False # Baseline is not an improvement
                is_singularity_rank = True # But it is the peak of current history (100th percentile)
            else:
                current_pb = history[-1]
                is_pb_stat = score >= current_pb
                is_singularity_rank = score >= current_pb
            
            if is_pb_stat:
                row_updates['Is_PB'] = True 
                
            # Rank Logic
            if is_singularity_rank:
                for rank_name, _ in rank_definitions:
                    if current_run_count < min_runs_for_gate and rank_name in gated_ranks: continue
                    row_updates[f'Rank_{rank_name}'] = 1
            else:
                pos = bisect.bisect_left(history, score)
                percentile = (pos / len(history)) * 100
                
                for rank_name, threshold in rank_definitions:
                    if rank_name == "SINGULARITY": continue
                    if current_run_count < min_runs_for_gate and rank_name in gated_ranks: continue
                    
                    if percentile >= threshold:
                        row_updates[f'Rank_{rank_name}'] = 1

            # Update history
            bisect.insort(history, score)
            updates.append((idx, row_updates))
            
    # Apply updates
    rows = []
    for idx, ups in updates:
        ups['index'] = idx
        rows.append(ups)
    
    if rows:
        updates_df = pd.DataFrame(rows).set_index('index')
        df.update(updates_df)
    
    return df

def calculate_profile_stats(enriched_df):
    """
    Summarizes stats from an ALREADY ENRICHED dataframe slice.
    """
    if enriched_df is None or enriched_df.empty: return None

    stats = {}
    stats['total_runs'] = len(enriched_df)
    stats['active_playtime'] = enriched_df['Duration'].sum()
    
    # Total Session Duration (approximate for the slice)
    if 'SessionID' in enriched_df.columns:
        sess = enriched_df.groupby('SessionID')['Timestamp'].agg(['min', 'max'])
        stats['total_session_time'] = (sess['max'] - sess['min']).sum().total_seconds()
    else:
        stats['total_session_time'] = stats['active_playtime']

    # Unique Scenarios
    stats['unique_scenarios'] = enriched_df['Scenario'].nunique()
    stats['unique_combos'] = enriched_df.groupby(['Scenario', 'Sens']).ngroups
    
    # Top 10 Scenarios
    top_scenarios = enriched_df['Scenario'].value_counts().head(10)
    stats['top_scenarios'] = top_scenarios.to_dict() 
    
    # Totals from enriched columns
    stats['total_pbs_combo'] = int(enriched_df['Is_PB'].sum())
    stats['total_pbs_scen'] = int(enriched_df['Is_PB_Scenario'].sum())
    
    rank_definitions = [
        ("SINGULARITY", 100),
        ("ARCADIA", 95),
        ("UBER", 90),
        ("EXALTED", 82),
        ("BLESSED", 75),
        ("TRANSMUTE", 55)
    ]
    
    rank_counts = {}
    for r_name, _ in rank_definitions:
        col = f'Rank_{r_name}'
        if col in enriched_df.columns:
            rank_counts[r_name] = int(enriched_df[col].sum())
        else:
            rank_counts[r_name] = 0
            
    stats['rank_counts'] = rank_counts
    stats['rank_defs'] = rank_definitions
    
    # Extra Info: Most Active Day
    day_counts = enriched_df['Timestamp'].dt.day_name().value_counts()
    stats['most_active_day'] = day_counts.idxmax() if not day_counts.empty else "N/A"
    
    return stats

def calculate_detailed_stats(runs_df):
    config = {
        'min_runs_for_foundational': 2,
        'min_runs_for_oracle_message': 10,
        'min_pbs_for_launchpad_analysis': 1,
        'recent_runs_window_min': 2,
        'recent_runs_window_max': 20,
        'launchpad_window_min': 2,
        'launchpad_window_max': 20,
    }

    if runs_df is None or runs_df.empty:
        return {}

    pb_row = runs_df.loc[runs_df['Score'].idxmax()]
    stats = {
        'count': len(runs_df),
        'max': pb_row['Score'],
        'pb_date': pb_row['Timestamp']
    }
    if len(runs_df) < config['min_runs_for_foundational']:
        return stats

    q1 = runs_df['Score'].quantile(0.25)
    q3 = runs_df['Score'].quantile(0.75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    cleaned_df = runs_df[runs_df['Score'] >= lower_bound].copy()
    if cleaned_df.empty: cleaned_df = runs_df.copy()

    p50 = cleaned_df['Score'].quantile(0.50)
    p75 = cleaned_df['Score'].quantile(0.75)
    stats.update({
        'avg': cleaned_df['Score'].mean(),
        'std': cleaned_df['Score'].std(),
        'min': cleaned_df['Score'].min(),
    })
    if pd.notna(p50): stats['p50'] = p50
    if pd.notna(p75): stats['p75'] = p75
        
    df_sorted = cleaned_df.sort_values('Timestamp').reset_index(drop=True)
    
    if len(df_sorted) >= config['recent_runs_window_min']:
        num_recent_runs_to_use = min(len(df_sorted), config['recent_runs_window_max'])
        recent_runs = df_sorted.tail(num_recent_runs_to_use)
        stats['recent_avg'] = recent_runs['Score'].mean()
        stats['recent_std'] = recent_runs['Score'].std() if len(recent_runs) > 1 else 0

    df_sorted['cummax'] = df_sorted['Score'].cummax()
    df_sorted['is_pb'] = df_sorted['Score'] > df_sorted['cummax'].shift(1).fillna(0)
    pb_indices = df_sorted[df_sorted['is_pb']].index.tolist()

    if len(pb_indices) >= config['min_pbs_for_launchpad_analysis']:
        last_pb_index = pb_indices[-1]
        if last_pb_index >= config['launchpad_window_min']:
            num_launchpad_runs_to_use = min(last_pb_index, config['launchpad_window_max'])
            start = max(0, last_pb_index - num_launchpad_runs_to_use)
            pre_pb_window = df_sorted.iloc[start:last_pb_index]
            if not pre_pb_window.empty:
                stats['launchpad_avg'] = pre_pb_window['Score'].mean()
                stats['launchpad_std'] = pre_pb_window['Score'].std() if len(pre_pb_window) > 1 else 0

    ## if len(runs_df) >= config['min_runs_for_oracle_message'] and 'recent_avg' in stats:
    #    recent_avg = stats['recent_avg']
        
    #    trend_signal = None
    #    if 'p75' in stats and recent_avg > stats['p75']:
    #        trend_signal = "Improving"
    #   elif 'p50' in stats and recent_avg > stats['p50']:
    #        trend_signal = "Plateau"
    #    elif 'p50' in stats:
    #       trend_signal = "Slump"
    #
    #    peak_signal = None
    #    if 'launchpad_avg' in stats and recent_avg >= (stats['launchpad_avg'] * 0.98):
    #        peak_signal = "Matching"

    #    verdict = None
    #    if trend_signal == "Improving" and peak_signal == "Matching":
    #        verdict = "Peaking!"
    #   elif trend_signal == "Plateau" and peak_signal == "Matching":
     #       verdict = "On a stable peak."
    #    elif trend_signal == "Slump" and peak_signal == "Matching":
      #      verdict = "New higher floor."
    #    elif peak_signal == "Matching":
      #       verdict = "Matching peak conditions."
    #    elif trend_signal == "Improving":
      #      verdict = "Improving."
    #    elif trend_signal == "Plateau":
      #      verdict = "On a plateau."
    #    elif trend_signal == "Slump":
       #     verdict = "In a slump."

     #   if verdict:
      #      stats['oracle'] = verdict
    
    return stats