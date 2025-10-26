import os
import pandas as pd
from pathlib import Path
import re
import json
from datetime import datetime, time, timedelta

CACHE_DF_PATH = 'kovaaks_cache.parquet'
CACHE_HISTORY_PATH = 'kovaaks_history_cache.parquet'
CACHE_INFO_PATH = 'kovaaks_cache_info.json'

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
        
        # Calculate precise duration if possible
        if start_time_str:
            try:
                # KovaaK's time can have more than 6 microsecond digits, which python strptime fails on
                if '.' in start_time_str and len(start_time_str.split('.')[1]) > 6:
                    start_time_str = start_time_str[:start_time_str.find('.')+7]
                
                parsed_time = datetime.strptime(start_time_str, '%H:%M:%S.%f').time()
                start_time = end_time.replace(hour=parsed_time.hour, minute=parsed_time.minute, 
                                              second=parsed_time.second, microsecond=parsed_time.microsecond)
                
                # Handle midnight crossing, e.g., starts at 23:59, ends at 00:01
                if start_time > end_time:
                    start_time -= timedelta(days=1)
                
                duration_seconds = (end_time - start_time).total_seconds()
                # Sanity check: cap duration at 10 minutes to avoid absurd values from clock changes
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
    if not path_obj.is_dir(): return None, None
    processed_files_info = {}
    cached_history_df = pd.DataFrame()
    if os.path.exists(CACHE_HISTORY_PATH) and os.path.exists(CACHE_INFO_PATH):
        try:
            print("---- Loading data from cache ----")
            cached_history_df = pd.read_parquet(CACHE_HISTORY_PATH)
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
    data_changed = False
    if new_files_to_process:
        data_changed = True
        newly_parsed_data = [d for d in (parse_kovaaks_stats_file(fp) for fp in new_files_to_process) if d]
        if newly_parsed_data:
            new_df = pd.DataFrame(newly_parsed_data)
            combined_history_df = pd.concat([cached_history_df, new_df], ignore_index=True)
            combined_history_df.drop_duplicates(subset=['Scenario', 'Sens', 'Timestamp', 'Score'], inplace=True)
        else: combined_history_df = cached_history_df
    else: combined_history_df = cached_history_df
    if combined_history_df.empty: return pd.DataFrame(), pd.DataFrame()
    
    combined_history_df = _detect_and_assign_sessions(combined_history_df, session_gap_minutes)

    df_max_scores = combined_history_df.loc[combined_history_df.groupby(['Scenario', 'Sens'])['Score'].idxmax()]
    try:
        df_max_scores.to_parquet(CACHE_DF_PATH)
        combined_history_df.to_parquet(CACHE_HISTORY_PATH)
        with open(CACHE_INFO_PATH, 'w') as f: json.dump(current_files_info, f, indent=2)
        print("---- Caches updated successfully ----")
    except Exception as e: print(f"Error saving cache: {e}")
    return df_max_scores.reset_index(drop=True), combined_history_df.reset_index(drop=True)

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

def get_scenario_family_info(master_df, base_scenario):
    if master_df is None or master_df.empty: return None
    family_df = master_df[master_df['Scenario'].str.startswith(base_scenario)].copy()
    if family_df.empty: return None
    def parse_modifiers(scenario_name):
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
        if not all(consumed): return {}
        return modifiers
    family_df['Modifiers'] = family_df['Scenario'].apply(parse_modifiers)
    return family_df

def analyze_variants(family_df, base_scenario, variable_axis, fixed_filters={}, pattern_filter=None):
    if family_df is None or family_df.empty: return pd.DataFrame()
    if variable_axis is None:
        grid_df = family_df.pivot_table(index='Scenario', columns='Sens', values='Score')
        grid_df['BEST Score'], grid_df['BEST CM'], grid_df['% vs Base'] = grid_df.max(axis=1), grid_df.idxmax(axis=1), '100.0%'
        return grid_df.sort_index()
    filtered_rows = []
    for _, row in family_df.iterrows():
        modifiers, is_base_scenario = row['Modifiers'], row['Scenario'] == base_scenario
        if not is_base_scenario and variable_axis not in modifiers: continue
        if not is_base_scenario and not modifiers: continue
        if pattern_filter and variable_axis in pattern_filter and not is_base_scenario:
            if modifiers[variable_axis][1] not in pattern_filter[variable_axis]: continue
        temp_modifiers_for_check = {k: v[0] for k, v in modifiers.items()}
        allowed_keys = set(fixed_filters.keys()) | {variable_axis}
        if not set(temp_modifiers_for_check.keys()).issubset(allowed_keys): continue
        match = all(temp_modifiers_for_check.get(key) == value for key, value in fixed_filters.items())
        if match: filtered_rows.append(row)
    if not filtered_rows: return pd.DataFrame()
    display_df = pd.DataFrame(filtered_rows)
    grid_df = display_df.pivot_table(index='Scenario', columns='Sens', values='Score')
    base_scores = display_df[display_df['Scenario'] == base_scenario]['Score']
    base_best_score = base_scores.max() if not base_scores.empty else 1.0
    if base_best_score == 0: base_best_score = 1.0
    grid_df['BEST Score'], grid_df['BEST CM'] = grid_df.max(axis=1), grid_df.idxmax(axis=1)
    grid_df['% vs Base'] = (grid_df['BEST Score'] / base_best_score * 100).round(1).astype(str) + '%'
    return grid_df.sort_index()