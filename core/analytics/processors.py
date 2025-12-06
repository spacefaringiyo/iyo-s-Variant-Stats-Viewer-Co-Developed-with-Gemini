import os
import pandas as pd
from pathlib import Path
import json
import bisect
from core.analytics.parsers import parse_kovaaks_stats_file

APP_DATA_DIR = Path.home() / '.VSV_cache_config'
APP_DATA_DIR.mkdir(exist_ok=True) 

CACHE_HISTORY_PATH = APP_DATA_DIR / 'vsv_history_cache.pkl'
CACHE_INFO_PATH = APP_DATA_DIR / 'vsv_cache_info.json'
CACHE_ENRICHED_PATH = APP_DATA_DIR / 'vsv_enriched_cache.pkl'
CACHE_META_PATH = APP_DATA_DIR / 'vsv_meta.json'

# Increment this when logic changes to force a cache rebuild
CACHE_VERSION = 2

def _detect_and_assign_sessions(history_df, session_gap_minutes=30):
    if history_df.empty or 'Timestamp' not in history_df.columns: return history_df
    df = history_df.copy()
    df.sort_values('Timestamp', inplace=True)
    time_diffs = df['Timestamp'].diff()
    session_starts = time_diffs > pd.Timedelta(minutes=session_gap_minutes)
    session_ids = session_starts.cumsum()
    df['SessionID'] = session_ids
    return df

def find_and_process_stats(stats_folder_path, session_gap_minutes=30):
    path_obj = Path(stats_folder_path)
    if not path_obj.is_dir(): return None
    
    processed_files_info = {}
    cached_history_df = pd.DataFrame()
    
    # 1. Load File Info Cache
    if os.path.exists(CACHE_HISTORY_PATH) and os.path.exists(CACHE_INFO_PATH):
        try:
            cached_history_df = pd.read_pickle(CACHE_HISTORY_PATH)
            with open(CACHE_INFO_PATH, 'r') as f: processed_files_info = json.load(f)
        except: pass
            
    # 2. Optimized Scan
    new_files_to_process = []
    current_files_info = {}
    files_changed = False
    
    try:
        with os.scandir(stats_folder_path) as entries:
            for entry in entries:
                if not entry.name.endswith('.csv') or 'Challenge' not in entry.name:
                    continue
                mtime = entry.stat().st_mtime
                fpath = entry.path
                
                current_files_info[str(fpath)] = mtime
                
                if str(fpath) not in processed_files_info or mtime > processed_files_info[str(fpath)]:
                    new_files_to_process.append(fpath)
                    files_changed = True
    except OSError:
        return pd.DataFrame()

    if len(current_files_info) != len(processed_files_info):
        files_changed = True

    # 3. HOT CACHE CHECK (With Version Control)
    if not files_changed and os.path.exists(CACHE_ENRICHED_PATH) and os.path.exists(CACHE_META_PATH):
        try:
            with open(CACHE_META_PATH, 'r') as f: meta = json.load(f)
            # Check Gap AND Version
            if meta.get('session_gap') == session_gap_minutes and meta.get('version') == CACHE_VERSION:
                return pd.read_pickle(CACHE_ENRICHED_PATH)
        except: pass

    # 4. Processing
    if new_files_to_process:
        newly_parsed_data = [d for d in (parse_kovaaks_stats_file(fp) for fp in new_files_to_process) if d]
        if newly_parsed_data:
            new_df = pd.DataFrame(newly_parsed_data)
            combined_history_df = pd.concat([cached_history_df, new_df], ignore_index=True)
            combined_history_df.drop_duplicates(subset=['Scenario', 'Sens', 'Timestamp', 'Score'], inplace=True)
        else: combined_history_df = cached_history_df
    else: combined_history_df = cached_history_df
        
    if combined_history_df.empty: return pd.DataFrame()

    try:
        combined_history_df.to_pickle(CACHE_HISTORY_PATH)
        with open(CACHE_INFO_PATH, 'w') as f: json.dump(current_files_info, f, indent=2)
    except: pass

    # 5. Enrichment
    combined_history_df = _detect_and_assign_sessions(combined_history_df, session_gap_minutes)
    enriched_df = enrich_history_with_stats(combined_history_df)
    enriched_df = enriched_df.reset_index(drop=True)

    # 6. Save with Version
    try:
        enriched_df.to_pickle(CACHE_ENRICHED_PATH)
        with open(CACHE_META_PATH, 'w') as f: 
            json.dump({'session_gap': session_gap_minutes, 'version': CACHE_VERSION}, f)
    except: pass

    return enriched_df

def enrich_history_with_stats(df):
    """Calculates PBs and Assigns Ranks (Vectorized)"""
    if df is None or df.empty: return df
    
    # Sort strictly by time
    df = df.sort_values('Timestamp').reset_index(drop=True)
    
    # --- 1. SESSION CONTEXT LOOKUPS ---
    df['Scen_Start_SessID'] = df.groupby('Scenario')['SessionID'].transform('min')
    df['Combo_Start_SessID'] = df.groupby(['Scenario', 'Sens'])['SessionID'].transform('min')

    # --- 2. VECTORIZED PBs & FIRSTS ---
    g_sens = df.groupby(['Scenario', 'Sens'])
    df['Is_First'] = g_sens.cumcount() == 0
    prev_max_sens = g_sens['Score'].cummax().shift(1).fillna(-999999)
    
    # FIX: A PB must be strictly better than previous AND not the first run
    df['Is_PB'] = (df['Score'] > prev_max_sens) & (~df['Is_First'])

    g_scen = df.groupby('Scenario')
    df['Is_Scen_First'] = g_scen.cumcount() == 0
    prev_max_scen = g_scen['Score'].cummax().shift(1).fillna(-999999)
    
    # FIX: Same for Scenario PBs
    df['Is_Scen_PB'] = (df['Score'] > prev_max_scen) & (~df['Is_Scen_First'])

    # --- 3. VECTORIZED RANKS ---
    percentiles = df.groupby(['Scenario', 'Sens'])['Score'].transform(
        lambda x: x.expanding().rank(pct=True)
    )
    percentiles = percentiles * 100.0
    
    ranks = [("SINGULARITY", 100), ("ARCADIA", 95), ("UBER", 90), ("EXALTED", 82), ("BLESSED", 75), ("TRANSMUTE", 55)]
    gated = {"SINGULARITY", "ARCADIA", "UBER"}
    
    run_counts = df.groupby(['Scenario', 'Sens']).cumcount() + 1
    
    for r_name, r_val in ranks:
        col = f'Rank_{r_name}'
        condition = percentiles >= r_val
        if r_name in gated:
            condition = condition & (run_counts >= 10)
        df[col] = condition.astype(int)

    # Cast Types
    df['Is_PB'] = df['Is_PB'].astype(bool)
    df['Is_Scen_PB'] = df['Is_Scen_PB'].astype(bool)
    df['Is_First'] = df['Is_First'].astype(bool)
    df['Is_Scen_First'] = df['Is_Scen_First'].astype(bool)
    
    for r, _ in ranks:
        col = f'Rank_{r}'
        df[col] = df[col].astype(int)

    return df