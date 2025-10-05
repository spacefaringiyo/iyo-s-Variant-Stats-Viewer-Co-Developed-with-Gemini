import os
import pandas as pd
from pathlib import Path
import re

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

# --- NO OTHER CHANGES BELOW THIS LINE ---
def find_and_process_stats(stats_folder_path):
    path_obj = Path(stats_folder_path)
    if not path_obj.is_dir():
        return None
    all_scenarios_data = []
    challenge_files = list(path_obj.glob('*- Challenge -*.csv'))
    print(f"---- STARTING THE REAL SCAN NOW ---- Found {len(challenge_files)} files.")
    for file_path in challenge_files:
        parsed_data = parse_kovaaks_stats_file(file_path)
        if parsed_data:
            all_scenarios_data.append(parsed_data)
    if not all_scenarios_data:
        # Return an empty DataFrame instead of None if no data is found
        return pd.DataFrame()
    df = pd.DataFrame(all_scenarios_data)
    df_max_scores = df.loc[df.groupby(['Scenario', 'Sens'])['Score'].idxmax()]
    return df_max_scores.reset_index(drop=True)

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
