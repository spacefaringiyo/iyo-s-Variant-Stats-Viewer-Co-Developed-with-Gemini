# --- START OF FINAL, CORRECTED engine.py ---

import os
import pandas as pd
from pathlib import Path
import re
import json

# Define cache file paths
CACHE_DF_PATH = 'kovaaks_cache.parquet'
CACHE_INFO_PATH = 'kovaaks_cache_info.json'

# This function remains unchanged
def parse_kovaaks_stats_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        data = {}
        for line in lines:
            if line.startswith('Scenario:'):
                data['Scenario'] = line.split(',', 1)[1].strip()
            elif line.startswith('Score:'):
                score_str = line.split(',')[1].strip()
                data['Score'] = float(score_str)
            elif line.startswith('Horiz Sens:'):
                sens_str = line.split(',')[1].strip()
                data['Sens'] = float(sens_str)
        if 'Scenario' in data and 'Score' in data and 'Sens' in data:
            return data
        else:
            return None
    except Exception as e:
        print(f"Error processing file {os.path.basename(file_path)}: {e}")
        return None

# THIS IS THE CORRECTED FUNCTION
def find_and_process_stats(stats_folder_path):
    path_obj = Path(stats_folder_path)
    if not path_obj.is_dir():
        return None
    processed_files_info = {}
    cached_df = pd.DataFrame()
    if os.path.exists(CACHE_DF_PATH) and os.path.exists(CACHE_INFO_PATH):
        try:
            print("---- Loading data from cache ----")
            cached_df = pd.read_parquet(CACHE_DF_PATH)
            with open(CACHE_INFO_PATH, 'r') as f:
                processed_files_info = json.load(f)
        except Exception as e:
            print(f"Could not load cache, performing full scan. Error: {e}")
            processed_files_info = {}
            cached_df = pd.DataFrame()
    all_challenge_files = list(path_obj.glob('*- Challenge -*.csv'))
    new_files_to_process = []
    current_files_info = {}
    for file_path in all_challenge_files:
        try:
            mtime = os.path.getmtime(file_path)
            current_files_info[str(file_path)] = mtime
            if str(file_path) not in processed_files_info or mtime > processed_files_info[str(file_path)]:
                new_files_to_process.append(file_path)
        except FileNotFoundError:
            continue
    print(f"---- STARTING SCAN ---- Found {len(all_challenge_files)} total files.")
    print(f"Found {len(new_files_to_process)} new files to process.")
    newly_parsed_data = []
    if new_files_to_process:
        for file_path in new_files_to_process:
            parsed_data = parse_kovaaks_stats_file(file_path)
            if parsed_data:
                newly_parsed_data.append(parsed_data)
    if not newly_parsed_data and cached_df.empty:
        return pd.DataFrame()
    new_df = pd.DataFrame(newly_parsed_data)
    combined_df = pd.concat([cached_df, new_df], ignore_index=True)
    if combined_df.empty:
        return pd.DataFrame()
    
    # THE BUGGY drop_duplicates() LINE HAS BEEN REMOVED.
    # The line below is the only logic that should be used to find the max scores.
    df_max_scores = combined_df.loc[combined_df.groupby(['Scenario', 'Sens'])['Score'].idxmax()]
    
    try:
        df_max_scores.to_parquet(CACHE_DF_PATH)
        with open(CACHE_INFO_PATH, 'w') as f:
            json.dump(current_files_info, f, indent=2)
        print("---- Cache updated successfully ----")
    except Exception as e:
        print(f"Error saving cache: {e}")
    return df_max_scores.reset_index(drop=True)

