import os
import re
from datetime import datetime, timedelta
import pandas as pd

# --- GLOBAL CACHE ---
# Stores parsed modifiers: "ScenarioName" -> {Modifiers Dict}
# Prevents expensive regex recalculation on every tab open
MODIFIER_CACHE = {} 
# --------------------

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
            
        data = {'Duration': 60.0} 
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
                if start_time > end_time: start_time -= timedelta(days=1)
                duration_seconds = (end_time - start_time).total_seconds()
                if 0 < duration_seconds < 600: data['Duration'] = duration_seconds
            except: pass

        if 'Scenario' in data and 'Score' in data and 'Sens' in data:
            data['Timestamp'] = end_time
            return data
        else: return None
    except: return None

def get_scenario_family_info(all_runs_df, base_scenario):
    if all_runs_df is None or all_runs_df.empty: return None
    family_df = all_runs_df[all_runs_df['Scenario'].str.startswith(base_scenario)].copy()
    if family_df.empty: return None
    
    # Use the Global Cache
    global MODIFIER_CACHE

    def parse_modifiers(scenario_name):
        if scenario_name in MODIFIER_CACHE:
            return MODIFIER_CACHE[scenario_name]

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
                if not is_value(t1) and is_value(t2): 
                    modifiers[t1] = (t2, 'word_value'); consumed[i] = consumed[i+1] = True; i += 2; continue
                elif is_value(t1) and not is_value(t2): 
                    modifiers[t2] = (t1, 'value_word'); consumed[i] = consumed[i+1] = True; i += 2; continue
            i += 1
        for i, token in enumerate(tokens):
            if not consumed[i]:
                unit_match = re.fullmatch(r'([\d.]+%?)(\w+)', token)
                if unit_match:
                    value, unit = unit_match.groups()
                    if unit in UNIT_MAP: modifiers[UNIT_MAP[unit]] = (token, 'standalone'); consumed[i] = True
                elif '%' in token and is_value(token):
                    modifiers['Percent'] = (token, 'standalone'); consumed[i] = True
        
        if not all(consumed):
             MODIFIER_CACHE[scenario_name] = {}
             return {}
             
        MODIFIER_CACHE[scenario_name] = modifiers
        return modifiers
        
    family_df['Modifiers'] = family_df['Scenario'].apply(parse_modifiers)
    return family_df