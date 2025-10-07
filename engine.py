# --- START OF MODIFIED FILE engine.py ---

import os
import pandas as pd
from pathlib import Path
import re
import json

# Define cache file paths
CACHE_DF_PATH = 'kovaaks_cache.parquet'
CACHE_INFO_PATH = 'kovaaks_cache_info.json'

# --- MODIFIED FUNCTION ---
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
        # THIS IS THE NEW LINE. It will tell us what's wrong.
        print(f"Error processing file {os.path.basename(file_path)}: {e}")
        return None

# --- REBUILT CACHING FUNCTION ---
def find_and_process_stats(stats_folder_path):
    path_obj = Path(stats_folder_path)
    if not path_obj.is_dir():
        return None

    # 1. Load existing cache if available
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

    # 2. Scan for all challenge files and identify new ones
    all_challenge_files = list(path_obj.glob('*- Challenge -*.csv'))
    new_files_to_process = []
    
    current_files_info = {}
    for file_path in all_challenge_files:
        try:
            mtime = os.path.getmtime(file_path)
            current_files_info[str(file_path)] = mtime
            # Check if file is new or was modified since last cache
            if str(file_path) not in processed_files_info or mtime > processed_files_info[str(file_path)]:
                new_files_to_process.append(file_path)
        except FileNotFoundError:
            # This can happen in rare cases if a file is deleted during the scan
            continue

    print(f"---- STARTING SCAN ---- Found {len(all_challenge_files)} total files.")
    print(f"Found {len(new_files_to_process)} new files to process.")

    # 3. Process only the new files
    newly_parsed_data = []
    if new_files_to_process:
        for file_path in new_files_to_process:
            parsed_data = parse_kovaaks_stats_file(file_path)
            if parsed_data:
                newly_parsed_data.append(parsed_data)
    
    # If there's no new data and the cache is empty, return empty
    if not newly_parsed_data and cached_df.empty:
        return pd.DataFrame()
        
    # 4. Combine old and new data
    new_df = pd.DataFrame(newly_parsed_data)
    combined_df = pd.concat([cached_df, new_df], ignore_index=True)

    # 5. Perform the original aggregation to find max scores
    # We need to run this on the combined dataframe to ensure new high scores replace old ones
    if combined_df.empty:
        return pd.DataFrame()

    # Drop duplicates to keep the latest entry for a scenario/sens combo if it was re-processed
    if not new_df.empty:
        unique_cols = ['Scenario', 'Sens']
        # Keep the last entry from the combined dataframe, which will be the newest one
        combined_df.drop_duplicates(subset=unique_cols, keep='last', inplace=True)

    df_max_scores = combined_df.loc[combined_df.groupby(['Scenario', 'Sens'])['Score'].idxmax()]
    
    # 6. Update and save the cache
    try:
        df_max_scores.to_parquet(CACHE_DF_PATH)
        with open(CACHE_INFO_PATH, 'w') as f:
            json.dump(current_files_info, f, indent=2)
        print("---- Cache updated successfully ----")
    except Exception as e:
        print(f"Error saving cache: {e}")

    return df_max_scores.reset_index(drop=True)

# --- NO OTHER CHANGES BELOW THIS LINE ---
def get_scenario_family_info(master_df, base_scenario):
    family_df = master_df[master_df['Scenario'].str.startswith(base_scenario)].copy()
    if family_df.empty:
        return None
    modifier_pattern = re.compile(r'([A-Za-z]+)\s+([\d.]+%?)')
    def parse_modifiers(scenario_name):
        modifier_str = scenario_name.replace(base_scenario, '', 1).strip()
        return dict(modifier_pattern.findall(modifier_str))
    family_df['Modifiers'] = family_df['Scenario'].apply(parse_modifiers)
    family_df['Parsed_Modifiers_Text'] = family_df['Modifiers'].apply(
        lambda mods: " ".join(sorted([f"{k} {v}" for k, v in mods.items()]))
    )
    family_df['Original_Modifiers_Text'] = family_df['Scenario'].apply(
        lambda name: name.replace(base_scenario, '', 1).strip()
    )
    family_df = family_df[family_df['Parsed_Modifiers_Text'] == family_df['Original_Modifiers_Text']]
    return family_df

def analyze_variants(family_df, base_scenario, variable_axis, fixed_filters={}):
    filtered_rows = []
    for _, row in family_df.iterrows():
        modifiers = row['Modifiers']
        allowed_keys = set(fixed_filters.keys()) | {variable_axis}
        if not set(modifiers.keys()).issubset(allowed_keys):
            continue
        match = True
        for key, value in fixed_filters.items():
            if modifiers.get(key) != value:
                match = False
                break
        if not match:
            continue
        filtered_rows.append(row)
    if not filtered_rows:
        print("No scenarios match the selected filters.")
        return None
    display_df = pd.DataFrame(filtered_rows)
    grid_df = display_df.pivot_table(index='Scenario', columns='Sens', values='Score')
    effective_base_name = base_scenario
    if fixed_filters:
        sorted_filters = sorted(fixed_filters.items())
        effective_base_name += " " + " ".join([f"{k} {v}" for k, v in sorted_filters])
    base_scores = display_df[display_df['Scenario'] == effective_base_name]['Score']
    base_best_score = base_scores.max() if not base_scores.empty else 1.0
    if base_best_score == 0: base_best_score = 1.0
    grid_df['BEST Score'] = grid_df.max(axis=1)
    grid_df['BEST CM'] = grid_df.idxmax(axis=1)
    grid_df['% vs Base'] = (grid_df['BEST Score'] / base_best_score * 100).round(1).astype(str) + '%'
    return grid_df.sort_index()