# This parser is now correct and does not need changes
def get_scenario_family_info(master_df, base_scenario):
    family_df = master_df[master_df['Scenario'].str.startswith(base_scenario)].copy()
    if family_df.empty:
        return None

    def parse_modifiers(scenario_name):
        modifier_str = scenario_name.replace(base_scenario, '', 1).strip()
        if not modifier_str:
            return {}
        UNIT_MAP = {'s': 'Duration', 'sec': 'Duration', 'm': 'Distance', 'hp': 'Health'}
        token_pattern = re.compile(r'(\d[\d.]*%?[a-zA-Z]*|[A-Za-z]+)')
        tokens = token_pattern.findall(modifier_str)
        def is_value(token):
            if re.fullmatch(r'[\d.]+%?', token): return True
            unit_match = re.fullmatch(r'([\d.]+%?)(\w+)', token)
            if unit_match and unit_match.groups()[1] in UNIT_MAP: return True
            return False
        modifiers = {}
        consumed = [False] * len(tokens)
        i = 0
        while i < len(tokens) - 1:
            if not consumed[i] and not consumed[i+1]:
                t1, t2 = tokens[i], tokens[i+1]
                is_t1_val, is_t2_val = is_value(t1), is_value(t2)
                if not is_t1_val and is_t2_val:
                    modifiers[t1] = (t2, 'word_value')
                    consumed[i] = consumed[i+1] = True
                    i += 2; continue
                elif is_t1_val and not is_t2_val:
                    modifiers[t2] = (t1, 'value_word')
                    consumed[i] = consumed[i+1] = True
                    i += 2; continue
            i += 1
        for i, token in enumerate(tokens):
            if not consumed[i]:
                unit_match = re.fullmatch(r'([\d.]+%?)(\w+)', token)
                if unit_match:
                    value, unit = unit_match.groups()
                    if unit in UNIT_MAP:
                        modifiers[UNIT_MAP[unit]] = (token, 'standalone')
                        consumed[i] = True
        if not all(consumed): return {}
        return modifiers
    family_df['Modifiers'] = family_df['Scenario'].apply(parse_modifiers)
    return family_df

# This analyzer function from the initial prompt has a bug where it doesn't check for empty family_df
# and also doesn't return an empty dataframe on no match, which can cause crashes.
# This version is more robust.
def analyze_variants(family_df, base_scenario, variable_axis, fixed_filters={}, pattern_filter=None):
    # This handles the case where only the base scenario is passed in, with no variants.
    if family_df is None or family_df.empty:
        return pd.DataFrame()

    if variable_axis is None:
        grid_df = family_df.pivot_table(index='Scenario', columns='Sens', values='Score')
        grid_df['BEST Score'] = grid_df.max(axis=1)
        grid_df['BEST CM'] = grid_df.idxmax(axis=1)
        grid_df['% vs Base'] = '100.0%'
        return grid_df.sort_index()

    filtered_rows = []
    for _, row in family_df.iterrows():
        modifiers = row['Modifiers']
        
        is_base_scenario = row['Scenario'] == base_scenario
        if not is_base_scenario and variable_axis not in modifiers:
            continue
        
        if not is_base_scenario and not modifiers:
            continue

        if pattern_filter and variable_axis in pattern_filter:
            if not is_base_scenario: # The pattern filter doesn't apply to the base scenario
                variable_pattern = modifiers[variable_axis][1]
                if variable_pattern not in pattern_filter[variable_axis]:
                    continue

        temp_modifiers_for_check = {k: v[0] for k, v in modifiers.items()}
        allowed_keys = set(fixed_filters.keys()) | {variable_axis}
        if not set(temp_modifiers_for_check.keys()).issubset(allowed_keys):
            continue
            
        match = True
        for key, value in fixed_filters.items():
            if temp_modifiers_for_check.get(key) != value:
                match = False; break
        if not match: continue
            
        filtered_rows.append(row)
        
    if not filtered_rows:
        print("No scenarios match the selected filters.")
        return pd.DataFrame() # Return an empty DataFrame, not None
        
    display_df = pd.DataFrame(filtered_rows)
    grid_df = display_df.pivot_table(index='Scenario', columns='Sens', values='Score')
    
    base_scores = display_df[display_df['Scenario'] == base_scenario]['Score']
    base_best_score = base_scores.max() if not base_scores.empty else 1.0
    if base_best_score == 0: base_best_score = 1.0

    grid_df['BEST Score'] = grid_df.max(axis=1)
    grid_df['BEST CM'] = grid_df.idxmax(axis=1)
    grid_df['% vs Base'] = (grid_df['BEST Score'] / base_best_score * 100).round(1).astype(str) + '%'
    return grid_df.sort_index()