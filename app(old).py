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

customtkinter.set_appearance_mode("System")
customtkinter.set_default_color_theme("blue")

USER_DATA_FILE = "user_data.json"

# --- New Softer Colors for Heatmap ---
COLOR_RED = (120, 47, 47)    # #782f2f
COLOR_YELLOW = (122, 118, 50) # #7a7632
COLOR_GREEN = (54, 107, 54)   # #366b36

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        self.master_df, self.scenario_list, self.results_table, self.current_family_info, self.current_unfiltered_grid_data = None, [], None, None, None
        self.variable_axis_var = customtkinter.StringVar()
        self.fixed_filter_vars = {}
        self.sens_filter_var = customtkinter.StringVar(value="All")
        self.highlight_mode_var = customtkinter.StringVar(value="Performance Drop")
        self.favorites, self.recents = [], []
        self.load_user_data()

        self.title("iyo's Variant Stats Viewer")
        self.geometry("1400x950")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.top_frame = customtkinter.CTkFrame(self, corner_radius=0); self.top_frame.grid(row=0, column=0, sticky="nsew"); self.top_frame.grid_columnconfigure(1, weight=1)
        self.bottom_frame = customtkinter.CTkFrame(self); self.bottom_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10); self.bottom_frame.grid_columnconfigure(0, weight=1); self.bottom_frame.grid_rowconfigure(0, weight=1)
        
        self.select_path_button = customtkinter.CTkButton(self.top_frame, text="Select Stats Folder", command=self.select_stats_folder); self.select_path_button.grid(row=0, column=0, padx=10, pady=10)
        self.path_entry = customtkinter.CTkEntry(self.top_frame, placeholder_text="Path to KovaaK's stats folder..."); self.path_entry.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(0, 10), pady=10)
        self.load_button = customtkinter.CTkButton(self.top_frame, text="Load Stats", font=("Arial", 16, "bold"), height=40, command=self.load_stats_thread); self.load_button.grid(row=1, column=0, columnspan=3, padx=10, pady=(5, 10), sticky="ew")
        self.status_label = customtkinter.CTkLabel(self.top_frame, text="Ready. Select stats folder and click 'Load Stats'."); self.status_label.grid(row=2, column=0, columnspan=3, padx=10, pady=(0, 10), sticky="w")
        self.progress_bar = customtkinter.CTkProgressBar(self.top_frame, mode='indeterminate')
        
        self.search_frame = customtkinter.CTkFrame(self.top_frame); self.search_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=10, pady=(0,10)); self.search_frame.grid_columnconfigure(0, weight=1)
        self.scenario_entry_label = customtkinter.CTkLabel(self.search_frame, text="Search for Base Scenario:"); self.scenario_entry_label.grid(row=0, column=0, padx=10, pady=(5,0), sticky="w")
        self.scenario_search_var = customtkinter.StringVar(); self.scenario_search_var.trace_add("write", self.update_autocomplete)
        self.scenario_entry = customtkinter.CTkEntry(self.search_frame, textvariable=self.scenario_search_var, state="disabled"); self.scenario_entry.grid(row=1, column=0, sticky="ew", padx=10)
        self.fav_button = customtkinter.CTkButton(self.search_frame, text="☆", font=("Arial", 20), width=30, command=self.toggle_favorite); self.fav_button.grid(row=1, column=1, padx=(5,10))
        self.autocomplete_listbox = customtkinter.CTkScrollableFrame(self.search_frame, height=150); self.autocomplete_listbox.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10); self.autocomplete_listbox.grid_remove()
        
        self.user_lists_frame = customtkinter.CTkFrame(self.top_frame); self.user_lists_frame.grid(row=4, column=0, columnspan=3, sticky="ew", padx=10, pady=(0,10)); self.user_lists_frame.grid_columnconfigure((0,1), weight=1)
        self.favorites_frame = customtkinter.CTkFrame(self.user_lists_frame); self.favorites_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.recents_frame = customtkinter.CTkFrame(self.user_lists_frame); self.recents_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.update_user_lists_display()

        self.display_options_frame = customtkinter.CTkFrame(self.top_frame); self.display_options_frame.grid(row=5, column=0, columnspan=3, sticky="ew", padx=10, pady=(0,10)); self.display_options_frame.grid_columnconfigure((0,1), weight=1)
        sens_filter_group = customtkinter.CTkFrame(self.display_options_frame); sens_filter_group.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        customtkinter.CTkLabel(sens_filter_group, text="Sensitivity Filter:").pack(side="left", padx=(10,5), pady=5)
        customtkinter.CTkRadioButton(sens_filter_group, text="All", variable=self.sens_filter_var, value="All", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        customtkinter.CTkRadioButton(sens_filter_group, text="5cm Inc.", variable=self.sens_filter_var, value="5cm", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        customtkinter.CTkRadioButton(sens_filter_group, text="10cm Inc.", variable=self.sens_filter_var, value="10cm", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        
        highlight_group = customtkinter.CTkFrame(self.display_options_frame); highlight_group.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        customtkinter.CTkLabel(highlight_group, text="Highlight Mode:").pack(side="left", padx=(10,5), pady=5)
        customtkinter.CTkRadioButton(highlight_group, text="None", variable=self.highlight_mode_var, value="None", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        customtkinter.CTkRadioButton(highlight_group, text="Perf. Drop", variable=self.highlight_mode_var, value="Performance Drop", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        customtkinter.CTkRadioButton(highlight_group, text="Heatmap", variable=self.highlight_mode_var, value="Heatmap", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)

        self.filters_frame = customtkinter.CTkFrame(self.top_frame); self.filters_frame.grid(row=6, column=0, columnspan=3, sticky="ew", padx=10, pady=(0,10)); self.filters_frame.grid_remove()

        self.set_default_path()
        self.after(100, self.load_stats_thread)

    def on_closing(self):
        if self.results_table: self.results_table.destroy()
        self.destroy()

    def on_display_option_change(self):
        self.save_user_data()
        self.display_grid_data()

    def load_user_data(self):
        if os.path.exists(USER_DATA_FILE):
            try:
                with open(USER_DATA_FILE, 'r') as f: data = json.load(f)
                loaded_favs = data.get("favorites", [])
                self.favorites = [{"name": fav, "axis": ""} if isinstance(fav, str) else fav for fav in loaded_favs]
                self.recents = data.get("recents", [])
                self.sens_filter_var.set(data.get("sens_filter_preference", "All"))
                self.highlight_mode_var.set(data.get("highlight_mode_preference", "Performance Drop"))
            except (json.JSONDecodeError, AttributeError): self.favorites, self.recents = [], []
    
    def save_user_data(self):
        data_to_save = {"favorites": self.favorites, "recents": self.recents, "sens_filter_preference": self.sens_filter_var.get(), "highlight_mode_preference": self.highlight_mode_var.get()}
        with open(USER_DATA_FILE, 'w') as f: json.dump(data_to_save, f, indent=2)

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
        for widget in self.favorites_frame.winfo_children(): widget.destroy()
        for widget in self.recents_frame.winfo_children(): widget.destroy()
        customtkinter.CTkLabel(self.favorites_frame, text="Favorites", font=customtkinter.CTkFont(weight="bold")).pack(anchor="w", padx=10)
        for fav in self.favorites:
            display_text = f"{fav['name']}"
            if fav.get('axis'): display_text += f"  [{fav['axis']}]"
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
        self.autocomplete_listbox.grid_remove(); self.current_family_info = None; self.update_grid()
        
    def update_grid(self):
        base_scenario = self.scenario_search_var.get()
        if not base_scenario or base_scenario not in self.scenario_list: return
        if self.current_family_info is None or not self.current_family_info['Scenario'].iloc[0].startswith(base_scenario):
            self.current_family_info = engine.get_scenario_family_info(self.master_df, base_scenario)
            if not self.variable_axis_var.get(): self.variable_axis_var.set("")
            self.fixed_filter_vars.clear()
        self.build_filters_and_get_data(); self.update_fav_button_state()

    def build_filters_and_get_data(self):
        for widget in self.filters_frame.winfo_children(): widget.destroy()
        if self.current_family_info is None or self.current_family_info.empty: self.filters_frame.grid_remove(); self.display_grid_data(); return
        all_modifiers = defaultdict(set); [all_modifiers[k].add(v) for mod_dict in self.current_family_info['Modifiers'] for k, v in mod_dict.items()]
        if not all_modifiers:
            self.filters_frame.grid_remove(); self.current_unfiltered_grid_data = self.current_family_info[self.current_family_info['Scenario'] == self.scenario_search_var.get()]; self.display_grid_data(); return
        self.filters_frame.grid()
        axis_frame = customtkinter.CTkFrame(self.filters_frame); axis_frame.pack(side="left", fill="x", expand=True, padx=10, pady=5)
        customtkinter.CTkLabel(axis_frame, text="Compare by:").pack(anchor="w", padx=5)
        if not self.variable_axis_var.get() or self.variable_axis_var.get() not in all_modifiers.keys(): self.variable_axis_var.set(list(all_modifiers.keys())[0])
        for key in all_modifiers.keys():
            rb = customtkinter.CTkRadioButton(axis_frame, text=key, variable=self.variable_axis_var, value=key, command=self.build_filters_and_get_data); rb.pack(side="left", padx=5, pady=5)
        filter_frame = customtkinter.CTkFrame(self.filters_frame); filter_frame.pack(side="left", fill="x", expand=True, padx=10, pady=5)
        customtkinter.CTkLabel(filter_frame, text="Pin Modifiers: (Advanced)").pack(anchor="w", padx=5)
        fixed_filters = {}; current_axis = self.variable_axis_var.get()
        for key, values in all_modifiers.items():
            if key == current_axis: continue
            if key not in self.fixed_filter_vars: self.fixed_filter_vars[key] = customtkinter.StringVar(value="None")
            dropdown_var = self.fixed_filter_vars[key]
            dropdown_menu = customtkinter.CTkOptionMenu(filter_frame, variable=dropdown_var, values=["None"] + sorted(list(values)), command=self.build_filters_and_get_data); dropdown_menu.pack(side="left", padx=5, pady=5)
        for key, var in self.fixed_filter_vars.items():
            if key != current_axis and var.get() != "None": fixed_filters[key] = var.get()
        base_scenario = self.scenario_search_var.get()
        self.current_unfiltered_grid_data = engine.analyze_variants(self.current_family_info, variable_axis=current_axis, fixed_filters=fixed_filters, base_scenario=base_scenario)
        self.display_grid_data()

    def display_grid_data(self):
        if self.results_table: self.results_table.destroy()
        if self.current_unfiltered_grid_data is None or self.current_unfiltered_grid_data.empty: return
        grid_data = self.current_unfiltered_grid_data.copy()
        sens_filter = self.sens_filter_var.get()
        if sens_filter != "All":
            increment = 5 if sens_filter == "5cm" else 10; cols_to_keep = ['Scenario', 'BEST Score', 'BEST CM', '% vs Base']
            sens_cols_str = [c for c in grid_data.columns if str(c).replace('.','',1).isdigit()]
            for col in sens_cols_str:
                if float(col) % increment == 0: cols_to_keep.append(col)
            grid_data = grid_data[[c for c in grid_data.columns if c in cols_to_keep]]
        if self.scenario_search_var.get() and self.scenario_search_var.get() not in self.recents: self.add_to_recents(self.scenario_search_var.get())
        base_scenario = self.scenario_search_var.get()
        grid_data = grid_data.fillna('').reset_index(inplace=False)
        if 'index' in grid_data.columns: grid_data = grid_data.drop(columns='index')
        def get_sort_key(scenario_name):
            modifier_str = scenario_name.replace(base_scenario, '').strip(); numbers = re.findall(r'(\d+\.?\d*)', modifier_str)
            if not numbers: return 100
            return float(numbers[-1])
        if 'Scenario' in grid_data.columns:
            grid_data['sort_key'] = grid_data['Scenario'].apply(get_sort_key); grid_data.sort_values(by='sort_key', inplace=True); grid_data.drop(columns='sort_key', inplace=True)
        cols = grid_data.columns.tolist(); summary_cols = ['BEST Score', 'BEST CM', '% vs Base']
        def is_float(val):
            try: float(val); return True
            except (ValueError, TypeError): return False
        sens_cols = sorted([c for c in cols if c not in summary_cols and c != 'Scenario' and is_float(c)], key=float)
        other_cols = [c for c in cols if c not in summary_cols and c != 'Scenario' and not is_float(c)]
        final_col_order = ['Scenario'] + sens_cols + other_cols + summary_cols; final_col_order = [c for c in final_col_order if c in grid_data.columns]
        grid_data = grid_data[final_col_order]
        formatted_columns = [f"{col}cm" if is_float(col) else col for col in grid_data.columns]
        table_values = [formatted_columns] + grid_data.values.tolist()
        self.results_table = CTkTable(self.bottom_frame, values=table_values)
        self.results_table.pack(expand=True, fill="both", padx=5, pady=5)
        if 'Scenario' in final_col_order: self.results_table.edit_column(0, width=350)
        self.apply_highlighting(grid_data)

    def apply_highlighting(self, grid_data):
        mode = self.highlight_mode_var.get()
        if mode == "None": return
        
        # Identify columns that should be highlighted
        perf_drop_cols = [c for c in grid_data.columns if c != 'Scenario' and c != 'BEST CM']
        heatmap_cols = [c for c in grid_data.columns if str(c).replace('.','',1).isdigit()]
        
        values_only = grid_data.values
        for r_idx, row_data in enumerate(values_only):
            if mode == "Performance Drop" and r_idx > 0:
                for c_idx, col_name in enumerate(grid_data.columns):
                    if col_name not in perf_drop_cols: continue
                    try:
                        current_val = float(str(row_data[c_idx]).replace('%', ''))
                        above_val = float(str(values_only[r_idx - 1][c_idx]).replace('%', ''))
                        if current_val < above_val: self.results_table.frame[r_idx + 1, c_idx].configure(fg_color="#592020")
                    except (ValueError, TypeError): continue
            elif mode == "Heatmap":
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

    def get_heatmap_color(self, normalized_value):
        # Interpolates between 3 colors: Red -> Yellow -> Green
        if normalized_value < 0.5:
            # Interpolate between Red and Yellow
            local_norm = normalized_value * 2
            r = int(COLOR_RED[0] * (1 - local_norm) + COLOR_YELLOW[0] * local_norm)
            g = int(COLOR_RED[1] * (1 - local_norm) + COLOR_YELLOW[1] * local_norm)
            b = int(COLOR_RED[2] * (1 - local_norm) + COLOR_YELLOW[2] * local_norm)
        else:
            # Interpolate between Yellow and Green
            local_norm = (normalized_value - 0.5) * 2
            r = int(COLOR_YELLOW[0] * (1 - local_norm) + COLOR_GREEN[0] * local_norm)
            g = int(COLOR_YELLOW[1] * (1 - local_norm) + COLOR_GREEN[1] * local_norm)
            b = int(COLOR_YELLOW[2] * (1 - local_norm) + COLOR_GREEN[2] * local_norm)
        return f"#{r:02x}{g:02x}{b:02x}"

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
        self.progress_bar.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=(0,10)); self.progress_bar.start()
        thread = threading.Thread(target=self.perform_load, args=(stats_path,)); thread.start()
    def perform_load(self, stats_path):
        df = engine.find_and_process_stats(stats_path); self.after(0, self.on_load_complete, df)
    def on_load_complete(self, result_df):
        self.progress_bar.stop(); self.progress_bar.grid_remove()
        if result_df is not None and not result_df.empty:
            self.master_df = result_df; unique_scenarios = self.master_df['Scenario'].unique()
            base_scenarios = {s for s in unique_scenarios if any(s != other and s in other for other in unique_scenarios)}
            all_scenarios = sorted(list(base_scenarios.union(unique_scenarios)))
            self.scenario_list = all_scenarios
            self.status_label.configure(text=f"Success! Loaded {len(self.master_df)} unique combinations. Ready to search.")
            self.scenario_entry.configure(state="normal"); self.load_button.configure(text="Refresh Stats")
        else:
            self.status_label.configure(text="Load complete, but no data was found."); self.master_df = None; self.scenario_list = []
        self.load_button.configure(state="normal"); self.select_path_button.configure(state="normal")

if __name__ == "__main__":
    app = App()
    app.mainloop()
