# --- START OF FINAL, POLISHED app.py ---

import customtkinter
import tkinter
from tkinter import filedialog
import os
import threading
import pandas as pd
import engine
from CTkTable import CTkTable
import re
from collections import defaultdict
import json
import numpy as np

customtkinter.set_appearance_mode("System")
customtkinter.set_default_color_theme("blue")

USER_DATA_FILE = "user_data.json"

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        # --- Add a flag to track the initial data load ---
        self.is_first_load = True

        self.master_df, self.scenario_list, self.results_table, self.current_family_info, self.current_unfiltered_grid_data = None, [], None, None, None
        self.variable_axis_var = customtkinter.StringVar()
        self.sens_filter_var = customtkinter.StringVar(value="All")
        self.highlight_mode_var = customtkinter.StringVar(value="Performance Drop")
        self.show_decimals_var = customtkinter.StringVar(value="Off")
        self.target_score_var = customtkinter.StringVar(value="3000")
        
        self.target_scores_by_scenario = {}
        self.format_filter_vars = {}
        self.format_filter_preferences = {}
        self.favorites, self.recents = [], []
        self.collapsed_states = {}
        self.hidden_scenarios = set()
        self.hidden_cms = set()
        self.load_user_data()

        self.title("iyo's Variant Stats Viewer co-developed with Gemini")
        self.geometry("1400x950")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.bind("<F5>", lambda event: self.load_stats_thread())

        self.top_frame = customtkinter.CTkFrame(self, corner_radius=0)
        self.top_frame.grid(row=0, column=0, sticky="nsew")
        self.top_frame.grid_columnconfigure(0, weight=1)
        
        self.bottom_frame = customtkinter.CTkFrame(self)
        self.bottom_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.bottom_frame.grid_columnconfigure(0, weight=1)
        self.bottom_frame.grid_rowconfigure(1, weight=1)

        self.rating_frame = customtkinter.CTkFrame(self.bottom_frame)
        self.rating_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(0, 5))
        self.rating_frame.grid_columnconfigure(0, weight=1)
        self.rating_label = customtkinter.CTkLabel(self.rating_frame, text="Rating: -", font=("Arial", 24, "bold"))
        self.rating_label.grid(row=0, column=0, pady=10)
        self.rating_frame.grid_remove()

        self._build_path_and_load_controls()

        self.set_default_path()
        self.after(100, self.load_stats_thread)

    def _build_path_and_load_controls(self):
        self.path_frame = customtkinter.CTkFrame(self.top_frame)
        self.path_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10,0))
        self.path_frame.grid_columnconfigure(1, weight=1)
        
        self.select_path_button = customtkinter.CTkButton(self.path_frame, text="Select Stats Folder", command=self.select_stats_folder)
        self.select_path_button.grid(row=0, column=0, padx=(0,10), pady=10)
        
        self.path_entry = customtkinter.CTkEntry(self.path_frame, placeholder_text="Path to KovaaK's stats folder...")
        self.path_entry.grid(row=0, column=1, columnspan=2, sticky="ew", pady=10)
        
        action_frame = customtkinter.CTkFrame(self.path_frame, fg_color="transparent")
        action_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0,10))
        action_frame.grid_columnconfigure(0, weight=1)
        
        self.load_button = customtkinter.CTkButton(action_frame, text="Load Stats", font=("Arial", 18, "bold"), height=50, command=self.load_stats_thread)
        self.load_button.grid(row=0, column=0, sticky="ew")
        
        self.status_label = customtkinter.CTkLabel(action_frame, text="Ready. Select stats folder and click 'Load Stats'.", anchor="w")
        self.status_label.grid(row=0, column=1, padx=(10, 0), sticky="w")
        
        self.progress_bar = customtkinter.CTkProgressBar(self.path_frame, mode='indeterminate')

    def _build_main_ui_controls(self):
        self.main_controls_header, self.main_controls_content = self._create_collapsible_section("Options & Analysis", "main_controls", 1)
        self.main_controls_content.grid_columnconfigure(0, weight=1)

        selection_content_frame = customtkinter.CTkFrame(self.main_controls_content); selection_content_frame.grid(row=0, column=0, sticky="ew", pady=(0,5))
        selection_content_frame.grid_columnconfigure(0, weight=1)
        search_frame = customtkinter.CTkFrame(selection_content_frame); search_frame.grid(row=0, column=0, sticky="ew", pady=(0,5)); search_frame.grid_columnconfigure(0, weight=1)
        user_lists_frame = customtkinter.CTkFrame(selection_content_frame); user_lists_frame.grid(row=1, column=0, sticky="ew"); user_lists_frame.grid_columnconfigure((0,1), weight=1)
        self.scenario_entry_label = customtkinter.CTkLabel(search_frame, text="Search for Base Scenario:"); self.scenario_entry_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(5,0))
        self.scenario_search_var = customtkinter.StringVar(); self.scenario_search_var.trace_add("write", self.update_autocomplete)
        self.scenario_entry = customtkinter.CTkEntry(search_frame, textvariable=self.scenario_search_var, state="disabled"); self.scenario_entry.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        self.fav_button = customtkinter.CTkButton(search_frame, text="☆", font=("Arial", 20), width=30, command=self.toggle_favorite); self.fav_button.grid(row=1, column=1, padx=(0,10), pady=5)
        self.autocomplete_listbox = customtkinter.CTkScrollableFrame(search_frame, height=150); self.autocomplete_listbox.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=5); self.autocomplete_listbox.grid_remove()
        self.favorites_frame = customtkinter.CTkFrame(user_lists_frame); self.favorites_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.recents_frame = customtkinter.CTkFrame(user_lists_frame); self.recents_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.update_user_lists_display()

        display_top_row_frame = customtkinter.CTkFrame(self.main_controls_content); display_top_row_frame.grid(row=1, column=0, sticky="ew"); display_top_row_frame.grid_columnconfigure((0, 1), weight=1)
        sens_filter_group = customtkinter.CTkFrame(display_top_row_frame); sens_filter_group.grid(row=0, column=0, padx=(0,5), pady=5, sticky="ew")
        customtkinter.CTkLabel(sens_filter_group, text="Sensitivity Filter:").pack(side="left", padx=(10,5), pady=5)
        customtkinter.CTkRadioButton(sens_filter_group, text="All", variable=self.sens_filter_var, value="All", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        customtkinter.CTkRadioButton(sens_filter_group, text="5cm Inc.", variable=self.sens_filter_var, value="5cm", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        customtkinter.CTkRadioButton(sens_filter_group, text="10cm Inc.", variable=self.sens_filter_var, value="10cm", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        misc_group = customtkinter.CTkFrame(display_top_row_frame); misc_group.grid(row=0, column=1, padx=(5,0), pady=5, sticky="ew")
        customtkinter.CTkSwitch(misc_group, text="Show Decimals", variable=self.show_decimals_var, onvalue="On", offvalue="Off", command=self.on_display_option_change).pack(side="left", padx=10, pady=5)
        customtkinter.CTkButton(misc_group, text="Manage Hidden", command=self.open_manage_hidden_window).pack(side="left", padx=10, pady=5)
        
        self.filters_frame = customtkinter.CTkFrame(self.main_controls_content); self.filters_frame.grid(row=2, column=0, sticky="ew", pady=(5,0))
        self.format_filter_frame = customtkinter.CTkFrame(self.main_controls_content); self.format_filter_frame.grid(row=3, column=0, sticky="ew", pady=(0,5))
        
        highlight_group = customtkinter.CTkFrame(self.top_frame)
        highlight_group.grid(row=3, column=0, sticky="ew", padx=10, pady=(0,5))
        customtkinter.CTkLabel(highlight_group, text="Highlight Mode:").pack(side="left", padx=(10,5), pady=5)
        customtkinter.CTkRadioButton(highlight_group, text="None", variable=self.highlight_mode_var, value="None", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        customtkinter.CTkRadioButton(highlight_group, text="Perf. Drop", variable=self.highlight_mode_var, value="Performance Drop", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        customtkinter.CTkRadioButton(highlight_group, text="Row Heatmap", variable=self.highlight_mode_var, value="Row Heatmap", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        customtkinter.CTkRadioButton(highlight_group, text="Global Heatmap", variable=self.highlight_mode_var, value="Global Heatmap", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        customtkinter.CTkRadioButton(highlight_group, text="Target Score", variable=self.highlight_mode_var, value="Target Score", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        self.target_score_entry = customtkinter.CTkEntry(highlight_group, textvariable=self.target_score_var, width=80)
        self.target_score_entry.pack(side="left", padx=(0,10), pady=5)
        self.target_score_entry.bind("<Return>", self.on_display_option_change)

        self._apply_initial_collapse_state()
        self.on_display_option_change()

    def on_load_complete(self, result_df):
        self.progress_bar.grid_remove()
        
        if not hasattr(self, 'main_controls_content'):
            self._build_main_ui_controls()

        if result_df is not None and not result_df.empty:
            self.master_df = result_df
            unique_scenarios = self.master_df['Scenario'].unique()
            base_scenarios = {s for s in unique_scenarios if any(s != other and s in other for other in unique_scenarios)}
            all_scenarios = sorted(list(base_scenarios.union(unique_scenarios)))
            self.scenario_list = all_scenarios
            self.status_label.configure(text=f"Loaded {len(self.master_df)} combos. Ready to search.")
            self.scenario_entry.configure(state="normal")
            self.load_button.configure(text="Refresh Stats (F5)") 
            
            # --- REFINED LOGIC WITH THE "FIRST LOAD" FLAG ---
            if self.is_first_load:
                self.is_first_load = False # Flip the flag so this doesn't run on refresh
                if self.recents:
                    last_viewed = self.recents[0]
                    if last_viewed["name"] in self.scenario_list:
                        self.after(50, self.select_from_list, last_viewed)
                        # This part now only runs on the initial startup
                        if not self.main_controls_content.winfo_viewable():
                             self.main_controls_content.toggle_function()
            else:
                # On refresh, just update the data for the currently selected scenario
                self.update_grid()
        else:
            self.status_label.configure(text="Load complete, but no data was found.")
            self.master_df = None
            self.scenario_list = []
        
        self.load_button.configure(state="normal")
        self.select_path_button.configure(state="normal")
    
    def _create_collapsible_section(self, title, section_key, row_index):
        header_frame = customtkinter.CTkFrame(self.top_frame, fg_color=("gray85", "gray20"), corner_radius=6)
        header_frame.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(5, 1))
        content_frame = customtkinter.CTkFrame(self.top_frame)
        content_frame.grid(row=row_index + 1, column=0, sticky="ew", padx=10, pady=(0, 5))
        theme_fg_color = customtkinter.ThemeManager.theme["CTkButton"]["fg_color"]
        theme_hover_color = customtkinter.ThemeManager.theme["CTkButton"]["hover_color"]
        toggle_button = customtkinter.CTkButton(header_frame, text="▼", width=32, height=32, font=customtkinter.CTkFont(size=22, weight="bold"), fg_color=theme_fg_color, hover_color=theme_hover_color)
        def toggle():
            is_collapsed = not content_frame.winfo_viewable()
            if is_collapsed:
                content_frame.grid()
                toggle_button.configure(text="▼")
                self.collapsed_states[section_key] = False
            else:
                content_frame.grid_remove()
                toggle_button.configure(text="▶")
                self.collapsed_states[section_key] = True
            self.save_user_data()
        toggle_button.configure(command=toggle)
        toggle_button.pack(side="left", padx=(8, 0))
        header_label = customtkinter.CTkLabel(header_frame, text=title, font=customtkinter.CTkFont(weight="bold"))
        header_label.pack(side="left", padx=15, pady=10)
        header_frame.bind("<Button-1>", lambda e: toggle())
        header_label.bind("<Button-1>", lambda e: toggle())
        header_frame.configure(cursor="hand2")
        header_label.configure(cursor="hand2")
        toggle_button.configure(cursor="hand2")
        content_frame.toggle_function = toggle
        return header_frame, content_frame

    def _apply_initial_collapse_state(self):
        if self.collapsed_states.get("main_controls", False):
            if hasattr(self, 'main_controls_content') and self.main_controls_content.winfo_viewable():
                self.main_controls_content.toggle_function()

    def on_closing(self):
        if self.results_table: self.results_table.destroy()
        self.destroy()

    def on_display_option_change(self, event=None):
        if hasattr(self, 'target_score_entry'):
            if self.highlight_mode_var.get() == "Target Score": self.target_score_entry.pack(side="left", padx=(0,10), pady=5)
            else: self.target_score_entry.pack_forget()
        self.save_user_data(); self.display_grid_data()

    def load_user_data(self):
        if os.path.exists(USER_DATA_FILE):
            try:
                with open(USER_DATA_FILE, 'r') as f: data = json.load(f)
                loaded_favs = data.get("favorites", [])
                self.favorites = [{"name": fav, "axis": ""} if isinstance(fav, str) else fav for fav in loaded_favs]
                loaded_recents = data.get("recents", [])
                self.recents = [{"name": rec, "axis": ""} if isinstance(rec, str) else rec for rec in loaded_recents]
                self.sens_filter_var.set(data.get("sens_filter_preference", "All"))
                self.highlight_mode_var.set(data.get("highlight_mode_preference", "Performance Drop"))
                self.show_decimals_var.set(data.get("show_decimals_preference", "Off"))
                self.target_scores_by_scenario = data.get("target_scores_by_scenario", {})
                self.collapsed_states = data.get("collapsed_states", {})
                self.hidden_scenarios = set(data.get("hidden_scenarios", [])); self.hidden_cms = set(data.get("hidden_cms", []))
                self.format_filter_preferences = data.get("format_filter_preferences", {})
                self.collapsed_states['main_controls'] = False
            except (json.JSONDecodeError, AttributeError): 
                self.favorites, self.recents, self.collapsed_states, self.target_scores_by_scenario, self.format_filter_preferences = [], [], {}, {}, {}
                self.hidden_scenarios, self.hidden_cms = set(), set()
    
    def load_stats_thread(self):
        stats_path = self.path_entry.get()
        if not stats_path or not os.path.isdir(stats_path): return
        self.status_label.configure(text="Loading stats, please wait..."); self.load_button.configure(state="disabled"); self.select_path_button.configure(state="disabled")
        self.progress_bar.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=(0,10))
        self.progress_bar.start()
        thread = threading.Thread(target=self.perform_load, args=(stats_path,)); thread.daemon = True; thread.start()
        
    def save_user_data(self):
        current_scenario = self.scenario_search_var.get()
        if current_scenario:
            self.target_scores_by_scenario[current_scenario] = self.target_score_var.get()
            variable_axis = self.variable_axis_var.get()
            if variable_axis:
                unchecked_patterns = [p for p, v in self.format_filter_vars.items() if not v.get()]
                if current_scenario not in self.format_filter_preferences:
                    self.format_filter_preferences[current_scenario] = {}
                if unchecked_patterns:
                    self.format_filter_preferences[current_scenario][variable_axis] = unchecked_patterns
                elif variable_axis in self.format_filter_preferences.get(current_scenario, {}):
                    del self.format_filter_preferences[current_scenario][variable_axis]
                if not self.format_filter_preferences.get(current_scenario):
                    del self.format_filter_preferences[current_scenario]
        data_to_save = {"favorites": self.favorites, "recents": self.recents, "sens_filter_preference": self.sens_filter_var.get(), "highlight_mode_preference": self.highlight_mode_var.get(), "show_decimals_preference": self.show_decimals_var.get(), "target_scores_by_scenario": self.target_scores_by_scenario, "collapsed_states": self.collapsed_states, "hidden_scenarios": list(self.hidden_scenarios), "hidden_cms": list(self.hidden_cms), "format_filter_preferences": self.format_filter_preferences}
        with open(USER_DATA_FILE, 'w') as f: json.dump(data_to_save, f, indent=2)

    def is_float(self, val):
        try: float(val); return True
        except (ValueError, TypeError): return False

    def _apply_format_filter(self):
        self.save_user_data()
        variable_axis = self.variable_axis_var.get()
        pattern_filter = {}
        selected_patterns = [p for p, v in self.format_filter_vars.items() if v.get()]
        if selected_patterns: pattern_filter[variable_axis] = selected_patterns
        df_to_process = self.current_family_info
        if self.hidden_scenarios and df_to_process is not None:
            df_to_process = df_to_process[~df_to_process['Scenario'].isin(self.hidden_scenarios)]
        self.current_unfiltered_grid_data = engine.analyze_variants(df_to_process, variable_axis=variable_axis, fixed_filters={}, base_scenario=self.scenario_search_var.get(), pattern_filter=pattern_filter)
        self.display_grid_data()

    def build_filters_and_get_data(self):
        for widget in self.filters_frame.winfo_children(): widget.destroy()
        for widget in self.format_filter_frame.winfo_children(): widget.destroy()
        self.format_filter_frame.grid_remove()
        self.format_filter_vars = {}
        if self.current_family_info is None or self.current_family_info.empty:
            self.filters_frame.grid_remove(); self.display_grid_data(); return
        filtered_family_info = self.current_family_info.copy()
        if self.hidden_scenarios: filtered_family_info = filtered_family_info[~filtered_family_info['Scenario'].isin(self.hidden_scenarios)]
        all_modifiers = defaultdict(set)
        for mod_dict in filtered_family_info['Modifiers']:
            for k, v_tuple in mod_dict.items(): all_modifiers[k].add(v_tuple)
        if not all_modifiers:
            self.filters_frame.grid_remove()
            base_name = self.scenario_search_var.get()
            base_df = filtered_family_info[filtered_family_info['Scenario'] == base_name]
            self.current_unfiltered_grid_data = engine.analyze_variants(base_df, base_scenario=base_name, variable_axis=None) if not base_df.empty else pd.DataFrame()
            self.display_grid_data(); return
        self.filters_frame.grid()
        customtkinter.CTkLabel(self.filters_frame, text="Compare by:").pack(side="left", padx=(10,5), pady=5)
        preferred_axis = self.variable_axis_var.get()
        if not preferred_axis or preferred_axis not in all_modifiers.keys():
            new_axis = list(all_modifiers.keys())[0]
            self.variable_axis_var.set(new_axis)
        for key in sorted(list(all_modifiers.keys())):
            rb = customtkinter.CTkRadioButton(self.filters_frame, text=key, variable=self.variable_axis_var, value=key, command=self.build_filters_and_get_data)
            rb.pack(side="left", padx=5, pady=5)
        patterns_found = set()
        variable_axis = self.variable_axis_var.get()
        base_scenario = self.scenario_search_var.get()
        if variable_axis in all_modifiers:
            for value_tuple in all_modifiers[variable_axis]: patterns_found.add(value_tuple[1])
        if len(patterns_found) > 1:
            self.format_filter_frame.grid()
            customtkinter.CTkLabel(self.format_filter_frame, text="Filter Format:").pack(side="left", padx=(10,5), pady=5)
            def get_pattern_label(pattern_key):
                if pattern_key == 'word_value': return f"{variable_axis} #"
                if pattern_key == 'value_word': return f"# {variable_axis}"
                return "Standalone"
            scenario_prefs = self.format_filter_preferences.get(base_scenario, {})
            unchecked_for_this_axis = scenario_prefs.get(variable_axis, [])
            for pattern in sorted(list(patterns_found)):
                is_checked = pattern not in unchecked_for_this_axis
                var = customtkinter.BooleanVar(value=is_checked); self.format_filter_vars[pattern] = var
                cb = customtkinter.CTkCheckBox(self.format_filter_frame, text=get_pattern_label(pattern), variable=var, command=self._apply_format_filter)
                cb.pack(side="left", padx=5, pady=5)
        self._apply_format_filter()

    def display_grid_data(self):
        if self.results_table: self.results_table.destroy()
        if self.current_unfiltered_grid_data is None or self.current_unfiltered_grid_data.empty:
            self.rating_frame.grid_remove(); return
        self.rating_frame.grid()
        grid_data = self.current_unfiltered_grid_data.copy()
        if self.hidden_cms:
            cols_to_drop = [c for c in grid_data.columns if str(c) in self.hidden_cms]
            grid_data.drop(columns=cols_to_drop, inplace=True, errors='ignore')
        if grid_data.empty: self.rating_frame.grid_remove(); return
        sens_filter = self.sens_filter_var.get()
        if sens_filter != "All":
            increment = 5 if sens_filter == "5cm" else 10; cols_to_keep = ['Scenario', 'BEST Score', 'BEST CM', '% vs Base']
            sens_cols_str = [c for c in grid_data.columns if str(c).replace('.','',1).isdigit()]
            for col in sens_cols_str:
                if float(col) % increment == 0: cols_to_keep.append(col)
            grid_data = grid_data[[c for c in grid_data.columns if c in cols_to_keep]]
        sens_cols_for_rating = [c for c in grid_data.columns if self.is_float(c)]
        if sens_cols_for_rating and not grid_data.empty:
            numeric_data_rating = grid_data[sens_cols_for_rating].apply(pd.to_numeric, errors='coerce').fillna(0)
            rating = numeric_data_rating.sum().sum() / (len(grid_data) * len(sens_cols_for_rating)) if len(grid_data) * len(sens_cols_for_rating) > 0 else 0
            self.rating_label.configure(text=f"Rating: {round(rating)}")
        else: self.rating_label.configure(text="Rating: -")
        current_scenario = self.scenario_search_var.get()
        current_axis = self.variable_axis_var.get()
        current_recent_entry = {"name": current_scenario, "axis": current_axis}
        if current_scenario and (not self.recents or self.recents[0] != current_recent_entry):
            self.add_to_recents(current_scenario, current_axis)
        base_scenario = self.scenario_search_var.get()
        grid_data = grid_data.fillna('').reset_index(inplace=False)
        if 'index' in grid_data.columns: grid_data = grid_data.drop(columns='index')
        def get_sort_key(scenario_name):
            modifier_str = scenario_name.replace(base_scenario, '').strip(); numbers = re.findall(r'(\d+\.?\d*)', modifier_str)
            return float(numbers[-1]) if numbers else 100
        if 'Scenario' in grid_data.columns and not grid_data.empty:
            grid_data['sort_key'] = grid_data['Scenario'].apply(get_sort_key); grid_data.sort_values(by='sort_key', inplace=True); grid_data.drop(columns='sort_key', inplace=True)
        sens_cols_for_avg = [c for c in grid_data.columns if self.is_float(c)]
        if sens_cols_for_avg: grid_data['AVG'] = grid_data[sens_cols_for_avg].apply(pd.to_numeric, errors='coerce').mean(axis=1)
        else: grid_data['AVG'] = np.nan
        summary_cols_map = {'BEST Score': 'Best', 'BEST CM': 'cm', '% vs Base': '%', 'AVG': 'AVG'}; grid_data.rename(columns=summary_cols_map, inplace=True)
        cols = grid_data.columns.tolist()
        sens_cols = sorted([c for c in cols if c not in summary_cols_map.values() and c != 'Scenario' and self.is_float(c)], key=float)
        other_cols = [c for c in cols if c not in summary_cols_map.values() and c != 'Scenario' and not self.is_float(c)]
        final_col_order = ['Scenario'] + sens_cols + other_cols + ['AVG', 'Best', 'cm', '%']; final_col_order = [c for c in final_col_order if c in grid_data.columns]; grid_data = grid_data[final_col_order]
        values = grid_data.values.tolist()
        if self.show_decimals_var.get() == "Off":
            percent_col_idx = -1
            if '%' in grid_data.columns: percent_col_idx = grid_data.columns.get_loc('%')
            for r_idx, row in enumerate(values):
                for c_idx, cell in enumerate(row):
                    if c_idx == percent_col_idx and isinstance(cell, str) and '%' in cell:
                        try: num_val = float(cell.replace('%', '')); values[r_idx][c_idx] = f"{round(num_val)}%"
                        except (ValueError, TypeError): continue
                    else:
                        try: values[r_idx][c_idx] = int(float(cell))
                        except (ValueError, TypeError): continue
        formatted_columns = [f"{col}cm" if self.is_float(col) else col for col in grid_data.columns]
        table_values = [formatted_columns] + values
        self.results_table = CTkTable(self.bottom_frame, values=table_values); self.results_table.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        if 'Scenario' in final_col_order: self.results_table.edit_column(0, width=350)
        self.bind_hide_events(table_values); self.apply_highlighting(grid_data)

    def apply_highlighting(self, grid_data):
        mode = self.highlight_mode_var.get()
        if mode == "None" or grid_data.empty: return
        perf_drop_cols = [c for c in grid_data.columns if c != 'Scenario' and c != 'cm']
        heatmap_cols = [c for c in grid_data.columns if self.is_float(c) or c == 'AVG' or c == 'Best']
        values_only = grid_data.values
        global_min, global_max = None, None
        if mode == "Global Heatmap":
            all_scores = [float(cell) for row in values_only for c_idx, cell in enumerate(row) if grid_data.columns[c_idx] in heatmap_cols and str(cell).replace('.','',1).isdigit()]
            if all_scores: global_min, global_max = min(all_scores), max(all_scores)
        target_score_val = 0; is_target_mode = mode == "Target Score"; grid_min_score = 0
        if is_target_mode:
            try:
                target_score_val = float(self.target_score_var.get())
                all_scores_in_grid = [float(cell) for row in values_only for c_idx, cell in enumerate(row) if grid_data.columns[c_idx] in heatmap_cols and self.is_float(cell)]
                if all_scores_in_grid: grid_min_score = min(all_scores_in_grid)
            except (ValueError, TypeError): is_target_mode = False
        for r_idx, row_data in enumerate(values_only):
            if mode == "Performance Drop" and r_idx > 0:
                for c_idx, col_name in enumerate(grid_data.columns):
                    if col_name not in perf_drop_cols: continue
                    try:
                        current_val = float(str(row_data[c_idx]).replace('%', '')); above_val = float(str(values_only[r_idx - 1][c_idx]).replace('%', ''))
                        if current_val < above_val: self.results_table.frame[r_idx + 1, c_idx].configure(fg_color="#592020")
                    except (ValueError, TypeError): continue
            elif mode == "Row Heatmap":
                row_scores = [float(row_data[c_idx]) for c_idx, col in enumerate(grid_data.columns) if col in heatmap_cols and str(row_data[c_idx]).replace('.','',1).isdigit()]
                if len(row_scores) < 2: continue
                min_score, max_score = min(row_scores), max(row_scores)
                if min_score == max_score: continue
                for c_idx, col_name in enumerate(grid_data.columns):
                    if col_name not in heatmap_cols: continue
                    try:
                        val = float(row_data[c_idx]); norm = (val - min_score) / (max_score - min_score)
                        self.results_table.frame[r_idx + 1, c_idx].configure(fg_color=self.get_heatmap_color(norm))
                    except (ValueError, TypeError): continue
            elif mode == "Global Heatmap" and global_min is not None and global_max is not None and global_min != global_max:
                for c_idx, col_name in enumerate(grid_data.columns):
                    if col_name not in heatmap_cols: continue
                    try:
                        val = float(row_data[c_idx]); norm = (val - global_min) / (global_max - global_min)
                        self.results_table.frame[r_idx + 1, c_idx].configure(fg_color=self.get_heatmap_color(norm))
                    except (ValueError, TypeError): continue
            elif is_target_mode:
                for c_idx, col_name in enumerate(grid_data.columns):
                    if col_name not in heatmap_cols: continue
                    try:
                        val = float(row_data[c_idx])
                        if val >= target_score_val: self.results_table.frame[r_idx + 1, c_idx].configure(fg_color="#591e9c")
                        else:
                            denominator = target_score_val - grid_min_score
                            if denominator <= 0: denominator = 1
                            norm = (val - grid_min_score) / denominator
                            self.results_table.frame[r_idx + 1, c_idx].configure(fg_color=self.get_heatmap_color(norm))
                    except (ValueError, TypeError): continue

    def get_heatmap_color(self, normalized_value):
        normalized_value = max(0, min(1, normalized_value)); COLOR_RED = (120, 47, 47); COLOR_YELLOW = (122, 118, 50); COLOR_GREEN = (54, 107, 54)
        if normalized_value < 0.5:
            local_norm = normalized_value * 2; r = int(COLOR_RED[0] * (1 - local_norm) + COLOR_YELLOW[0] * local_norm); g = int(COLOR_RED[1] * (1 - local_norm) + COLOR_YELLOW[1] * local_norm); b = int(COLOR_RED[2] * (1 - local_norm) + COLOR_YELLOW[2] * local_norm)
        else:
            local_norm = (normalized_value - 0.5) * 2; r = int(COLOR_YELLOW[0] * (1 - local_norm) + COLOR_GREEN[0] * local_norm); g = int(COLOR_YELLOW[1] * (1 - local_norm) + COLOR_GREEN[1] * local_norm); b = int(COLOR_YELLOW[2] * (1 - local_norm) + COLOR_GREEN[2] * local_norm)
        return f"#{r:02x}{g:02x}{b:02x}"

    def bind_hide_events(self, table_values):
        if not self.results_table or not table_values: return
        column_headers = table_values[0]
        for j, header_text in enumerate(column_headers):
            cm_value = header_text.replace('cm', '')
            if self.is_float(cm_value): self.results_table.frame[0, j].bind("<Button-3>", lambda e, cm=cm_value: self.show_col_context_menu(e, cm))
        data_rows = table_values[1:]
        for i, row_data in enumerate(data_rows):
            if row_data and row_data[0]: self.results_table.frame[i + 1, 0].bind("<Button-3>", lambda e, s=row_data[0]: self.show_row_context_menu(e, s))

    def show_col_context_menu(self, event, cm_value):
        menu = tkinter.Menu(self, tearoff=0); menu.add_command(label=f"Hide {cm_value}cm", command=lambda: self.hide_cm(cm_value)); menu.tk_popup(event.x_root, event.y_root)

    def show_row_context_menu(self, event, scenario_name):
        menu = tkinter.Menu(self, tearoff=0); menu.add_command(label=f"Hide Scenario", command=lambda: self.hide_scenario(scenario_name)); menu.tk_popup(event.x_root, event.y_root)

    def hide_cm(self, cm_value):
        self.hidden_cms.add(str(cm_value)); self.save_user_data(); self.display_grid_data()

    def hide_scenario(self, scenario_name):
        self.hidden_scenarios.add(scenario_name); self.save_user_data(); self.build_filters_and_get_data()

    def open_manage_hidden_window(self):
        win = customtkinter.CTkToplevel(self); win.title("Manage Hidden Items"); win.geometry("600x400"); win.transient(self); win.grid_columnconfigure(0, weight=1); win.grid_rowconfigure(1, weight=1)
        customtkinter.CTkLabel(win, text="Right-click a header to hide it. Un-hide items below.", font=customtkinter.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10)
        tabview = customtkinter.CTkTabview(win); tabview.grid(row=1, column=0, padx=10, pady=10, sticky="nsew"); tabview.add("Hidden Scenarios"); tabview.add("Hidden CMs")
        self._populate_manage_hidden_window(tabview)

    def _populate_manage_hidden_window(self, tabview):
        for tab_name in ["Hidden Scenarios", "Hidden CMs"]:
            for widget in tabview.tab(tab_name).winfo_children():
                widget.destroy()
        scenarios_frame = customtkinter.CTkScrollableFrame(tabview.tab("Hidden Scenarios")); scenarios_frame.pack(expand=True, fill="both")
        if not self.hidden_scenarios: customtkinter.CTkLabel(scenarios_frame, text="No hidden scenarios.").pack(pady=10)
        for scenario in sorted(list(self.hidden_scenarios)):
            item_frame = customtkinter.CTkFrame(scenarios_frame); item_frame.pack(fill="x", pady=2)
            customtkinter.CTkLabel(item_frame, text=scenario, wraplength=400, justify="left").pack(side="left", padx=5, pady=2)
            customtkinter.CTkButton(item_frame, text="Unhide", width=80, command=lambda s=scenario: self.unhide_item('scenario', s, tabview)).pack(side="right", padx=5)
        cms_frame = customtkinter.CTkScrollableFrame(tabview.tab("Hidden CMs")); cms_frame.pack(expand=True, fill="both")
        if not self.hidden_cms: customtkinter.CTkLabel(cms_frame, text="No hidden cm values.").pack(pady=10)
        for cm in sorted(list(self.hidden_cms), key=float):
            item_frame = customtkinter.CTkFrame(cms_frame); item_frame.pack(fill="x", pady=2)
            customtkinter.CTkLabel(item_frame, text=f"{cm}cm").pack(side="left", padx=5, pady=2)
            customtkinter.CTkButton(item_frame, text="Unhide", width=80, command=lambda c=cm: self.unhide_item('cm', c, tabview)).pack(side="right", padx=5)

    def unhide_item(self, item_type, value, tabview):
        if item_type == 'scenario': self.hidden_scenarios.remove(value)
        elif item_type == 'cm': self.hidden_cms.remove(str(value))
        self.save_user_data(); self._populate_manage_hidden_window(tabview)
        if item_type == 'scenario': self.build_filters_and_get_data()
        else: self.display_grid_data()

    def toggle_favorite(self):
        scenario = self.scenario_search_var.get()
        if not scenario: return
        fav_entry = next((item for item in self.favorites if item["name"] == scenario), None)
        if fav_entry: self.favorites.remove(fav_entry)
        else: self.favorites.append({"name": scenario, "axis": self.variable_axis_var.get()})
        self.save_user_data(); self.update_user_lists_display(); self.update_fav_button_state()

    def add_to_recents(self, scenario, axis):
        self.recents = [rec for rec in self.recents if rec['name'] != scenario]
        self.recents.insert(0, {"name": scenario, "axis": axis}); self.recents = self.recents[:5]
        self.save_user_data(); self.update_user_lists_display()

    def update_user_lists_display(self):
        for frame in [self.favorites_frame, self.recents_frame]:
            for widget in frame.winfo_children(): widget.destroy()
        customtkinter.CTkLabel(self.favorites_frame, text="Favorites", font=customtkinter.CTkFont(weight="bold")).pack(anchor="w", padx=10)
        for fav in self.favorites:
            display_text = f"{fav['name']}" + (f"  [{fav['axis']}]" if fav.get('axis') else "")
            btn = customtkinter.CTkButton(self.favorites_frame, text=display_text, fg_color="transparent", anchor="w", command=lambda f=fav: self.select_from_list(f)); btn.pack(fill="x", padx=5)
        customtkinter.CTkLabel(self.recents_frame, text="Recents", font=customtkinter.CTkFont(weight="bold")).pack(anchor="w", padx=10)
        for rec in self.recents:
            display_text = f"{rec['name']}" + (f"  [{rec['axis']}]" if rec.get('axis') else "")
            btn = customtkinter.CTkButton(self.recents_frame, text=display_text, fg_color="transparent", anchor="w", command=lambda s=rec: self.select_from_list(s)); btn.pack(fill="x", padx=5)

    def update_fav_button_state(self):
        scenario = self.scenario_search_var.get()
        if scenario and any(fav["name"] == scenario for fav in self.favorites): self.fav_button.configure(text="★", fg_color="gold")
        else: self.fav_button.configure(text="☆", fg_color=customtkinter.ThemeManager.theme["CTkButton"]["fg_color"])

    def select_from_list(self, selection):
        if isinstance(selection, dict): self.scenario_search_var.set(selection['name']); self.variable_axis_var.set(selection.get('axis', ''))
        else: self.scenario_search_var.set(selection)
        self.autocomplete_listbox.grid_remove(); self.update_grid()

    def update_grid(self):
        base_scenario = self.scenario_search_var.get()
        if not base_scenario or self.master_df is None: return
        saved_target = self.target_scores_by_scenario.get(base_scenario, "3000")
        self.target_score_var.set(saved_target)
        self.current_family_info = engine.get_scenario_family_info(self.master_df, base_scenario)
        if not self.variable_axis_var.get(): self.variable_axis_var.set("")
        self.build_filters_and_get_data(); self.update_fav_button_state()

    def update_autocomplete(self, *args):
        search_term = self.scenario_search_var.get().lower(); self.update_fav_button_state()
        for widget in self.autocomplete_listbox.winfo_children(): widget.destroy()
        if not search_term: self.autocomplete_listbox.grid_remove(); return
        suggestions = [scen for scen in self.scenario_list if search_term in scen.lower()][:20]
        if suggestions:
            self.autocomplete_listbox.grid()
            for scen in suggestions: btn = customtkinter.CTkButton(self.autocomplete_listbox, text=scen, fg_color="transparent", anchor="w", command=lambda s=scen: self.select_from_list(s)); btn.pack(fill="x")
        else: self.autocomplete_listbox.grid_remove()

    def select_stats_folder(self):
        folder_path = filedialog.askdirectory();
        if folder_path: self.path_entry.delete(0, "end"); self.path_entry.insert(0, folder_path)

    def set_default_path(self):
        path = r"C:\Program Files (x86)\Steam\steamapps\common\FPSAimTrainer\FPSAimTrainer\stats"
        if os.path.exists(path): self.path_entry.insert(0, path)

    def perform_load(self, stats_path):
        df = engine.find_and_process_stats(stats_path); self.after(0, self.on_load_complete, df)

if __name__ == "__main__":
    app = App()
    app.mainloop()