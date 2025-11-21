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
from datetime import timedelta
from pathlib import Path

# Import separated modules
import windows
import utils

customtkinter.set_default_color_theme("blue")

APP_DATA_DIR = Path.home() / '.kovaaks_stats_viewer'
APP_DATA_DIR.mkdir(exist_ok=True)
USER_DATA_FILE = APP_DATA_DIR / "user_data.json"

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.is_first_load = True
        self.all_runs_df = None
        self.scenario_list = []
        self.results_table = None
        
        self.current_family_runs = None
        self.current_filtered_runs = None
        self.current_summary_data = None
        
        self.variable_axis_var = customtkinter.StringVar()
        self.sens_filter_mode_var = customtkinter.StringVar(value="All")
        self.sens_custom_step_var = customtkinter.StringVar(value="3")
        self.sens_specific_list_var = customtkinter.StringVar(value="")
        self.sens_settings_by_scenario = {}
        
        self.grid_display_mode_var = customtkinter.StringVar(value="Personal Best")
        self.highlight_mode_var = customtkinter.StringVar(value="Performance Drop")
        self.show_decimals_var = customtkinter.StringVar(value="Off")
        
        self.cell_height_var = customtkinter.StringVar(value="28")
        self.appearance_mode_var = customtkinter.StringVar(value="System")
        self.font_size_var = customtkinter.StringVar(value="12")
        
        self.target_score_var = customtkinter.StringVar(value="3000")
        self.session_gap_minutes_var = customtkinter.StringVar(value="30")
        
        self.pb_rank_var = customtkinter.StringVar(value="1")
        self.pb_rank_var.trace_add("write", self.schedule_rank_update)
        self.rank_update_job = None
        
        # --- MOVED UP: Initialize defaults before loading ---
        self.last_custom_rank = 3 
        self.hidden_scenarios = set()
        self.hidden_cms_by_scenario = {}
        self.hidden_cms = set()
        self.graph_hide_settings = {}
        self.session_report_geometry = "900x800"
        self.target_scores_by_scenario = {}
        self.format_filter_vars = {}
        self.format_filter_preferences = {}
        self.favorites = []
        self.recents = []
        self.collapsed_states = {}
        # ---------------------------------------------------
        
        self.current_report_window = None
        
        self.tooltip_instances = []
        self.detailed_stats_cache = {}

        self.load_user_data() # Now this overrides the defaults above
        customtkinter.set_appearance_mode(self.appearance_mode_var.get())
        
        self.title("Variant Stats Viewer by iyo & Gemini (Version v1.21)")
        if hasattr(self, 'saved_geometry') and self.saved_geometry:
            self.geometry(self.saved_geometry)
        else:
            self.geometry("1400x950")
            
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.bind("<F5>", lambda event: self.load_stats_thread())
        
        self.top_frame = customtkinter.CTkFrame(self, corner_radius=0)
        self.top_frame.grid(row=0, column=0, sticky="new")
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
    
    def load_user_data(self):
        if os.path.exists(USER_DATA_FILE):
            try:
                with open(USER_DATA_FILE, 'r') as f: data = json.load(f)
                self.saved_geometry = data.get("window_geometry")
                self.appearance_mode_var.set(data.get("appearance_mode", "System"))
                self.favorites = [{"name": fav, "axis": ""} if isinstance(fav, str) else fav for fav in data.get("favorites", [])]
                self.recents = [{"name": rec, "axis": ""} if isinstance(rec, str) else rec for rec in data.get("recents", [])]
                
                self.sens_settings_by_scenario = data.get("sens_settings_by_scenario", {})
                
                self.grid_display_mode_var.set(data.get("grid_display_mode_preference", "Personal Best"))
                self.highlight_mode_var.set(data.get("highlight_mode_preference", "Performance Drop"))
                self.show_decimals_var.set(data.get("show_decimals_preference", "Off"))
                self.cell_height_var.set(str(data.get("cell_height_preference", "28")))
                self.font_size_var.set(str(data.get("font_size_preference", "12")))
                self.session_gap_minutes_var.set(str(data.get("session_gap_minutes", "30")))
                self.target_scores_by_scenario = data.get("target_scores_by_scenario", {})
                self.collapsed_states = data.get("collapsed_states", {})
                
                self.hidden_scenarios = set(data.get("hidden_scenarios", []))
                self.hidden_cms_by_scenario = data.get("hidden_cms_by_scenario", {})
                
                self.format_filter_preferences = data.get("format_filter_preferences", {})
                self.graph_hide_settings = data.get("graph_hide_settings", {})
                self.session_report_geometry = data.get("session_report_geometry", "900x800")
                
                # --- NEW: Load Last Custom Rank ---
                self.last_custom_rank = data.get("last_custom_rank", 3)
                # ----------------------------------

                self.collapsed_states['main_controls'] = False
            except (json.JSONDecodeError, AttributeError): 
                self.favorites,self.recents,self.collapsed_states,self.target_scores_by_scenario,self.format_filter_preferences = [],[],{},{},{}
                self.hidden_scenarios,self.hidden_cms_by_scenario,self.graph_hide_settings = set(),{},{}

    def save_user_data(self):
        current_scenario = self.scenario_search_var.get()
        if current_scenario:
            self.target_scores_by_scenario[current_scenario] = self.target_score_var.get()
            
            self.sens_settings_by_scenario[current_scenario] = {
                "mode": self.sens_filter_mode_var.get(),
                "step": self.sens_custom_step_var.get(),
                "list": self.sens_specific_list_var.get()
            }

            variable_axis = self.variable_axis_var.get()
            if variable_axis:
                unchecked_patterns = [p for p, v in self.format_filter_vars.items() if not v.get()]
                if current_scenario not in self.format_filter_preferences: self.format_filter_preferences[current_scenario] = {}
                if unchecked_patterns: self.format_filter_preferences[current_scenario][variable_axis] = unchecked_patterns
                elif variable_axis in self.format_filter_preferences.get(current_scenario, {}): del self.format_filter_preferences[current_scenario][variable_axis]
                if not self.format_filter_preferences.get(current_scenario): del self.format_filter_preferences[current_scenario]
        
        # --- NEW: Update last_custom_rank based on current UI state ---
        try:
            current_rank_val = int(self.pb_rank_var.get())
            if current_rank_val > 1:
                self.last_custom_rank = current_rank_val
        except ValueError: pass
        # --------------------------------------------------------------

        data_to_save = {
            "window_geometry": self.geometry(),
            "appearance_mode": self.appearance_mode_var.get(),
            "favorites": self.favorites, "recents": self.recents, 
            "sens_settings_by_scenario": self.sens_settings_by_scenario,
            "grid_display_mode_preference": self.grid_display_mode_var.get(),
            "highlight_mode_preference": self.highlight_mode_var.get(), "show_decimals_preference": self.show_decimals_var.get(),
            "cell_height_preference": self.cell_height_var.get(), "font_size_preference": self.font_size_var.get(),
            "session_gap_minutes": self.session_gap_minutes_var.get(),
            "target_scores_by_scenario": self.target_scores_by_scenario, "collapsed_states": self.collapsed_states, 
            "hidden_scenarios": list(self.hidden_scenarios), 
            "hidden_cms_by_scenario": self.hidden_cms_by_scenario, 
            "format_filter_preferences": self.format_filter_preferences, 
            "graph_hide_settings": self.graph_hide_settings,
            "session_report_geometry": self.session_report_geometry,
            
            # --- NEW: Save Key ---
            "last_custom_rank": self.last_custom_rank,
            # ---------------------
        }
        with open(USER_DATA_FILE, 'w') as f: json.dump(data_to_save, f, indent=2)

    def on_cell_click(self, event, scenario_name, sensitivity):
        if self.all_runs_df is None or self.all_runs_df.empty: return
        
        if sensitivity == "ALL":
            self.on_scenario_name_click(event, scenario_name)
            return

        sensitivity = float(sensitivity)
        graph_id = f"{scenario_name}|{sensitivity}"
        if graph_id not in self.graph_hide_settings:
            self.graph_hide_settings[graph_id] = {}
        hide_settings_for_graph = self.graph_hide_settings[graph_id]
        
        history_data = self.all_runs_df[(self.all_runs_df['Scenario'] == scenario_name) & (self.all_runs_df['Sens'] == sensitivity)].copy()
        history_data.sort_values(by='Timestamp', inplace=True)
        if history_data.empty:
            return
        
        history_data['unique_id'] = history_data.apply(lambda row: f"{row['Timestamp'].isoformat()}|{row['Score']}", axis=1)
        title = f"History: {scenario_name} at {sensitivity}cm"
        windows.GraphWindow(self, full_data=history_data, hide_settings=hide_settings_for_graph, save_callback=self.save_user_data, graph_id=graph_id, title=title)
        
    def on_scenario_name_click(self, event, scenario_name):
        if self.all_runs_df is None or self.all_runs_df.empty: return
        
        graph_id = f"{scenario_name}|ALL"
        if graph_id not in self.graph_hide_settings:
            self.graph_hide_settings[graph_id] = {}
        hide_settings_for_graph = self.graph_hide_settings[graph_id]
        
        history_data = self.all_runs_df[self.all_runs_df['Scenario'] == scenario_name].copy()
        history_data.sort_values(by='Timestamp', inplace=True)
        
        if history_data.empty: return
            
        history_data['unique_id'] = history_data.apply(lambda row: f"{row['Timestamp'].isoformat()}|{row['Score']}", axis=1)
        title = f"History: {scenario_name} (All Sensitivities)"
        windows.GraphWindow(self, full_data=history_data, hide_settings=hide_settings_for_graph, save_callback=self.save_user_data, graph_id=graph_id, title=title)
        
    def _build_path_and_load_controls(self):
        self.path_frame = customtkinter.CTkFrame(self.top_frame); self.path_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10,0)); self.path_frame.grid_columnconfigure(1, weight=1)
        self.select_path_button = customtkinter.CTkButton(self.path_frame, text="Select Stats Folder", command=self.select_stats_folder); self.select_path_button.grid(row=0, column=0, padx=(0,10), pady=10)
        self.path_entry = customtkinter.CTkEntry(self.path_frame, placeholder_text="Path to KovaaK's stats folder..."); self.path_entry.grid(row=0, column=1, sticky="ew", pady=10)
        
        action_frame = customtkinter.CTkFrame(self.path_frame, fg_color="transparent"); action_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0,10)); action_frame.grid_columnconfigure(0, weight=1)
        self.load_button = customtkinter.CTkButton(action_frame, text="Load Stats", font=("Arial", 18, "bold"), height=50, command=self.load_stats_thread); self.load_button.grid(row=0, column=0, sticky="ew")
        
        report_buttons_frame = customtkinter.CTkFrame(action_frame, fg_color="transparent")
        report_buttons_frame.grid(row=0, column=1, padx=(10,0))
        self.session_report_button = customtkinter.CTkButton(report_buttons_frame, text="Last Session Report", command=self.open_session_report, state="disabled")
        self.session_report_button.pack(fill="x", pady=(0,2))
        self.session_history_button = customtkinter.CTkButton(report_buttons_frame, text="Session History", command=self.open_session_history, state="disabled")
        self.session_history_button.pack(fill="x", pady=(2,0))
        
        status_frame = customtkinter.CTkFrame(self.path_frame, fg_color="transparent"); status_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.status_label = customtkinter.CTkLabel(status_frame, text="Ready. Select stats folder and click 'Load Stats'.", anchor="w"); self.status_label.pack(side="left", padx=(0,10))
        self.progress_bar = customtkinter.CTkProgressBar(self.path_frame, mode='indeterminate')

    def _build_main_ui_controls(self):
        self.main_controls_header, self.main_controls_content = self._create_collapsible_section("Options & Analysis", "main_controls", 1); self.main_controls_content.grid_columnconfigure(0, weight=1)
        
        selection_content_frame = customtkinter.CTkFrame(self.main_controls_content); selection_content_frame.grid(row=0, column=0, sticky="ew", pady=(0,5)); selection_content_frame.grid_columnconfigure(0, weight=1)
        
        search_frame = customtkinter.CTkFrame(selection_content_frame); search_frame.grid(row=0, column=0, sticky="ew", pady=(0,5))
        search_frame.grid_columnconfigure(1, weight=1)
        
        user_lists_frame = customtkinter.CTkFrame(selection_content_frame); user_lists_frame.grid(row=1, column=0, sticky="ew")
        user_lists_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        self.scenario_entry_label = customtkinter.CTkLabel(search_frame, text="Search for Base Scenario:"); self.scenario_entry_label.grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(5,0))
        self.scenario_search_var = customtkinter.StringVar(); self.scenario_search_var.trace_add("write", self.update_autocomplete)
        
        self.clear_btn = customtkinter.CTkButton(search_frame, text="✕", width=30, fg_color=("gray75", "gray30"), command=self.clear_search); self.clear_btn.grid(row=1, column=0, padx=(10, 5), pady=5)
        self.scenario_entry = customtkinter.CTkEntry(search_frame, textvariable=self.scenario_search_var, state="disabled"); self.scenario_entry.grid(row=1, column=1, sticky="ew", padx=(0, 5), pady=5)
        self.fav_button = customtkinter.CTkButton(search_frame, text="☆", font=("Arial", 20), width=30, command=self.toggle_favorite); self.fav_button.grid(row=1, column=2, padx=(0,10), pady=5)
        
        self.autocomplete_listbox = customtkinter.CTkScrollableFrame(search_frame, height=150); self.autocomplete_listbox.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=5); self.autocomplete_listbox.grid_remove()
        
        self.favorites_frame = customtkinter.CTkFrame(user_lists_frame); self.favorites_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.recents_frame = customtkinter.CTkFrame(user_lists_frame); self.recents_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.recently_played_frame = customtkinter.CTkScrollableFrame(user_lists_frame); self.recently_played_frame.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)
        self.update_user_lists_display()
        
        display_top_row_frame = customtkinter.CTkFrame(self.main_controls_content); display_top_row_frame.grid(row=1, column=0, sticky="ew"); 
        display_top_row_frame.grid_columnconfigure((0, 1), weight=1, uniform="group1")
        
        session_group = customtkinter.CTkFrame(display_top_row_frame); session_group.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="ew")
        customtkinter.CTkLabel(session_group, text="Session Gap (min):").pack(side="left", padx=(10, 5));
        customtkinter.CTkEntry(session_group, textvariable=self.session_gap_minutes_var, width=50).pack(side="left")
        customtkinter.CTkLabel(session_group, text="(Requires Refresh)", font=customtkinter.CTkFont(size=10, slant="italic")).pack(side="left", padx=(5,10));
        
        misc_group = customtkinter.CTkFrame(display_top_row_frame); misc_group.grid(row=0, column=1, padx=(5,0), pady=5, sticky="ew")
        misc_group.grid_columnconfigure(0, weight=1)
        top_misc_frame = customtkinter.CTkFrame(misc_group, fg_color="transparent")
        top_misc_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        theme_frame = customtkinter.CTkFrame(top_misc_frame, fg_color="transparent")
        theme_frame.pack(side="left", padx=(0,10))
        customtkinter.CTkLabel(theme_frame, text="Theme:").pack(side="left", padx=(0,5))
        customtkinter.CTkOptionMenu(theme_frame, variable=self.appearance_mode_var, values=["System", "Dark", "Light"], command=self.on_appearance_mode_change, width=90).pack(side="left")
        customtkinter.CTkSwitch(top_misc_frame, text="Show Decimals", variable=self.show_decimals_var, onvalue="On", offvalue="Off", command=self.on_display_option_change).pack(side="left", padx=(10,0))
        customtkinter.CTkButton(top_misc_frame, text="Manage Hidden", command=self.open_manage_hidden_window).pack(side="right")
        bottom_misc_frame = customtkinter.CTkFrame(misc_group, fg_color="transparent")
        bottom_misc_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0,5))
        customtkinter.CTkLabel(bottom_misc_frame, text="Font Size:").pack(side="left")
        font_size_entry = customtkinter.CTkEntry(bottom_misc_frame, textvariable=self.font_size_var, width=40)
        font_size_entry.pack(side="left", padx=(0,10))
        customtkinter.CTkLabel(bottom_misc_frame, text="Cell H:").pack(side="left")
        cell_height_entry = customtkinter.CTkEntry(bottom_misc_frame, textvariable=self.cell_height_var, width=40)
        cell_height_entry.pack(side="left")
        font_size_entry.bind("<Return>", self.on_display_option_change)
        cell_height_entry.bind("<Return>", self.on_display_option_change)

        self.filters_frame = customtkinter.CTkFrame(self.main_controls_content); self.filters_frame.grid(row=2, column=0, sticky="ew", pady=(5,0)); self.format_filter_frame = customtkinter.CTkFrame(self.main_controls_content); self.format_filter_frame.grid(row=3, column=0, sticky="ew", pady=(0,5))
        
        analysis_modes_frame = customtkinter.CTkFrame(self.top_frame)
        analysis_modes_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(5,5))
        analysis_modes_frame.grid_columnconfigure((0, 1, 2), weight=1) 

        self.top_frame.grid_rowconfigure(4, weight=1)

        sens_filter_group = customtkinter.CTkFrame(analysis_modes_frame)
        sens_filter_group.grid(row=0, column=0, sticky="ew", padx=(0,5))
        customtkinter.CTkLabel(sens_filter_group, text="Sens Filter:").pack(side="left", padx=(10,5), pady=5)
        self.sens_filter_menu = customtkinter.CTkOptionMenu(sens_filter_group, variable=self.sens_filter_mode_var, values=["All", "2cm Step", "3cm Step", "5cm Step", "10cm Step", "Custom Step", "Specific List"], width=110, command=self.on_display_option_change)
        self.sens_filter_menu.pack(side="left", padx=5, pady=5)
        self.sens_custom_step_entry = customtkinter.CTkEntry(sens_filter_group, textvariable=self.sens_custom_step_var, width=40, placeholder_text="3")
        self.sens_custom_step_entry.bind("<Return>", self.on_display_option_change)
        self.sens_specific_list_entry = customtkinter.CTkEntry(sens_filter_group, textvariable=self.sens_specific_list_var, width=120, placeholder_text="34.6, 43.3...")
        self.sens_specific_list_entry.bind("<Return>", self.on_display_option_change)

        grid_mode_frame = customtkinter.CTkFrame(analysis_modes_frame); grid_mode_frame.grid(row=0, column=1, sticky="ew", padx=5)
        customtkinter.CTkLabel(grid_mode_frame, text="Grid Mode:").pack(side="left", padx=(10,5), pady=5)
        
        self.pb_rank_frame = customtkinter.CTkFrame(grid_mode_frame, fg_color="transparent")
        self.pb_rank_frame.pack(side="left", padx=(0, 5))
        customtkinter.CTkLabel(self.pb_rank_frame, text="PB #:").pack(side="left", padx=(0,2))
        
        self.rank_toggle_btn = customtkinter.CTkButton(self.pb_rank_frame, text="1⇄N", width=40, height=20, fg_color=("gray70", "gray30"), command=self.toggle_pb_rank)
        self.rank_toggle_btn.pack(side="left", padx=3)

        btn_minus = customtkinter.CTkButton(self.pb_rank_frame, text="-", width=20, height=20, command=lambda: self.change_pb_rank(-1))
        btn_minus.pack(side="left", padx=2)
        entry_rank = customtkinter.CTkEntry(self.pb_rank_frame, textvariable=self.pb_rank_var, width=30, height=20)
        entry_rank.pack(side="left", padx=2)
        entry_rank.bind("<Return>", lambda e: self.on_display_option_change())
        btn_plus = customtkinter.CTkButton(self.pb_rank_frame, text="+", width=20, height=20, command=lambda: self.change_pb_rank(1))
        btn_plus.pack(side="left", padx=2)

        modes = ["Personal Best", "Average Score", "Play Count"]
        for mode in modes:
            customtkinter.CTkRadioButton(grid_mode_frame, text=mode, variable=self.grid_display_mode_var, value=mode, command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        
        highlight_group = customtkinter.CTkFrame(analysis_modes_frame); highlight_group.grid(row=0, column=2, sticky="ew", padx=(5,0))
        customtkinter.CTkLabel(highlight_group, text="Highlight:").pack(side="left", padx=(10,5), pady=5)
        h_modes = {"None": "None", "Perf. Drop": "Performance Drop", "Row Heatmap": "Row Heatmap", "Global Heatmap": "Global Heatmap", "Target": "Target Score"}
        for text, val in h_modes.items():
             customtkinter.CTkRadioButton(highlight_group, text=text, variable=self.highlight_mode_var, value=val, command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        self.target_score_entry = customtkinter.CTkEntry(highlight_group, textvariable=self.target_score_var, width=80); self.target_score_entry.pack(side="left", padx=(0,10), pady=5); self.target_score_entry.bind("<Return>", self.on_display_option_change)
        
        self._apply_initial_collapse_state(); self.on_display_option_change()

    def clear_search(self):
        self.scenario_search_var.set("")
        self.scenario_entry.focus()

    def schedule_rank_update(self, *args):
        if self.rank_update_job: self.after_cancel(self.rank_update_job)
        self.rank_update_job = self.after(600, self.perform_rank_update)

    def perform_rank_update(self):
        self.rank_update_job = None
        try:
            int(self.pb_rank_var.get())
            self.on_display_option_change()
        except ValueError: pass

    def toggle_pb_rank(self):
        try: current = int(self.pb_rank_var.get())
        except ValueError: current = 1
        if current == 1: self.pb_rank_var.set(str(self.last_custom_rank))
        else:
            self.last_custom_rank = current
            self.pb_rank_var.set("1")
        self.on_display_option_change()

    def change_pb_rank(self, delta):
        try:
            val_str = self.pb_rank_var.get()
            current = int(val_str) if val_str else 1
        except ValueError: current = 1
        new_val = max(1, current + delta)
        self.pb_rank_var.set(str(new_val))
        if self.rank_update_job: self.after_cancel(self.rank_update_job)
        self.on_display_option_change()

    def load_stats_thread(self, callback=None):
        stats_path = self.path_entry.get()
        if not stats_path or not os.path.isdir(stats_path): return
        self.status_label.configure(text="Loading stats, please wait...")
        self.load_button.configure(state="disabled")
        self.select_path_button.configure(state="disabled")
        self.progress_bar.grid(row=4, column=0, columnspan=2, sticky="ew", padx=10, pady=(0,10))
        self.progress_bar.start()
        
        thread = threading.Thread(target=self.perform_load, args=(stats_path, callback))
        thread.daemon = True
        thread.start()

    def perform_load(self, stats_path, callback=None):
        try: gap_minutes = int(self.session_gap_minutes_var.get())
        except (ValueError, TypeError): gap_minutes = 30
        all_runs_df = engine.find_and_process_stats(stats_path, session_gap_minutes=gap_minutes)
        self.after(0, self.on_load_complete, all_runs_df, callback)

    def on_load_complete(self, all_runs_df, callback=None):
        self.progress_bar.grid_remove()
        if not hasattr(self, 'main_controls_content'): self._build_main_ui_controls()
        
        if all_runs_df is not None and not all_runs_df.empty and 'Duration' in all_runs_df.columns:
            self.all_runs_df = all_runs_df
            unique_scenarios = self.all_runs_df['Scenario'].unique()
            self.scenario_list = sorted(list(unique_scenarios))
            self.update_user_lists_display()
            self.status_label.configure(text=f"Loaded {len(self.all_runs_df)} total runs. Ready to search.")
            self.scenario_entry.configure(state="normal")
            self.session_report_button.configure(state="normal")
            self.session_history_button.configure(state="normal")
            self.load_button.configure(text="Refresh Stats (F5)") 
            if self.is_first_load:
                self.is_first_load = False 
                if self.recents:
                    last_viewed = self.recents[0]
                    if last_viewed["name"] in self.scenario_list:
                        self.after(50, self.select_from_list, last_viewed)
                        if not self.main_controls_content.winfo_viewable(): self.main_controls_content.toggle_function()
            else: 
                self.update_grid()

            if self.current_report_window and self.current_report_window.winfo_exists():
                try:
                    # Re-calculate data for the specific session ID the window is viewing
                    sid = self.current_report_window.session_id
                    data = self._generate_session_payload(sid)
                    if data:
                        self.current_report_window.update_content(*data)
                except Exception as e:
                    print(f"Error refreshing report window: {e}")


            if callback: callback()
        else:
            if all_runs_df is None: self.status_label.configure(text="Load failed or no data found.")
            else: self.status_label.configure(text="Data loaded, but is missing 'Duration'. Please Refresh Stats (F5).")
            self.all_runs_df, self.scenario_list = None, []
            self.session_report_button.configure(state="disabled")
            self.session_history_button.configure(state="disabled")
        self.load_button.configure(state="normal"); self.select_path_button.configure(state="normal")

    def _create_collapsible_section(self, title, section_key, row_index):
        header_frame = customtkinter.CTkFrame(self.top_frame, fg_color=("gray85", "gray20"), corner_radius=6); header_frame.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(5, 1))
        content_frame = customtkinter.CTkFrame(self.top_frame); content_frame.grid(row=row_index + 1, column=0, sticky="ew", padx=10, pady=(0, 5))
        theme_fg_color = customtkinter.ThemeManager.theme["CTkButton"]["fg_color"]; theme_hover_color = customtkinter.ThemeManager.theme["CTkButton"]["hover_color"]
        toggle_button = customtkinter.CTkButton(header_frame, text="▼", width=32, height=32, font=customtkinter.CTkFont(size=22, weight="bold"), fg_color=theme_fg_color, hover_color=theme_hover_color)
        def toggle():
            is_collapsed = not content_frame.winfo_viewable()
            if is_collapsed: content_frame.grid(); toggle_button.configure(text="▼"); self.collapsed_states[section_key] = False
            else: content_frame.grid_remove(); toggle_button.configure(text="▶"); self.collapsed_states[section_key] = True
            self.save_user_data()
        toggle_button.configure(command=toggle); toggle_button.pack(side="left", padx=(8, 0))
        header_label = customtkinter.CTkLabel(header_frame, text=title, font=customtkinter.CTkFont(weight="bold")); header_label.pack(side="left", padx=15, pady=10)
        header_frame.bind("<Button-1>", lambda e: toggle()); header_label.bind("<Button-1>", lambda e: toggle())
        header_frame.configure(cursor="hand2"); header_label.configure(cursor="hand2"); toggle_button.configure(cursor="hand2")
        content_frame.toggle_function = toggle
        return header_frame, content_frame
        
    def _apply_initial_collapse_state(self):
        if self.collapsed_states.get("main_controls", False):
            if hasattr(self, 'main_controls_content') and self.main_controls_content.winfo_viewable(): self.main_controls_content.toggle_function()
            
    def on_closing(self):
        self.save_user_data()
        if self.results_table: self.results_table.destroy()
        self.destroy()
        
    def on_display_option_change(self, event=None):
        if hasattr(self, 'target_score_entry'):
            if self.highlight_mode_var.get() == "Target Score": self.target_score_entry.pack(side="left", padx=(0,10), pady=5)
            else: self.target_score_entry.pack_forget()
        self.save_user_data(); self.display_grid_data()

    def on_appearance_mode_change(self, new_mode):
        customtkinter.set_appearance_mode(new_mode)
        for child in self.winfo_children():
            if isinstance(child, windows.GraphWindow):
                child.redraw_plot()
        self.save_user_data(); self.display_grid_data()
        
    def is_float(self, val):
        try: float(val); return True
        except (ValueError, TypeError): return False
        
    def _apply_format_filter(self):
        self.save_user_data()
        variable_axis = self.variable_axis_var.get()
        pattern_filter = {}
        selected_patterns = [p for p, v in self.format_filter_vars.items() if v.get()]
        if selected_patterns: pattern_filter[variable_axis] = selected_patterns
        
        df_to_process = self.current_family_runs
        if self.hidden_scenarios and df_to_process is not None:
            df_to_process = df_to_process[~df_to_process['Scenario'].isin(self.hidden_scenarios)]

        filtered_rows = []
        base_scenario = self.scenario_search_var.get()

        if variable_axis:
            for _, row in df_to_process.iterrows():
                modifiers, is_base_scenario = row['Modifiers'], row['Scenario'] == base_scenario
                if not is_base_scenario and variable_axis not in modifiers: continue
                if not is_base_scenario and not modifiers: continue
                if pattern_filter and variable_axis in pattern_filter and not is_base_scenario:
                    if modifiers[variable_axis][1] not in pattern_filter[variable_axis]: continue
                
                fixed_filters = {} 
                temp_modifiers_for_check = {k: v[0] for k, v in modifiers.items()}
                allowed_keys = set(fixed_filters.keys()) | {variable_axis}
                if not set(temp_modifiers_for_check.keys()).issubset(allowed_keys): continue
                match = all(temp_modifiers_for_check.get(key) == value for key, value in fixed_filters.items())
                if match: filtered_rows.append(row)
        else:
            filtered_rows = [row for _, row in df_to_process.iterrows()]

        if not filtered_rows:
            self.current_filtered_runs = None
            self.current_summary_data = pd.DataFrame()
        else:
            self.current_filtered_runs = pd.DataFrame(filtered_rows)
            self.current_summary_data = self.current_filtered_runs.groupby(['Scenario', 'Sens']).agg(
                PB_Score=('Score', 'max'),
                Avg_Score=('Score', 'mean'),
                Play_Count=('Score', 'size')
            ).reset_index()

        self.display_grid_data()
        
    def build_filters_and_get_data(self):
        for widget in self.filters_frame.winfo_children(): widget.destroy()
        for widget in self.format_filter_frame.winfo_children(): widget.destroy()
        self.format_filter_frame.grid_remove(); self.format_filter_vars = {}
        
        if self.current_family_runs is None or self.current_family_runs.empty:
            self.filters_frame.grid_remove()
            self.current_summary_data = pd.DataFrame()
            self.display_grid_data()
            return

        filtered_family_info = self.current_family_runs.copy()
        if self.hidden_scenarios: filtered_family_info = filtered_family_info[~filtered_family_info['Scenario'].isin(self.hidden_scenarios)]
        
        all_modifiers = defaultdict(set)
        for mod_dict in filtered_family_info['Modifiers']:
            if mod_dict: 
                for k, v_tuple in mod_dict.items(): all_modifiers[k].add(v_tuple)
            
        if not all_modifiers:
            self.filters_frame.grid_remove()
            self.variable_axis_var.set("")
            self._apply_format_filter()
            return

        self.filters_frame.grid(); customtkinter.CTkLabel(self.filters_frame, text="Compare by:").pack(side="left", padx=(10,5), pady=5)
        preferred_axis = self.variable_axis_var.get()
        if not preferred_axis or preferred_axis not in all_modifiers.keys(): self.variable_axis_var.set(list(all_modifiers.keys())[0])
        
        for key in sorted(list(all_modifiers.keys())):
            customtkinter.CTkRadioButton(self.filters_frame, text=key, variable=self.variable_axis_var, value=key, command=self.build_filters_and_get_data).pack(side="left", padx=5, pady=5)
        
        patterns_found = set(); variable_axis = self.variable_axis_var.get(); base_scenario = self.scenario_search_var.get()
        if variable_axis in all_modifiers:
            for value_tuple in all_modifiers[variable_axis]: patterns_found.add(value_tuple[1])
            
        if len(patterns_found) > 1:
            self.format_filter_frame.grid(); customtkinter.CTkLabel(self.format_filter_frame, text="Filter Format:").pack(side="left", padx=(10,5), pady=5)
            def get_pattern_label(pattern_key):
                if pattern_key == 'word_value': return f"{variable_axis} #"
                if pattern_key == 'value_word': return f"# {variable_axis}"
                return "Standalone"
            scenario_prefs = self.format_filter_preferences.get(base_scenario, {}); unchecked_for_this_axis = scenario_prefs.get(variable_axis, [])
            for pattern in sorted(list(patterns_found)):
                is_checked = pattern not in unchecked_for_this_axis
                var = customtkinter.BooleanVar(value=is_checked); self.format_filter_vars[pattern] = var
                customtkinter.CTkCheckBox(self.format_filter_frame, text=get_pattern_label(pattern), variable=var, command=self._apply_format_filter).pack(side="left", padx=5, pady=5)
        
        self._apply_format_filter()
        
    def display_grid_data(self):
        for tip in self.tooltip_instances:
            tip.widget.unbind("<Enter>")
            tip.widget.unbind("<Leave>")
            tip.widget.unbind("<ButtonPress>")
        self.tooltip_instances = []

        if self.results_table: self.results_table.destroy()
        if self.current_summary_data is None or self.current_summary_data.empty:
            self.rating_frame.grid_remove()
            return
            
        self.rating_frame.grid()
        summary_data = self.current_summary_data.copy()

        try: cell_height = int(self.cell_height_var.get())
        except (ValueError, TypeError): cell_height = 28
        try: font_size = int(self.font_size_var.get())
        except (ValueError, TypeError): font_size = 12

        display_mode = self.grid_display_mode_var.get()
        
        if display_mode == "Personal Best":
            children = self.pb_rank_frame.master.winfo_children()
            if children: self.pb_rank_frame.pack(side="left", padx=(0, 5), after=children[0])
            else: self.pb_rank_frame.pack(side="left", padx=(0, 5))
        else:
            self.pb_rank_frame.pack_forget()

        target_rank = 1
        if display_mode == "Personal Best":
            try: target_rank = int(self.pb_rank_var.get())
            except ValueError: target_rank = 1
        
        if display_mode == "Personal Best" and target_rank > 1 and self.current_filtered_runs is not None:
            def get_nth_score(group):
                if len(group) < target_rank: return np.nan
                return group.nlargest(target_rank).iloc[-1]
            nth_scores = self.current_filtered_runs.groupby(['Scenario', 'Sens'])['Score'].apply(get_nth_score).reset_index()
            nth_scores.rename(columns={'Score': 'PB_Score'}, inplace=True)
            display_data_source = nth_scores
        else:
            display_data_source = summary_data

        value_map = {"Personal Best": "PB_Score", "Average Score": "Avg_Score", "Play Count": "Play_Count"}
        display_value_col = value_map[display_mode]
        highlight_value_col = "Avg_Score" if display_mode == "Average Score" else "PB_Score"

        display_df = display_data_source.pivot_table(index='Scenario', columns='Sens', values=display_value_col).fillna(np.nan)
        
        if display_mode == "Personal Best" and target_rank > 1:
             highlight_df = display_data_source.pivot_table(index='Scenario', columns='Sens', values='PB_Score').fillna(np.nan)
        else:
             highlight_df = summary_data.pivot_table(index='Scenario', columns='Sens', values=highlight_value_col).fillna(np.nan)

        stats_source_df = display_data_source.pivot_table(index='Scenario', columns='Sens', values='PB_Score').fillna(np.nan)

        all_sens_cols = [c for c in display_df.columns if self.is_float(c)]
        valid_sens_cols = []
        base_scenario = self.scenario_search_var.get()
        current_hidden_list = self.hidden_cms_by_scenario.get(base_scenario, [])
        visible_cols = [c for c in all_sens_cols if str(c) not in current_hidden_list]

        sens_mode = self.sens_filter_mode_var.get()
        self.sens_custom_step_entry.pack_forget()
        self.sens_specific_list_entry.pack_forget()
        if sens_mode == "Custom Step": self.sens_custom_step_entry.pack(side="left", padx=5)
        elif sens_mode == "Specific List": self.sens_specific_list_entry.pack(side="left", padx=5)

        if sens_mode == "All": valid_sens_cols = visible_cols
        elif sens_mode == "Specific List":
            try:
                raw_text = self.sens_specific_list_var.get()
                target_floats = [float(x.strip()) for x in raw_text.split(',') if x.strip()]
                for col_s in visible_cols:
                    col_f = float(col_s)
                    if any(abs(col_f - t) < 0.01 for t in target_floats): valid_sens_cols.append(col_s)
            except ValueError: valid_sens_cols = visible_cols
        else:
            try:
                if sens_mode == "Custom Step": step = float(self.sens_custom_step_var.get())
                else: step = float(sens_mode.split('cm')[0])
                if step > 0:
                    for col_s in visible_cols:
                        col_f = float(col_s)
                        if abs(col_f % step) < 0.05 or abs((col_f % step) - step) < 0.05: valid_sens_cols.append(col_s)
            except ValueError: valid_sens_cols = visible_cols

        display_df = display_df[valid_sens_cols]
        highlight_df = highlight_df[valid_sens_cols]
        stats_source_df = stats_source_df[valid_sens_cols]

        if display_df.empty: self.rating_frame.grid_remove(); return

        stats_source_df['Best'] = stats_source_df.max(axis=1)
        stats_source_df['cm'] = stats_source_df[valid_sens_cols].idxmax(axis=1)
        base_pb_score = stats_source_df.loc[base_scenario, 'Best'] if base_scenario in stats_source_df.index else 1.0
        if pd.isna(base_pb_score) or base_pb_score == 0: base_pb_score = 1.0
        stats_source_df['%'] = (stats_source_df['Best'] / base_pb_score * 100)
        grid_data = display_df.join(stats_source_df[['Best', 'cm', '%']])

        if valid_sens_cols and not grid_data.empty and display_mode != "Play Count":
            numeric_data_rating = grid_data[valid_sens_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
            rating = numeric_data_rating.mean().mean()
            self.rating_label.configure(text=f"Rating: {round(rating)}")
        else: self.rating_label.configure(text="Rating: -")

        avg_row_series = None
        if valid_sens_cols and not stats_source_df.empty:
            column_averages = stats_source_df[valid_sens_cols].apply(pd.to_numeric, errors='coerce').mean()
            avg_row_series = pd.Series(column_averages, name="-- Averages --")
            avg_of_avgs = avg_row_series.mean()
            best_avg_score = avg_row_series.max()
            best_avg_cm = avg_row_series.idxmax()
            percent_vs_base = (best_avg_score / base_pb_score * 100)
            avg_row_series['AVG'] = avg_of_avgs
            avg_row_series['Best'] = best_avg_score
            avg_row_series['cm'] = best_avg_cm
            avg_row_series['%'] = percent_vs_base
            avg_row_series['Scenario'] = "-- Averages --"

        grid_data.reset_index(inplace=True)
        def get_sort_key(scenario_name):
            if scenario_name == base_scenario: return 100.0
            modifier_str = scenario_name.replace(base_scenario, '').strip()
            numbers = re.findall(r'(\d+\.?\d*)', modifier_str)
            return float(numbers[-1]) if numbers else 999.0
        grid_data['sort_key'] = grid_data['Scenario'].apply(get_sort_key); grid_data.sort_values(by='sort_key', inplace=True); grid_data.drop(columns='sort_key', inplace=True)
        
        if valid_sens_cols: grid_data['AVG'] = grid_data[valid_sens_cols].apply(pd.to_numeric, errors='coerce').mean(axis=1)
        else: grid_data['AVG'] = np.nan
        
        if avg_row_series is not None:
             grid_data = pd.concat([avg_row_series.to_frame().T, grid_data], ignore_index=True)
        
        grid_data = grid_data.fillna('')
        cols = grid_data.columns.tolist()
        summary_cols = ['AVG', 'Best', 'cm', '%']
        sens_cols_sorted = sorted([c for c in cols if self.is_float(c)], key=float)
        final_col_order = ['Scenario'] + sens_cols_sorted + summary_cols
        final_col_order = [c for c in final_col_order if c in grid_data.columns]
        grid_data = grid_data[final_col_order]
        
        values = grid_data.values.tolist()
        if self.show_decimals_var.get() == "Off":
            percent_col_idx = grid_data.columns.get_loc('%') if '%' in grid_data.columns else -1
            for r_idx, row in enumerate(values):
                for c_idx, cell in enumerate(row):
                    if c_idx == percent_col_idx and isinstance(cell, (float, int)):
                         values[r_idx][c_idx] = f"{round(cell)}%"
                    else:
                        try: values[r_idx][c_idx] = int(round(float(cell)))
                        except (ValueError, TypeError): continue
        
        formatted_columns = [f"{col}cm" if self.is_float(col) else col for col in grid_data.columns]
        table_values = [formatted_columns] + values

        self.detailed_stats_cache = {}
        base_df_for_stats = self.current_filtered_runs if self.current_filtered_runs is not None else self.current_family_runs
        if base_df_for_stats is not None:
            for row in grid_data.itertuples(index=False):
                scenario_name = getattr(row, 'Scenario', None)
                if not scenario_name or scenario_name == '-- Averages --': continue
                
                row_runs_df = base_df_for_stats[base_df_for_stats['Scenario'] == scenario_name]
                self.detailed_stats_cache[(scenario_name, "ALL")] = engine.calculate_detailed_stats(row_runs_df)
                
                for col_name in grid_data.columns:
                    if self.is_float(col_name):
                        cell_runs_df = row_runs_df[row_runs_df['Sens'] == float(col_name)]
                        self.detailed_stats_cache[(scenario_name, col_name)] = engine.calculate_detailed_stats(cell_runs_df)

        self.results_table = CTkTable(self.bottom_frame, values=table_values, 
                                      header_color=("gray80", "gray25"),
                                      font=("Arial", font_size))
        self.results_table.grid(row=1, column=0, sticky="new", padx=5, pady=5)

        for r in range(self.results_table.rows):
            for c in range(self.results_table.columns):
                cell = self.results_table.frame.get((r, c))
                if cell: cell.configure(height=cell_height)

        if 'Scenario' in final_col_order: self.results_table.edit_column(0, width=350)
        
        self.bind_graph_events(grid_data)
        self.bind_hide_events(table_values)
        self.bind_tooltips(grid_data)
        self.apply_highlighting(highlight_df, grid_data)

    def apply_highlighting(self, highlight_df, display_df):
        mode = self.highlight_mode_var.get()
        if mode == "None" or highlight_df.empty: return
        
        highlight_df = highlight_df.reindex(index=display_df['Scenario'].values).fillna(np.nan)
        sens_cols = [c for c in highlight_df.columns if self.is_float(c)]
        
        if sens_cols:
            highlight_df['Best'] = highlight_df[sens_cols].max(axis=1)
            highlight_df['AVG'] = highlight_df[sens_cols].mean(axis=1)
        else:
            highlight_df['Best'] = np.nan
            highlight_df['AVG'] = np.nan

        heatmap_cols = sens_cols + ['Best', 'AVG']
            
        is_avg_row_present = '-- Averages --' in display_df['Scenario'].values
        if is_avg_row_present:
            avg_row_data = display_df[display_df['Scenario'] == '-- Averages --']
            if not avg_row_data.empty:
                data_rows = highlight_df[highlight_df.index != '-- Averages --']
                highlight_avg_row = data_rows[heatmap_cols].mean()
                highlight_df.loc['-- Averages --', heatmap_cols] = highlight_avg_row

        perf_drop_cols = heatmap_cols
        values_only, global_min, global_max = highlight_df.values, None, None
        
        if mode == "Global Heatmap":
            data_rows = highlight_df[highlight_df.index != '-- Averages --']
            all_scores = data_rows[sens_cols].to_numpy().flatten()
            all_scores = all_scores[~np.isnan(all_scores)]
            if all_scores.size > 0:
                global_min, global_max = np.min(all_scores), np.max(all_scores)

        target_score_val, is_target_mode, grid_min_score = 0, mode == "Target Score", 0
        if is_target_mode:
            try:
                target_score_val = float(self.target_score_var.get())
                data_rows = highlight_df[highlight_df.index != '-- Averages --']
                all_scores_in_grid = data_rows[sens_cols].to_numpy().flatten()
                all_scores_in_grid = all_scores_in_grid[~np.isnan(all_scores_in_grid)]
                if all_scores_in_grid.size > 0: grid_min_score = np.min(all_scores_in_grid)
            except (ValueError, TypeError): is_target_mode = False

        for r_idx, row_data in enumerate(highlight_df.itertuples(index=True)):
            scenario_name = row_data.Index
            
            if is_avg_row_present and scenario_name == "-- Averages --":
                for c_idx in range(len(display_df.columns)):
                    self.results_table.frame[r_idx + 1, c_idx].configure(fg_color=("gray70", "gray25"))
            
            for c_idx, col_name in enumerate(highlight_df.columns):
                table_col_idx = display_df.columns.get_loc(col_name) if col_name in display_df.columns else -1
                if table_col_idx == -1: continue

                try:
                    val = float(row_data[c_idx+1])
                    if pd.isna(val): continue
                except (ValueError, TypeError, IndexError): continue

                if mode == "Performance Drop" and r_idx > 0:
                    if col_name not in perf_drop_cols: continue
                    if is_avg_row_present and r_idx == 1: continue
                    try:
                        above_val = float(values_only[r_idx - 1][c_idx])
                        if pd.notna(above_val) and val < above_val:
                             self.results_table.frame[r_idx + 1, table_col_idx].configure(fg_color="#592020")
                    except (ValueError, TypeError, IndexError): continue
                elif mode == "Row Heatmap":
                    if col_name not in heatmap_cols: continue
                    row_cells = [float(cell) for c, cell in enumerate(row_data[1:]) if highlight_df.columns[c] in sens_cols and pd.notna(cell)]
                    if not row_cells: continue
                    min_score, max_score = min(row_cells), max(row_cells)
                    if min_score == max_score: norm = 1.0 
                    else: norm = (val - min_score) / (max_score - min_score)
                    self.results_table.frame[r_idx + 1, table_col_idx].configure(fg_color=self.get_heatmap_color(norm))
                elif mode == "Global Heatmap" and global_min is not None and global_max is not None and global_min != global_max:
                    if col_name not in heatmap_cols: continue
                    norm = (val - global_min) / (global_max - global_min); self.results_table.frame[r_idx + 1, table_col_idx].configure(fg_color=self.get_heatmap_color(norm))
                elif is_target_mode:
                    if col_name not in heatmap_cols: continue
                    if val >= target_score_val: self.results_table.frame[r_idx + 1, table_col_idx].configure(fg_color="#591e9c")
                    else:
                        denominator = target_score_val - grid_min_score
                        if denominator <= 0: denominator = 1
                        norm = (val - grid_min_score) / denominator; self.results_table.frame[r_idx + 1, table_col_idx].configure(fg_color=self.get_heatmap_color(norm))

    def get_heatmap_color(self, normalized_value):
        normalized_value = max(0, min(1, normalized_value)); COLOR_RED, COLOR_YELLOW, COLOR_GREEN = (120, 47, 47), (122, 118, 50), (54, 107, 54)
        if normalized_value < 0.5:
            local_norm = normalized_value * 2; r, g, b = int(COLOR_RED[0]*(1-local_norm)+COLOR_YELLOW[0]*local_norm), int(COLOR_RED[1]*(1-local_norm)+COLOR_YELLOW[1]*local_norm), int(COLOR_RED[2]*(1-local_norm)+COLOR_YELLOW[2]*local_norm)
        else:
            local_norm = (normalized_value - 0.5) * 2; r, g, b = int(COLOR_YELLOW[0]*(1-local_norm)+COLOR_GREEN[0]*local_norm), int(COLOR_YELLOW[1]*(1-local_norm)+COLOR_GREEN[1]*local_norm), int(COLOR_YELLOW[2]*(1-local_norm)+COLOR_GREEN[2]*local_norm)
        return f"#{r:02x}{g:02x}{b:02x}"

    def bind_graph_events(self, grid_data):
        if not self.results_table or grid_data.empty: return
        scenario_col_idx = grid_data.columns.get_loc('Scenario') if 'Scenario' in grid_data.columns else -1
        if scenario_col_idx == -1: return

        for r_idx, row in enumerate(grid_data.itertuples(index=False)):
            scenario_name = getattr(row, 'Scenario', None)
            if not scenario_name or scenario_name == '-- Averages --': continue
            
            scenario_cell_widget = self.results_table.frame[r_idx + 1, scenario_col_idx]
            scenario_cell_widget.bind("<Button-1>", lambda e, s=scenario_name: self.on_scenario_name_click(e, s))
            scenario_cell_widget.configure(cursor="hand2")

            for c_idx, col_name in enumerate(grid_data.columns):
                if self.is_float(col_name):
                    cell_widget = self.results_table.frame[r_idx + 1, c_idx]
                    cell_widget.bind("<Button-1>", lambda e, s=scenario_name, cm=col_name: self.on_cell_click(e, s, cm)); cell_widget.configure(cursor="hand2")

    def bind_tooltips(self, grid_data):
        if not self.results_table or grid_data.empty or not hasattr(self, 'detailed_stats_cache'): return
        
        scenario_col_idx = grid_data.columns.get_loc('Scenario') if 'Scenario' in grid_data.columns else -1
        if scenario_col_idx == -1: return

        def make_text_func(key):
            def get_tooltip_text():
                stats = self.detailed_stats_cache.get(key)
                if not stats or stats.get('count', 0) == 0: return ""
                
                scen_name = key[0]
                sens_val = key[1]
                sens_display = "All Sensitivities" if sens_val == "ALL" else f"{sens_val}cm"
                
                text_lines = [f"{scen_name}", f"Sensitivity: {sens_display}", "-" * 30]
                pb_date_str = stats['pb_date'].strftime('%Y-%m-%d')
                text_lines.append(f"PB: {stats['max']:.1f} (on {pb_date_str})")
                text_lines.append(f"Runs: {stats['count']}")
                if 'avg' in stats: text_lines.append(f"Avg: {stats['avg']:.1f} (±{stats.get('std', 0):.1f})")
                
                p50_text = f"{stats['p50']:.1f}" if 'p50' in stats else "N/A"
                p75_text = f"{stats['p75']:.1f}" if 'p75' in stats else "N/A"
                text_lines.append(f"Median: {p50_text} | 75th: {p75_text}")

                if 'launchpad_avg' in stats:
                    text_lines.append("-" * 30)
                    text_lines.append(f"Launchpad Avg: {stats['launchpad_avg']:.1f}")
                if 'recent_avg' in stats:
                    text_lines.append(f"Recent Avg:    {stats['recent_avg']:.1f}")
                oracle_msg = stats.get('oracle')
                if oracle_msg:
                    text_lines.append("-" * 30)
                    text_lines.append(oracle_msg)
                
                return "\n".join(text_lines)
            return get_tooltip_text

        def make_plot_data_func(scenario_name, sensitivity):
            def get_plot_data():
                if self.current_family_runs is None: return None
                df = self.current_family_runs[self.current_family_runs['Scenario'] == scenario_name]
                if sensitivity != "ALL":
                    try:
                        s_val = float(sensitivity)
                        df = df[df['Sens'] == s_val]
                    except ValueError: return None
                if df.empty: return None
                df_sorted = df.sort_values('Timestamp')
                return df_sorted[['Score', 'Timestamp']].to_dict('records')
            return get_plot_data

        for r_idx, row in enumerate(grid_data.itertuples(index=False)):
            scenario_name = getattr(row, 'Scenario', None)
            if not scenario_name or scenario_name == '-- Averages --': continue

            row_widget = self.results_table.frame[r_idx + 1, scenario_col_idx]
            tooltip_row = utils.Tooltip(row_widget, make_text_func((scenario_name, "ALL")), make_plot_data_func(scenario_name, "ALL"))
            self.tooltip_instances.append(tooltip_row)

            for c_idx, col_name in enumerate(grid_data.columns):
                if self.is_float(col_name):
                    cell_widget = self.results_table.frame[r_idx + 1, c_idx]
                    tooltip_cell = utils.Tooltip(cell_widget, make_text_func((scenario_name, col_name)), make_plot_data_func(scenario_name, col_name))
                    self.tooltip_instances.append(tooltip_cell)

    def bind_hide_events(self, table_values):
        if not self.results_table or not table_values: return
        column_headers = table_values[0]
        for j, header_text in enumerate(column_headers):
            cm_value = header_text.replace('cm', '')
            if self.is_float(cm_value): self.results_table.frame[0, j].bind("<Button-3>", lambda e, cm=cm_value: self.show_col_context_menu(e, cm))
        for i, row_data in enumerate(table_values[1:]):
            if row_data and row_data[0]: self.results_table.frame[i + 1, 0].bind("<Button-3>", lambda e, s=row_data[0]: self.show_row_context_menu(e, s))
            
    def show_col_context_menu(self, event, cm_value):
        menu = tkinter.Menu(self, tearoff=0); menu.add_command(label=f"Hide {cm_value}cm", command=lambda: self.hide_cm(cm_value)); menu.tk_popup(event.x_root, event.y_root)
        
    def show_row_context_menu(self, event, scenario_name):
        menu = tkinter.Menu(self, tearoff=0); menu.add_command(label=f"Hide Scenario", command=lambda: self.hide_scenario(scenario_name)); menu.tk_popup(event.x_root, event.y_root)
        
    def hide_cm(self, cm_value): 
        base_scenario = self.scenario_search_var.get()
        if not base_scenario: return
        if base_scenario not in self.hidden_cms_by_scenario: self.hidden_cms_by_scenario[base_scenario] = []
        if str(cm_value) not in self.hidden_cms_by_scenario[base_scenario]:
            self.hidden_cms_by_scenario[base_scenario].append(str(cm_value))
        self.save_user_data()
        self.display_grid_data()
    
    def hide_scenario(self, scenario_name): self.hidden_scenarios.add(scenario_name); self.save_user_data(); self.build_filters_and_get_data()
    
    def open_manage_hidden_window(self):
        win = customtkinter.CTkToplevel(self); win.title("Manage Hidden Items"); win.geometry("600x400"); win.transient(self); win.grid_columnconfigure(0, weight=1); win.grid_rowconfigure(1, weight=1)
        customtkinter.CTkLabel(win, text="Right-click a header to hide it. Un-hide items below.", font=customtkinter.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10)
        tabview = customtkinter.CTkTabview(win); tabview.grid(row=1, column=0, padx=10, pady=10, sticky="nsew"); tabview.add("Hidden Scenarios"); tabview.add("Hidden CMs")
        self._populate_manage_hidden_window(tabview)
        
    def _populate_manage_hidden_window(self, tabview):
        scenarios_tab = tabview.tab("Hidden Scenarios")
        for w in scenarios_tab.winfo_children(): w.destroy()
        scenarios_frame = customtkinter.CTkScrollableFrame(scenarios_tab)
        scenarios_frame.pack(expand=True, fill="both")
        if not self.hidden_scenarios: customtkinter.CTkLabel(scenarios_frame, text="No hidden scenarios.").pack(pady=10)
        for scenario in sorted(list(self.hidden_scenarios)):
            item_frame = customtkinter.CTkFrame(scenarios_frame); item_frame.pack(fill="x", pady=2)
            customtkinter.CTkLabel(item_frame, text=scenario, wraplength=400, justify="left").pack(side="left", padx=5, pady=2)
            customtkinter.CTkButton(item_frame, text="Unhide", width=80, command=lambda s=scenario: self.unhide_item('scenario', s, tabview)).pack(side="right", padx=5)

        cms_tab = tabview.tab("Hidden CMs")
        for w in cms_tab.winfo_children(): w.destroy()
        cms_scroll = customtkinter.CTkScrollableFrame(cms_tab)
        cms_scroll.pack(expand=True, fill="both")
        if not self.hidden_cms_by_scenario: customtkinter.CTkLabel(cms_scroll, text="No hidden CMs.").pack(pady=10); return

        for scen_name, hidden_list in self.hidden_cms_by_scenario.items():
            if not hidden_list: continue
            header_frame = customtkinter.CTkFrame(cms_scroll, fg_color=("gray75", "gray25")); header_frame.pack(fill="x", pady=(5, 0))
            content_frame = customtkinter.CTkFrame(cms_scroll, fg_color="transparent"); content_frame.pack(fill="x", pady=(0, 5), padx=10)
            def toggle(frame=content_frame, btn=None):
                if frame.winfo_viewable(): frame.pack_forget(); btn.configure(text="▶") if btn else None
                else: frame.pack(fill="x", pady=(0, 5), padx=10); btn.configure(text="▼") if btn else None
            toggle_btn = customtkinter.CTkButton(header_frame, text="▼", width=20, height=20, fg_color="transparent", text_color=("black", "white"), command=lambda f=content_frame: toggle(f))
            toggle_btn.configure(command=lambda f=content_frame, b=toggle_btn: toggle(f, b))
            toggle_btn.pack(side="left", padx=5)
            customtkinter.CTkLabel(header_frame, text=f"{scen_name} ({len(hidden_list)})", font=customtkinter.CTkFont(weight="bold")).pack(side="left", padx=5, pady=5)
            for cm in sorted(hidden_list, key=float):
                row = customtkinter.CTkFrame(content_frame); row.pack(fill="x", pady=1)
                customtkinter.CTkLabel(row, text=f"{cm}cm").pack(side="left", padx=10)
                customtkinter.CTkButton(row, text="Unhide", width=60, height=24, command=lambda s=scen_name, c=cm: self.unhide_item('cm', c, tabview, s)).pack(side="right", padx=5, pady=2)
            
    def unhide_item(self, item_type, value, tabview, scenario_key=None):
        if item_type == 'scenario': self.hidden_scenarios.remove(value); self.build_filters_and_get_data()
        elif item_type == 'cm' and scenario_key:
            if scenario_key in self.hidden_cms_by_scenario:
                if str(value) in self.hidden_cms_by_scenario[scenario_key]:
                    self.hidden_cms_by_scenario[scenario_key].remove(str(value))
                    if not self.hidden_cms_by_scenario[scenario_key]: del self.hidden_cms_by_scenario[scenario_key]
            self.display_grid_data()
        self.save_user_data(); self._populate_manage_hidden_window(tabview)

    def _get_recently_played_bases(self, num_to_scan=300, num_to_return=15):
        if self.all_runs_df is None or self.all_runs_df.empty: return []
        recent_uniques_series = self.all_runs_df.drop_duplicates(subset=['Scenario'], keep='last')
        recent_uniques_list = recent_uniques_series.tail(num_to_scan)['Scenario'].tolist()
        recency_scores = {name: i for i, name in enumerate(recent_uniques_list)}
        sorted_recents = sorted(recent_uniques_list)
        base_scenarios = []
        for scenario in sorted_recents:
            is_variant = any(scenario.startswith(s + ' ') for s in base_scenarios)
            if not is_variant: base_scenarios.append(scenario)
        def get_group_recency_score(base_name):
            group_members = [s for s in recent_uniques_list if s == base_name or s.startswith(base_name + ' ')]
            if not group_members: return -1
            max_score = max(recency_scores.get(member, -1) for member in group_members)
            return max_score
        base_scenarios.sort(key=get_group_recency_score, reverse=True)
        return base_scenarios[:num_to_return]
        
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
        for frame in [self.favorites_frame, self.recents_frame, self.recently_played_frame]:
            for widget in frame.winfo_children(): widget.destroy()

        customtkinter.CTkLabel(self.recently_played_frame, text="Recently Played", font=customtkinter.CTkFont(weight="bold")).pack(anchor="w", padx=10)
        recently_played = self._get_recently_played_bases()
        for scen in recently_played:
            selection = {"name": scen, "axis": ""} 
            btn = customtkinter.CTkButton(self.recently_played_frame, text=scen, fg_color="transparent", anchor="w", command=lambda s=selection: self.select_from_list(s))
            btn.pack(fill="x", padx=5)

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
        if not base_scenario or self.all_runs_df is None: return
        saved_target = self.target_scores_by_scenario.get(base_scenario, "3000")
        self.target_score_var.set(saved_target)
        
        settings = self.sens_settings_by_scenario.get(base_scenario, {"mode": "All", "step": "3", "list": ""})
        self.sens_filter_mode_var.set(settings.get("mode", "All"))
        self.sens_custom_step_var.set(settings.get("step", "3"))
        self.sens_specific_list_var.set(settings.get("list", ""))

        self.current_family_runs = engine.get_scenario_family_info(self.all_runs_df, base_scenario)
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
        home = Path.home()
        paths_to_check = [
            Path("C:/Program Files (x86)/Steam/steamapps/common/FPSAimTrainer/FPSAimTrainer/stats"),
            home / ".steam/steam/steamapps/common/FPSAimTrainer/FPSAimTrainer/stats",
            home / ".local/share/Steam/steamapps/common/FPSAimTrainer/FPSAimTrainer/stats"
        ]
        for path in paths_to_check:
            if path.exists():
                self.path_entry.insert(0, str(path))
                break
                
    def format_timedelta(self, td):
        if isinstance(td, (int, float)): td = timedelta(seconds=td)
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f'{hours:02}:{minutes:02}:{seconds:02}'

    def open_session_history(self):
        if self.all_runs_df is None or self.all_runs_df.empty or 'SessionID' not in self.all_runs_df.columns: return
        summary_list = []
        for session_id, group in self.all_runs_df.groupby('SessionID'):
            start_time = group['Timestamp'].min()
            summary = {
                "id": session_id,
                "date_str": start_time.strftime('%B %d, %Y'),
                "total_duration_str": self.format_timedelta(group['Timestamp'].max() - start_time),
                "play_count": len(group),
                "top_scenario": group['Scenario'].mode()[0] if not group.empty else "N/A"
            }
            summary_list.append(summary)
        summary_list.sort(key=lambda x: x['id'], reverse=True)
        windows.SessionHistoryWindow(self, summary_list)

    def open_session_report(self, event=None, session_id=None):
        if self.all_runs_df is None or self.all_runs_df.empty: return
        self._calculate_and_show_report(session_id)

    def _generate_session_payload(self, session_id):
        if self.all_runs_df is None or 'SessionID' not in self.all_runs_df.columns: return None
        if session_id is None: session_id = self.all_runs_df['SessionID'].max()
        
        session_df = self.all_runs_df[self.all_runs_df['SessionID'] == session_id].copy()
        if session_df.empty: return None

        session_start_time = session_df['Timestamp'].min()
        history_before_session = self.all_runs_df[self.all_runs_df['Timestamp'] < session_start_time]
        
        total_duration = session_df['Timestamp'].max() - session_start_time
        active_playtime = session_df['Duration'].sum()
        
        header_metrics = {
            "total_duration_str": self.format_timedelta(total_duration),
            "active_playtime_str": self.format_timedelta(active_playtime),
            "play_density": (active_playtime / total_duration.total_seconds() * 100) if total_duration.total_seconds() > 0 else 0,
            "total_plays_grid": len(session_df),
            "total_plays_scenario": session_df['Scenario'].nunique()
        }
        
        relevant_keys = set(zip(session_df['Scenario'], session_df['Sens']))
        relevant_history = history_before_session[history_before_session.set_index(['Scenario', 'Sens']).index.isin(relevant_keys)]

        running_stats = defaultdict(lambda: {'sum': 0.0, 'count': 0})
        if not relevant_history.empty:
            grouped_history = relevant_history.groupby(['Scenario', 'Sens'])['Score'].agg(['sum', 'count'])
            for (scen, sens), row in grouped_history.iterrows():
                running_stats[(scen, sens)]['sum'] = row['sum']
                running_stats[(scen, sens)]['count'] = row['count']

        graph_data = []
        sorted_session = session_df.sort_values('Timestamp')
        for row in sorted_session.itertuples():
            key = (row.Scenario, row.Sens)
            stats = running_stats[key]
            if stats['count'] > 0:
                current_avg = stats['sum'] / stats['count']
                perf_pct = ((row.Score - current_avg) / current_avg) * 100
            else: perf_pct = 0.0 
            graph_data.append({'time': row.Timestamp, 'pct': perf_pct, 'scenario': row.Scenario, 'sens': row.Sens})
            stats['sum'] += row.Score; stats['count'] += 1
        
        report_data = {"grid": defaultdict(list), "scenario": defaultdict(list)}
        all_time_grid_stats = self.all_runs_df.groupby(['Scenario', 'Sens'])['Score'].agg(['mean', 'size'])
        prev_grid_pb = history_before_session.groupby(['Scenario', 'Sens'])['Score'].max()
        all_time_scen_stats = self.all_runs_df.groupby('Scenario')['Score'].agg(['mean', 'size'])
        prev_scen_pb = history_before_session.groupby('Scenario')['Score'].max()
        
        for (scenario, sens), group in session_df.groupby(['Scenario', 'Sens']):
            session_pb = group['Score'].max()
            is_first_time = (scenario, sens) not in prev_grid_pb.index
            prev_pb = 0 if is_first_time else prev_grid_pb.loc[(scenario, sens)]
            is_pb = not is_first_time and session_pb > prev_pb
            session_avg = group['Score'].mean()
            all_time_avg = all_time_grid_stats.loc[(scenario, sens)]['mean'] if (scenario, sens) in all_time_grid_stats.index else 0
            all_time_count = all_time_grid_stats.loc[(scenario, sens)]['size'] if (scenario, sens) in all_time_grid_stats.index else 0

            item = { "name": scenario, "sens": sens, "play_count": len(group), "first_played": group['Timestamp'].min(), 
                        "session_avg": session_avg, "all_time_avg": all_time_avg, "all_time_play_count": all_time_count,
                        "perf_vs_avg": (session_avg / all_time_avg - 1) * 100 if all_time_avg > 0 else 0, "is_pb": is_pb }
            report_data["grid"]["played"].append(item)
            if not is_first_time: report_data["grid"]["averages"].append(item)
            if is_pb:
                item_pb = item.copy()
                item_pb.update({ "new_score": session_pb, "prev_score": prev_pb, "improvement_pts": session_pb - prev_pb, "improvement_pct": (session_pb / prev_pb - 1) * 100 if prev_pb > 0 else float('inf') })
                report_data["grid"]["pbs"].append(item_pb)

        for scenario, group in session_df.groupby('Scenario'):
            session_pb = group['Score'].max()
            is_first_time = scenario not in prev_scen_pb.index
            prev_pb = 0 if is_first_time else prev_scen_pb.loc[scenario]
            is_pb = not is_first_time and session_pb > prev_pb
            session_avg = group['Score'].mean()
            all_time_avg = all_time_scen_stats.loc[scenario]['mean'] if scenario in all_time_scen_stats.index else 0
            all_time_count = all_time_scen_stats.loc[scenario]['size'] if scenario in all_time_scen_stats.index else 0
            
            item = { "name": scenario, "play_count": len(group), "first_played": group['Timestamp'].min(), 
                        "session_avg": session_avg, "all_time_avg": all_time_avg, "all_time_play_count": all_time_count,
                        "perf_vs_avg": (session_avg / all_time_avg - 1) * 100 if all_time_avg > 0 else 0, "is_pb": is_pb }
            report_data["scenario"]["played"].append(item)
            if not is_first_time: report_data["scenario"]["averages"].append(item)
            if is_pb:
                item_pb = item.copy()
                item_pb.update({ "new_score": session_pb, "prev_score": prev_pb, "improvement_pts": session_pb - prev_pb, "improvement_pct": (session_pb / prev_pb - 1) * 100 if prev_pb > 0 else float('inf') })
                report_data["scenario"]["pbs"].append(item_pb)
        
        session_date_str = session_start_time.strftime('%B %d, %Y')
        return (header_metrics, report_data, session_date_str, graph_data)

    def _calculate_and_show_report(self, session_id):
        self.status_label.configure(text="Calculating session report...")
        try:
            data = self._generate_session_payload(session_id)
            if data:
                self.after(0, self._show_session_report_window, session_id, *data)
        finally:
            self.after(0, self.status_label.configure, {"text": "Report ready."})

    def _show_session_report_window(self, session_id, header_metrics, report_data, session_date_str, graph_data):
        # Save reference so we can refresh it later
        self.current_report_window = windows.SessionReportWindow(self, session_id, header_metrics, report_data, session_date_str, graph_data)


    def trigger_report_refresh(self, report_window, session_id):
        # Just trigger a standard load. 
        # on_load_complete will see self.current_report_window and update it.
        self.load_stats_thread()