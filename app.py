# --- START OF MODIFIED FILE app.py ---

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

        self.master_df, self.scenario_list, self.results_table, self.current_family_info, self.current_unfiltered_grid_data = None, [], None, None, None
        self.variable_axis_var = customtkinter.StringVar()
        self.sens_filter_var = customtkinter.StringVar(value="All")
        self.highlight_mode_var = customtkinter.StringVar(value="Performance Drop")
        self.show_decimals_var = customtkinter.StringVar(value="Off")
        # --- NEW: Default changed to 3000 ---
        self.target_score_var = customtkinter.StringVar(value="3000")
        
        # --- NEW: Dictionary to hold per-scenario scores ---
        self.target_scores_by_scenario = {}

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

        self.top_frame = customtkinter.CTkFrame(self, corner_radius=0); self.top_frame.grid(row=0, column=0, sticky="nsew"); self.top_frame.grid_columnconfigure(0, weight=1)
        self.bottom_frame = customtkinter.CTkFrame(self); self.bottom_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10); self.bottom_frame.grid_columnconfigure(0, weight=1); self.bottom_frame.grid_rowconfigure(1, weight=1)

        self.rating_frame = customtkinter.CTkFrame(self.bottom_frame)
        self.rating_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(0, 5))
        self.rating_frame.grid_columnconfigure(0, weight=1)
        self.rating_label = customtkinter.CTkLabel(self.rating_frame, text="Rating: -", font=("Arial", 24, "bold"))
        self.rating_label.grid(row=0, column=0, pady=10)
        self.rating_frame.grid_remove()

        row_counter = 0

        path_frame = customtkinter.CTkFrame(self.top_frame); path_frame.grid(row=row_counter, column=0, sticky="ew", padx=10, pady=(10,0)); row_counter += 1; path_frame.grid_columnconfigure(1, weight=1)
        self.select_path_button = customtkinter.CTkButton(path_frame, text="Select Stats Folder", command=self.select_stats_folder); self.select_path_button.grid(row=0, column=0, padx=(0,10), pady=10)
        self.path_entry = customtkinter.CTkEntry(path_frame, placeholder_text="Path to KovaaK's stats folder..."); self.path_entry.grid(row=0, column=1, sticky="ew", pady=10)
        self.load_button = customtkinter.CTkButton(path_frame, text="Load Stats", font=("Arial", 18, "bold"), height=50, command=self.load_stats_thread)
        self.load_button.grid(row=1, column=0, columnspan=2, pady=(0, 10), sticky="ew")
        self.status_label = customtkinter.CTkLabel(path_frame, text="Ready. Select stats folder and click 'Load Stats'."); self.status_label.grid(row=2, column=0, columnspan=2, pady=(0, 10), sticky="w")
        self.progress_bar = customtkinter.CTkProgressBar(path_frame, mode='indeterminate')

        selection_header, self.selection_content_frame = self._create_collapsible_section("Scenario Selection", "main_selection", row_counter)
        row_counter += 2
        
        self.search_frame = customtkinter.CTkFrame(self.selection_content_frame); self.search_frame.grid(row=0, column=0, sticky="ew", pady=(0,5)); self.search_frame.grid_columnconfigure(0, weight=1)
        self.user_lists_frame = customtkinter.CTkFrame(self.selection_content_frame); self.user_lists_frame.grid(row=1, column=0, sticky="ew"); self.selection_content_frame.grid_columnconfigure(0, weight=1)

        self.scenario_entry_label = customtkinter.CTkLabel(self.search_frame, text="Search for Base Scenario:"); self.scenario_entry_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(5,0))
        self.scenario_search_var = customtkinter.StringVar(); self.scenario_search_var.trace_add("write", self.update_autocomplete)
        self.scenario_entry = customtkinter.CTkEntry(self.search_frame, textvariable=self.scenario_search_var, state="disabled"); self.scenario_entry.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        self.fav_button = customtkinter.CTkButton(self.search_frame, text="☆", font=("Arial", 20), width=30, command=self.toggle_favorite); self.fav_button.grid(row=1, column=1, padx=(0,10), pady=5)
        self.autocomplete_listbox = customtkinter.CTkScrollableFrame(self.search_frame, height=150); self.autocomplete_listbox.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=5); self.autocomplete_listbox.grid_remove()
        
        self.user_lists_frame.grid_columnconfigure((0,1), weight=1)
        self.favorites_frame = customtkinter.CTkFrame(self.user_lists_frame); self.favorites_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.recents_frame = customtkinter.CTkFrame(self.user_lists_frame); self.recents_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.update_user_lists_display()

        analysis_tools_frame = customtkinter.CTkFrame(self.top_frame); analysis_tools_frame.grid(row=row_counter, column=0, sticky="ew", padx=10, pady=5); row_counter += 1
        analysis_tools_frame.grid_columnconfigure(0, weight=1)
        
        display_top_row_frame = customtkinter.CTkFrame(analysis_tools_frame); display_top_row_frame.grid(row=0, column=0, sticky="ew"); display_top_row_frame.grid_columnconfigure((0, 1), weight=1)
        
        sens_filter_group = customtkinter.CTkFrame(display_top_row_frame); sens_filter_group.grid(row=0, column=0, padx=(0,5), pady=5, sticky="ew")
        customtkinter.CTkLabel(sens_filter_group, text="Sensitivity Filter:").pack(side="left", padx=(10,5), pady=5)
        customtkinter.CTkRadioButton(sens_filter_group, text="All", variable=self.sens_filter_var, value="All", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        customtkinter.CTkRadioButton(sens_filter_group, text="5cm Inc.", variable=self.sens_filter_var, value="5cm", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        customtkinter.CTkRadioButton(sens_filter_group, text="10cm Inc.", variable=self.sens_filter_var, value="10cm", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        
        misc_group = customtkinter.CTkFrame(display_top_row_frame); misc_group.grid(row=0, column=1, padx=(5,0), pady=5, sticky="ew")
        customtkinter.CTkSwitch(misc_group, text="Show Decimals", variable=self.show_decimals_var, onvalue="On", offvalue="Off", command=self.on_display_option_change).pack(side="left", padx=10, pady=5)
        self.manage_hidden_button = customtkinter.CTkButton(misc_group, text="Manage Hidden", command=self.open_manage_hidden_window)
        self.manage_hidden_button.pack(side="left", padx=10, pady=5)

        highlight_group = customtkinter.CTkFrame(analysis_tools_frame); highlight_group.grid(row=1, column=0, sticky="ew", pady=(0,5))
        customtkinter.CTkLabel(highlight_group, text="Highlight Mode:").pack(side="left", padx=(10,5), pady=5)
        customtkinter.CTkRadioButton(highlight_group, text="None", variable=self.highlight_mode_var, value="None", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        customtkinter.CTkRadioButton(highlight_group, text="Perf. Drop", variable=self.highlight_mode_var, value="Performance Drop", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        customtkinter.CTkRadioButton(highlight_group, text="Row Heatmap", variable=self.highlight_mode_var, value="Row Heatmap", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        customtkinter.CTkRadioButton(highlight_group, text="Global Heatmap", variable=self.highlight_mode_var, value="Global Heatmap", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        customtkinter.CTkRadioButton(highlight_group, text="Target Score", variable=self.highlight_mode_var, value="Target Score", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        self.target_score_entry = customtkinter.CTkEntry(highlight_group, textvariable=self.target_score_var, width=80)
        self.target_score_entry.pack(side="left", padx=(0,10), pady=5)
        
        # --- NEW: Only bind to the Enter key ---
        self.target_score_entry.bind("<Return>", self.on_display_option_change)
        
        self.filters_frame = customtkinter.CTkFrame(analysis_tools_frame); self.filters_frame.grid(row=2, column=0, sticky="ew", pady=(5,0));
        
        self.set_default_path()
        self.after(100, self.load_stats_thread)
        self.after(200, self._apply_initial_collapse_state)
        self.after(250, self.on_display_option_change)
    
    def _create_collapsible_section(self, title, section_key, row_index):
        header_frame = customtkinter.CTkFrame(self.top_frame)
        header_frame.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(5,0))
        content_frame = customtkinter.CTkFrame(self.top_frame)
        content_frame.grid(row=row_index + 1, column=0, sticky="ew", padx=10, pady=(0, 5))
        toggle_button = customtkinter.CTkButton(header_frame, text="▼", width=30, fg_color="transparent")
        def toggle():
            is_collapsed = not content_frame.winfo_viewable()
            if is_collapsed: content_frame.grid(); toggle_button.configure(text="▼"); self.collapsed_states[section_key] = False
            else: content_frame.grid_remove(); toggle_button.configure(text="▶"); self.collapsed_states[section_key] = True
            self.save_user_data()
        toggle_button.configure(command=toggle)
        toggle_button.pack(side="left")
        header_label = customtkinter.CTkLabel(header_frame, text=title, font=customtkinter.CTkFont(weight="bold"))
        header_label.pack(side="left")
        header_frame.bind("<Button-1>", lambda e: toggle()); header_label.bind("<Button-1>", lambda e: toggle())
        content_frame.toggle_function = toggle
        return header_frame, content_frame

    def _apply_initial_collapse_state(self):
        if self.collapsed_states.get("main_selection", False):
            if self.selection_content_frame.winfo_viewable(): self.selection_content_frame.toggle_function()

    def on_closing(self):
        if self.results_table: self.results_table.destroy()
        self.destroy()

    def on_display_option_change(self, event=None):
        if hasattr(self, 'target_score_entry'):
            if self.highlight_mode_var.get() == "Target Score":
                self.target_score_entry.pack(side="left", padx=(0,10), pady=5)
            else:
                self.target_score_entry.pack_forget()

        self.save_user_data()
        self.display_grid_data()

    def load_user_data(self):
        if os.path.exists(USER_DATA_FILE):
            try:
                with open(USER_DATA_FILE, 'r') as f: data = json.load(f)
                loaded_favs = data.get("favorites", []); self.favorites = [{"name": fav, "axis": ""} if isinstance(fav, str) else fav for fav in loaded_favs]
                self.recents = data.get("recents", [])
                self.sens_filter_var.set(data.get("sens_filter_preference", "All"))
                self.highlight_mode_var.set(data.get("highlight_mode_preference", "Performance Drop"))
                self.show_decimals_var.set(data.get("show_decimals_preference", "Off"))
                # --- NEW: Load the dictionary of target scores ---
                self.target_scores_by_scenario = data.get("target_scores_by_scenario", {})
                self.collapsed_states = data.get("collapsed_states", {})
                self.hidden_scenarios = set(data.get("hidden_scenarios", []))
                self.hidden_cms = set(data.get("hidden_cms", []))
            except (json.JSONDecodeError, AttributeError): 
                self.favorites, self.recents, self.collapsed_states, self.target_scores_by_scenario = [], [], {}, {}
                self.hidden_scenarios, self.hidden_cms = set(), set()
    
    def save_user_data(self):
        # --- NEW: Save the current target score to its scenario ---
        current_scenario = self.scenario_search_var.get()
        if current_scenario:
            self.target_scores_by_scenario[current_scenario] = self.target_score_var.get()

        data_to_save = {
            "favorites": self.favorites, 
            "recents": self.recents, 
            "sens_filter_preference": self.sens_filter_var.get(), 
            "highlight_mode_preference": self.highlight_mode_var.get(), 
            "show_decimals_preference": self.show_decimals_var.get(),
            # --- NEW: Save the entire dictionary ---
            "target_scores_by_scenario": self.target_scores_by_scenario,
            "collapsed_states": self.collapsed_states,
            "hidden_scenarios": list(self.hidden_scenarios),
            "hidden_cms": list(self.hidden_cms)
        }
        with open(USER_DATA_FILE, 'w') as f: json.dump(data_to_save, f, indent=2)
    
    def is_float(self, val):
        try: float(val); return True
        except (ValueError, TypeError): return False

    def display_grid_data(self):
        if self.results_table: self.results_table.destroy()
        if self.current_unfiltered_grid_data is None or self.current_unfiltered_grid_data.empty:
            self.rating_frame.grid_remove()
            return

        self.rating_frame.grid()
        
        grid_data = self.current_unfiltered_grid_data.copy()

        if 'Scenario' in grid_data.columns and self.hidden_scenarios:
            grid_data = grid_data[~grid_data['Scenario'].isin(self.hidden_scenarios)]
        if self.hidden_cms:
            cols_to_drop = [c for c in grid_data.columns if str(c) in self.hidden_cms]
            grid_data.drop(columns=cols_to_drop, inplace=True, errors='ignore')

        if grid_data.empty:
            self.rating_frame.grid_remove()
            return

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
            total_score = numeric_data_rating.sum().sum()
            num_rows = len(grid_data)
            num_cols = len(sens_cols_for_rating)
            possible_slots = num_rows * num_cols
            rating = total_score / possible_slots if possible_slots > 0 else 0
            self.rating_label.configure(text=f"Rating: {round(rating)}")
        else:
            self.rating_label.configure(text="Rating: -")
        
        if self.scenario_search_var.get() and self.scenario_search_var.get() not in self.recents: self.add_to_recents(self.scenario_search_var.get())
        base_scenario = self.scenario_search_var.get()
        grid_data = grid_data.fillna('').reset_index(inplace=False)
        if 'index' in grid_data.columns: grid_data = grid_data.drop(columns='index')
        def get_sort_key(scenario_name):
            modifier_str = scenario_name.replace(base_scenario, '').strip(); numbers = re.findall(r'(\d+\.?\d*)', modifier_str)
            if not numbers: return 100
            return float(numbers[-1])
        if 'Scenario' in grid_data.columns and not grid_data.empty:
            grid_data['sort_key'] = grid_data['Scenario'].apply(get_sort_key); grid_data.sort_values(by='sort_key', inplace=True); grid_data.drop(columns='sort_key', inplace=True)
        
        sens_cols_for_avg = [c for c in grid_data.columns if self.is_float(c)]
        if sens_cols_for_avg:
            numeric_data = grid_data[sens_cols_for_avg].apply(pd.to_numeric, errors='coerce')
            grid_data['AVG'] = numeric_data.mean(axis=1)
        else:
            grid_data['AVG'] = np.nan

        summary_cols_map = {'BEST Score': 'Best', 'BEST CM': 'cm', '% vs Base': '%', 'AVG': 'AVG'}
        grid_data.rename(columns=summary_cols_map, inplace=True)
        cols = grid_data.columns.tolist()

        sens_cols = sorted([c for c in cols if c not in summary_cols_map.values() and c != 'Scenario' and self.is_float(c)], key=float)
        other_cols = [c for c in cols if c not in summary_cols_map.values() and c != 'Scenario' and not self.is_float(c)]
        final_col_order = ['Scenario'] + sens_cols + other_cols + ['AVG', 'Best', 'cm', '%']
        final_col_order = [c for c in final_col_order if c in grid_data.columns]
        grid_data = grid_data[final_col_order]
        
        values = grid_data.values.tolist()
        if self.show_decimals_var.get() == "Off":
            for r_idx, row in enumerate(values):
                for c_idx, cell in enumerate(row):
                    try: values[r_idx][c_idx] = int(float(cell))
                    except (ValueError, TypeError): continue
        
        formatted_columns = [f"{col}cm" if self.is_float(col) else col for col in grid_data.columns]
        table_values = [formatted_columns] + values
        self.results_table = CTkTable(self.bottom_frame, values=table_values)
        self.results_table.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        if 'Scenario' in final_col_order: self.results_table.edit_column(0, width=350)
        
        self.bind_hide_events(table_values)
        self.apply_highlighting(grid_data)

    def apply_highlighting(self, grid_data):
        mode = self.highlight_mode_var.get()
        if mode == "None" or grid_data.empty: return
        
        perf_drop_cols = [c for c in grid_data.columns if c != 'Scenario' and c != 'cm']
        heatmap_cols = [c for c in grid_data.columns if self.is_float(c) or c == 'AVG' or c == 'Best']
        
        values_only = grid_data.values
        
        global_min, global_max = None, None
        if mode == "Global Heatmap":
            all_scores = [float(cell) for row in values_only for c_idx, cell in enumerate(row) if grid_data.columns[c_idx] in heatmap_cols and str(cell).replace('.','',1).isdigit()]
            if all_scores:
                global_min, global_max = min(all_scores), max(all_scores)

        target_score_val = 0
        is_target_mode = mode == "Target Score"
        grid_min_score = 0
        if is_target_mode:
            try:
                target_score_val = float(self.target_score_var.get())
                all_scores_in_grid = [float(cell) for row in values_only for c_idx, cell in enumerate(row) if grid_data.columns[c_idx] in heatmap_cols and self.is_float(cell)]
                if all_scores_in_grid:
                    grid_min_score = min(all_scores_in_grid)
            except (ValueError, TypeError):
                is_target_mode = False
        
        for r_idx, row_data in enumerate(values_only):
            if mode == "Performance Drop" and r_idx > 0:
                for c_idx, col_name in enumerate(grid_data.columns):
                    if col_name not in perf_drop_cols: continue
                    try:
                        current_val = float(str(row_data[c_idx]).replace('%', ''))
                        above_val = float(str(values_only[r_idx - 1][c_idx]).replace('%', ''))
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
                        val = float(row_data[c_idx])
                        norm = (val - min_score) / (max_score - min_score)
                        self.results_table.frame[r_idx + 1, c_idx].configure(fg_color=self.get_heatmap_color(norm))
                    except (ValueError, TypeError): continue
            elif mode == "Global Heatmap" and global_min is not None and global_max is not None and global_min != global_max:
                for c_idx, col_name in enumerate(grid_data.columns):
                    if col_name not in heatmap_cols: continue
                    try:
                        val = float(row_data[c_idx])
                        norm = (val - global_min) / (global_max - global_min)
                        self.results_table.frame[r_idx + 1, c_idx].configure(fg_color=self.get_heatmap_color(norm))
                    except (ValueError, TypeError): continue
            elif is_target_mode:
                for c_idx, col_name in enumerate(grid_data.columns):
                    if col_name not in heatmap_cols: continue
                    try:
                        val = float(row_data[c_idx])
                        if val >= target_score_val:
                            self.results_table.frame[r_idx + 1, c_idx].configure(fg_color="#591e9c")
                        else:
                            denominator = target_score_val - grid_min_score
                            if denominator <= 0: denominator = 1
                            norm = (val - grid_min_score) / denominator
                            self.results_table.frame[r_idx + 1, c_idx].configure(fg_color=self.get_heatmap_color(norm))
                    except (ValueError, TypeError): continue

    def get_heatmap_color(self, normalized_value):
        normalized_value = max(0, min(1, normalized_value))
        COLOR_RED = (120, 47, 47); COLOR_YELLOW = (122, 118, 50); COLOR_GREEN = (54, 107, 54)
        if normalized_value < 0.5:
            local_norm = normalized_value * 2
            r = int(COLOR_RED[0] * (1 - local_norm) + COLOR_YELLOW[0] * local_norm); g = int(COLOR_RED[1] * (1 - local_norm) + COLOR_YELLOW[1] * local_norm); b = int(COLOR_RED[2] * (1 - local_norm) + COLOR_YELLOW[2] * local_norm)
        else:
            local_norm = (normalized_value - 0.5) * 2
            r = int(COLOR_YELLOW[0] * (1 - local_norm) + COLOR_GREEN[0] * local_norm); g = int(COLOR_YELLOW[1] * (1 - local_norm) + COLOR_GREEN[1] * local_norm); b = int(COLOR_YELLOW[2] * (1 - local_norm) + COLOR_GREEN[2] * local_norm)
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
            for widget in tabview.tab(tab_name).winfo_children(): widget.destroy()
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
    def on_load_complete(self, result_df):
        self.progress_bar.stop(); self.progress_bar.grid_remove()
        if result_df is not None and not result_df.empty:
            self.master_df = result_df; unique_scenarios = self.master_df['Scenario'].unique()
            base_scenarios = {s for s in unique_scenarios if any(s != other and s in other for other in unique_scenarios)}
            all_scenarios = sorted(list(base_scenarios.union(unique_scenarios)))
            self.scenario_list = all_scenarios
            self.status_label.configure(text=f"Success! Loaded {len(self.master_df)} unique combinations. Ready to search.")
            self.scenario_entry.configure(state="normal"); self.load_button.configure(text="Refresh Stats (F5)") 
            if self.scenario_search_var.get(): self.update_grid()
        else:
            self.status_label.configure(text="Load complete, but no data was found."); self.master_df = None; self.scenario_list = []
        self.load_button.configure(state="normal"); self.select_path_button.configure(state="normal")
    def toggle_favorite(self):
        scenario = self.scenario_search_var.get()
        if not scenario: return
        fav_entry = next((item for item in self.favorites if item["name"] == scenario), None)
        if fav_entry: self.favorites.remove(fav_entry)
        else: self.favorites.append({"name": scenario, "axis": self.variable_axis_var.get()})
        self.save_user_data(); self.update_user_lists_display(); self.update_fav_button_state()
    def add_to_recents(self, scenario):
        if scenario in self.recents: self.recents.remove(scenario)
        self.recents.insert(0, scenario); self.recents = self.recents[:5]
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
            btn = customtkinter.CTkButton(self.recents_frame, text=rec, fg_color="transparent", anchor="w", command=lambda s=rec: self.select_from_list(s)); btn.pack(fill="x", padx=5)
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
        
        # --- NEW: Load the correct target score for the selected scenario ---
        saved_target = self.target_scores_by_scenario.get(base_scenario, "3000") # Default to 3000
        self.target_score_var.set(saved_target)

        self.current_family_info = engine.get_scenario_family_info(self.master_df, base_scenario)
        if not self.variable_axis_var.get(): self.variable_axis_var.set("")
        self.build_filters_and_get_data(); self.update_fav_button_state()
    def build_filters_and_get_data(self):
        for widget in self.filters_frame.winfo_children(): widget.destroy()
        if self.current_family_info is None or self.current_family_info.empty: self.filters_frame.grid_remove(); self.display_grid_data(); return
        filtered_family_info = self.current_family_info.copy()
        if self.hidden_scenarios: filtered_family_info = filtered_family_info[~filtered_family_info['Scenario'].isin(self.hidden_scenarios)]
        all_modifiers = defaultdict(set); [all_modifiers[k].add(v) for mod_dict in filtered_family_info['Modifiers'] for k, v in mod_dict.items()]
        if not all_modifiers:
            self.filters_frame.grid_remove(); self.current_unfiltered_grid_data = filtered_family_info[filtered_family_info['Scenario'] == self.scenario_search_var.get()]; self.display_grid_data(); return
        self.filters_frame.grid(); customtkinter.CTkLabel(self.filters_frame, text="Compare by:").pack(side="left", padx=(10,5), pady=5)
        if not self.variable_axis_var.get() or self.variable_axis_var.get() not in all_modifiers.keys(): self.variable_axis_var.set(list(all_modifiers.keys())[0])
        for key in all_modifiers.keys():
            customtkinter.CTkRadioButton(self.filters_frame, text=key, variable=self.variable_axis_var, value=key, command=self.build_filters_and_get_data).pack(side="left", padx=5, pady=5)
        self.current_unfiltered_grid_data = engine.analyze_variants(filtered_family_info, variable_axis=self.variable_axis_var.get(), fixed_filters={}, base_scenario=self.scenario_search_var.get()); self.display_grid_data()
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
    def load_stats_thread(self):
        stats_path = self.path_entry.get()
        if not stats_path or not os.path.isdir(stats_path): return
        self.status_label.configure(text="Loading..."); self.load_button.configure(state="disabled"); self.select_path_button.configure(state="disabled")
        self.progress_bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0,10)); self.progress_bar.start()
        thread = threading.Thread(target=self.perform_load, args=(stats_path,)); thread.daemon = True; thread.start()
    def perform_load(self, stats_path):
        df = engine.find_and_process_stats(stats_path); self.after(0, self.on_load_complete, df)

if __name__ == "__main__":
    app = App()
    app.mainloop()