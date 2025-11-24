import bisect
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
import windows
import engine

import windows
import utils
import locales # --- NEW: Import Locales ---

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
        
        self.language_var = customtkinter.StringVar(value="en") 
        self.current_language = "en"

        self.target_score_var = customtkinter.StringVar(value="3000")
        
        self.percentile_var = customtkinter.StringVar(value="75")
        self.recent_success_days_var = customtkinter.StringVar(value="14")
        
        # --- SESSION GRAPH SETTINGS ---
        self.graph_show_trend_var = customtkinter.BooleanVar(value=True)
        self.graph_show_flow_var = customtkinter.BooleanVar(value=True)
        self.graph_show_pulse_var = customtkinter.BooleanVar(value=False)
        self.graph_flow_window_var = customtkinter.StringVar(value="5")

        # --- GRID GRAPH SETTINGS ---
        self.graph_grid_show_trend_var = customtkinter.BooleanVar(value=False)
        
        # SMA 1 (Purple)
        self.graph_grid_show_sma_var = customtkinter.BooleanVar(value=False)
        self.graph_grid_sma_window_var = customtkinter.StringVar(value="20")
        
        # SMA 2 (Cyan) - NEW
        self.graph_grid_show_sma2_var = customtkinter.BooleanVar(value=False)
        self.graph_grid_sma2_window_var = customtkinter.StringVar(value="10")
        # ---------------------------

        self.session_gap_minutes_var = customtkinter.StringVar(value="30")
        
        self.pb_rank_var = customtkinter.StringVar(value="1")
        self.pb_rank_var.trace_add("write", self.schedule_rank_update)
        self.rank_update_job = None
        
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
        
        self.current_report_window = None
        self.open_graph_windows = []
        
        self.tooltip_instances = []
        self.detailed_stats_cache = {}

        self.load_user_data()
        customtkinter.set_appearance_mode(self.appearance_mode_var.get())
        
        self.title(locales.get_text(self.current_language, "window_title"))
        
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
        
        self.rating_frame = customtkinter.CTkFrame(self.bottom_frame, height=50)
        self.rating_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(0, 5))
        
        # Prevent frame from shrinking to fit just the small hint text
        self.rating_frame.grid_propagate(False) 

        # 1. Rating Label: Absolute Center
        self.rating_label = customtkinter.CTkLabel(self.rating_frame, text=locales.get_text(self.current_language, "rating", val="-"), font=("Arial", 24, "bold"))
        self.rating_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # 2. Hint Text: Right Aligned
        self.hint_label = customtkinter.CTkLabel(self.rating_frame, text=locales.get_text(self.current_language, "hint_hide"), text_color="gray")
        # Use pack or place for the hint. Place is safer here to avoid conflict with grid_propagate(False).
        self.hint_label.place(relx=1.0, rely=0.5, anchor="e", x=-20) # x=-20 provides the padding
        
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
                
                lang = data.get("language_preference", "en")
                self.language_var.set(lang)
                self.current_language = lang

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
                
                self.last_custom_rank = data.get("last_custom_rank", 3)
                
                self.percentile_var.set(str(data.get("percentile_preference", "75")))
                self.recent_success_days_var.set(str(data.get("recent_success_days", "14")))
                
                # --- SESSION GRAPH SETTINGS ---
                self.graph_show_trend_var.set(data.get("graph_show_trend", True))
                self.graph_show_flow_var.set(data.get("graph_show_flow", True))
                self.graph_show_pulse_var.set(data.get("graph_show_pulse", False))
                self.graph_flow_window_var.set(str(data.get("graph_flow_window", "5")))
                
                # --- GRID GRAPH SETTINGS ---
                self.graph_grid_show_trend_var.set(data.get("graph_grid_show_trend", False))
                
                self.graph_grid_show_sma_var.set(data.get("graph_grid_show_sma", False))
                self.graph_grid_sma_window_var.set(str(data.get("graph_grid_sma_window", "20")))
                
                self.graph_grid_show_sma2_var.set(data.get("graph_grid_show_sma2", False))
                self.graph_grid_sma2_window_var.set(str(data.get("graph_grid_sma2_window", "10")))

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
        
        try:
            current_rank_val = int(self.pb_rank_var.get())
            if current_rank_val > 1:
                self.last_custom_rank = current_rank_val
        except ValueError: pass

        data_to_save = {
            "window_geometry": self.geometry(),
            "appearance_mode": self.appearance_mode_var.get(),
            "language_preference": self.language_var.get(),
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
            "last_custom_rank": self.last_custom_rank,
            "percentile_preference": self.percentile_var.get(),
            "recent_success_days": self.recent_success_days_var.get(),
            
            # --- SESSION GRAPH SETTINGS ---
            "graph_show_trend": self.graph_show_trend_var.get(),
            "graph_show_flow": self.graph_show_flow_var.get(),
            "graph_show_pulse": self.graph_show_pulse_var.get(),
            "graph_flow_window": self.graph_flow_window_var.get(),
            
            # --- GRID GRAPH SETTINGS ---
            "graph_grid_show_trend": self.graph_grid_show_trend_var.get(),
            "graph_grid_show_sma": self.graph_grid_show_sma_var.get(),
            "graph_grid_sma_window": self.graph_grid_sma_window_var.get(),
            "graph_grid_show_sma2": self.graph_grid_show_sma2_var.get(),
            "graph_grid_sma2_window": self.graph_grid_sma2_window_var.get(),
        }
        with open(USER_DATA_FILE, 'w') as f: json.dump(data_to_save, f, indent=2)

    # --- NEW: Handle Language Change ---
    def on_language_change(self, choice):
        # Convert Display Name -> Code
        code = self.lang_map.get(choice, "en")
        self.language_var.set(code) # Save code
        
        self.save_user_data()
        tkinter.messagebox.showinfo(
            locales.get_text(self.language_var.get(), "restart_title"),
            locales.get_text(self.language_var.get(), "restart_msg")
        )
    # -----------------------------------

    def register_graph_window(self, window):
        self.open_graph_windows.append(window)

    def deregister_graph_window(self, window):
        if window in self.open_graph_windows:
            self.open_graph_windows.remove(window)

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
        # Localized Title
        title = f"History: {scenario_name} at {sensitivity}cm" # Keeping simple for now, or could localize "History"
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
        
        # Localized
        self.select_path_button = customtkinter.CTkButton(self.path_frame, text=locales.get_text(self.current_language, "select_folder_btn"), command=self.select_stats_folder); self.select_path_button.grid(row=0, column=0, padx=(0,10), pady=10)
        self.path_entry = customtkinter.CTkEntry(self.path_frame, placeholder_text="Path to KovaaK's stats folder..."); self.path_entry.grid(row=0, column=1, sticky="ew", pady=10)
        
        # Action Frame (Load Button + Report Buttons)
        action_frame = customtkinter.CTkFrame(self.path_frame, fg_color="transparent"); action_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0,10)); action_frame.grid_columnconfigure(0, weight=1)
        
        # 1. Load Button (Expands to fill left space)
        self.load_button = customtkinter.CTkButton(action_frame, text=locales.get_text(self.current_language, "load_btn"), font=("Arial", 18, "bold"), height=50, command=self.load_stats_thread); self.load_button.grid(row=0, column=0, sticky="ew")
        
        # 2. Report Buttons Frame (Right side)
        report_buttons_frame = customtkinter.CTkFrame(action_frame, fg_color="transparent")
        report_buttons_frame.grid(row=0, column=1, padx=(10,0), sticky="ns")
        
        # Button Config: Height=50 to match Load Button, Width=140 for text space
        btn_h, btn_w = 50, 140
        
        # A. Career Profile
        self.profile_button = customtkinter.CTkButton(report_buttons_frame, text="Career Profile", command=self.open_career_profile, state="disabled", fg_color="#673AB7", hover_color="#512DA8", height=btn_h, width=btn_w)
        self.profile_button.grid(row=0, column=0, padx=(0, 5))
        
        # B. Session History
        self.session_history_button = customtkinter.CTkButton(report_buttons_frame, text=locales.get_text(self.current_language, "session_hist_btn"), command=self.open_session_history, state="disabled", height=btn_h, width=btn_w)
        self.session_history_button.grid(row=0, column=1, padx=(0, 5))

        # C. Last Session Report
        self.session_report_button = customtkinter.CTkButton(report_buttons_frame, text=locales.get_text(self.current_language, "session_report_btn"), command=self.open_session_report, state="disabled", height=btn_h, width=btn_w)
        self.session_report_button.grid(row=0, column=2)
        
        # Status Bar
        status_frame = customtkinter.CTkFrame(self.path_frame, fg_color="transparent"); status_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.status_label = customtkinter.CTkLabel(status_frame, text=locales.get_text(self.current_language, "ready_label"), anchor="w"); self.status_label.pack(side="left", padx=(0,10))
        self.progress_bar = customtkinter.CTkProgressBar(self.path_frame, mode='indeterminate')

    def open_career_profile(self):
        if self.all_runs_df is None: return
        windows.CareerProfileWindow(self, self.all_runs_df)

    def _build_main_ui_controls(self):
        self.main_controls_header, self.main_controls_content = self._create_collapsible_section("Options & Analysis", "main_controls", 1); self.main_controls_content.grid_columnconfigure(0, weight=1)
        
        selection_content_frame = customtkinter.CTkFrame(self.main_controls_content); selection_content_frame.grid(row=0, column=0, sticky="ew", pady=(0,5)); selection_content_frame.grid_columnconfigure(0, weight=1)
        
        search_frame = customtkinter.CTkFrame(selection_content_frame); search_frame.grid(row=0, column=0, sticky="ew", pady=(0,5))
        search_frame.grid_columnconfigure(1, weight=1)
        
        user_lists_frame = customtkinter.CTkFrame(selection_content_frame); user_lists_frame.grid(row=1, column=0, sticky="ew")
        user_lists_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        self.scenario_entry_label = customtkinter.CTkLabel(search_frame, text=locales.get_text(self.current_language, "search_label")); self.scenario_entry_label.grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(5,0))
        self.scenario_search_var = customtkinter.StringVar(); self.scenario_search_var.trace_add("write", self.update_autocomplete)
        
        self.clear_btn = customtkinter.CTkButton(search_frame, text="✕", width=30, fg_color=("gray75", "gray30"), command=self.clear_search); self.clear_btn.grid(row=1, column=0, padx=(10, 5), pady=5)
        self.scenario_entry = customtkinter.CTkEntry(search_frame, textvariable=self.scenario_search_var, state="disabled"); self.scenario_entry.grid(row=1, column=1, sticky="ew", padx=(0, 5), pady=5)
        self.fav_button = customtkinter.CTkButton(search_frame, text="☆", font=("Arial", 20), width=30, command=self.toggle_favorite); self.fav_button.grid(row=1, column=2, padx=(0,10), pady=5)
        
        self.autocomplete_listbox = customtkinter.CTkScrollableFrame(search_frame, height=150); self.autocomplete_listbox.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=5); self.autocomplete_listbox.grid_remove()
        
        self.favorites_frame = customtkinter.CTkFrame(user_lists_frame); self.favorites_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.recents_frame = customtkinter.CTkFrame(user_lists_frame); self.recents_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.recently_played_frame = customtkinter.CTkScrollableFrame(user_lists_frame); self.recently_played_frame.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)
        self.update_user_lists_display()
        
        # --- UNIFIED SETTINGS AREA ---
        display_top_row_frame = customtkinter.CTkFrame(self.main_controls_content)
        display_top_row_frame.grid(row=1, column=0, sticky="ew", pady=5)
        
        # 1. Language Group (Left, Prominent)
        lang_frame = customtkinter.CTkFrame(display_top_row_frame, fg_color="transparent")
        lang_frame.pack(side="left", padx=10, pady=5)
        
        # Big Emoji + Text Label
        customtkinter.CTkLabel(lang_frame, text="🌐 Language/言語", font=("Arial", 14, "bold")).pack(side="left", padx=(0,10))
        
        self.lang_map = {
            "English": "en", 
            "Español (ES)": "es",
            "Português (PT)": "pt",
            "日本語 (JP)": "jp", 
            "한국어 (KO)": "ko",
            "简体中文 (CN)": "cn",
            "한국어 (KO)": "ko",
            "Русский (RU)": "ru",
            "Українська (UA)": "ua"
        }
        self.lang_display_list = list(self.lang_map.keys())
        current_disp = next((k for k, v in self.lang_map.items() if v == self.language_var.get()), "English")
        self.lang_display_var = customtkinter.StringVar(value=current_disp)
        
        # Dropdown
        customtkinter.CTkOptionMenu(lang_frame, variable=self.lang_display_var, values=self.lang_display_list, command=self.on_language_change, width=130, height=32).pack(side="left")

        # Separator Line (Visual)
        sep = customtkinter.CTkFrame(display_top_row_frame, width=2, height=40, fg_color=("gray70", "gray30"))
        sep.pack(side="left", padx=5)

        # 2. Main Settings Group (Right)
        settings_group = customtkinter.CTkFrame(display_top_row_frame, fg_color="transparent")
        settings_group.pack(side="left", fill="both", expand=True, padx=5)
        
        # Row A: Theme | Session Gap | Decimals | Hidden
        row_a = customtkinter.CTkFrame(settings_group, fg_color="transparent")
        row_a.pack(fill="x", pady=2)
        
        # Theme
        customtkinter.CTkLabel(row_a, text=locales.get_text(self.current_language, "theme")).pack(side="left", padx=(0,5))
        customtkinter.CTkOptionMenu(row_a, variable=self.appearance_mode_var, values=["System", "Dark", "Light"], command=self.on_appearance_mode_change, width=90).pack(side="left")
        
        # Session Gap
        customtkinter.CTkLabel(row_a, text=locales.get_text(self.current_language, "session_gap")).pack(side="left", padx=(15, 5));
        customtkinter.CTkEntry(row_a, textvariable=self.session_gap_minutes_var, width=40).pack(side="left")
        customtkinter.CTkLabel(row_a, text=locales.get_text(self.current_language, "req_refresh"), font=customtkinter.CTkFont(size=10, slant="italic"), text_color="gray").pack(side="left", padx=(2,0));

        # Decimals
        customtkinter.CTkSwitch(row_a, text=locales.get_text(self.current_language, "show_decimals"), variable=self.show_decimals_var, onvalue="On", offvalue="Off", command=self.on_display_option_change).pack(side="left", padx=(15,0))
        
        # Manage Hidden (Right align, taller)
        customtkinter.CTkButton(row_a, text=locales.get_text(self.current_language, "manage_hidden"), command=self.open_manage_hidden_window, height=32).pack(side="right", padx=5, anchor="center")

        # Row B: Font | Cell Height
        row_b = customtkinter.CTkFrame(settings_group, fg_color="transparent")
        row_b.pack(fill="x", pady=2)
        
        customtkinter.CTkLabel(row_b, text=locales.get_text(self.current_language, "font_size")).pack(side="left")
        font_size_entry = customtkinter.CTkEntry(row_b, textvariable=self.font_size_var, width=40)
        font_size_entry.pack(side="left", padx=(0,10))
        customtkinter.CTkLabel(row_b, text=locales.get_text(self.current_language, "cell_h")).pack(side="left")
        cell_height_entry = customtkinter.CTkEntry(row_b, textvariable=self.cell_height_var, width=40)
        cell_height_entry.pack(side="left")
        font_size_entry.bind("<Return>", self.on_display_option_change)
        cell_height_entry.bind("<Return>", self.on_display_option_change)
        # -----------------------------------

        self.filters_frame = customtkinter.CTkFrame(self.main_controls_content); self.filters_frame.grid(row=2, column=0, sticky="ew", pady=(5,0)); self.format_filter_frame = customtkinter.CTkFrame(self.main_controls_content); self.format_filter_frame.grid(row=3, column=0, sticky="ew", pady=(0,5))
        
        analysis_modes_frame = customtkinter.CTkFrame(self.top_frame)
        analysis_modes_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(5,5))
        analysis_modes_frame.grid_columnconfigure(0, weight=1)

        analysis_row1 = customtkinter.CTkFrame(analysis_modes_frame, fg_color="transparent")
        analysis_row1.grid(row=0, column=0, sticky="ew")

        sens_filter_group = customtkinter.CTkFrame(analysis_row1)
        sens_filter_group.pack(side="left", padx=(0,5), fill="both")
        customtkinter.CTkLabel(sens_filter_group, text=locales.get_text(self.current_language, "sens_filter")).pack(side="left", padx=(10,5), pady=5)
        
        self.sens_filter_menu = customtkinter.CTkOptionMenu(sens_filter_group, variable=self.sens_filter_mode_var, values=["All", "2cm Step", "3cm Step", "5cm Step", "10cm Step", "Custom Step", "Specific List"], width=110, command=self.on_display_option_change)
        self.sens_filter_menu.pack(side="left", padx=5, pady=5)
        self.sens_custom_step_entry = customtkinter.CTkEntry(sens_filter_group, textvariable=self.sens_custom_step_var, width=40, placeholder_text="3")
        self.sens_custom_step_entry.bind("<Return>", self.on_display_option_change)
        self.sens_specific_list_entry = customtkinter.CTkEntry(sens_filter_group, textvariable=self.sens_specific_list_var, width=120, placeholder_text="34.6, 43.3...")
        self.sens_specific_list_entry.bind("<Return>", self.on_display_option_change)

        grid_mode_frame = customtkinter.CTkFrame(analysis_row1); 
        grid_mode_frame.pack(side="left", padx=5, fill="both", expand=True)
        customtkinter.CTkLabel(grid_mode_frame, text=locales.get_text(self.current_language, "grid_mode")).pack(side="left", padx=(10,5), pady=5)
        
        self.pb_rank_frame = customtkinter.CTkFrame(grid_mode_frame, fg_color="transparent")
        self.pb_rank_frame.pack(side="left", padx=(0, 5))
        customtkinter.CTkLabel(self.pb_rank_frame, text=locales.get_text(self.current_language, "pb_num")).pack(side="left", padx=(0,2))
        self.rank_toggle_btn = customtkinter.CTkButton(self.pb_rank_frame, text="1⇄N", width=40, height=20, fg_color=("gray70", "gray30"), command=self.toggle_pb_rank)
        self.rank_toggle_btn.pack(side="left", padx=3)
        btn_minus = customtkinter.CTkButton(self.pb_rank_frame, text="-", width=20, height=20, command=lambda: self.change_pb_rank(-1)); btn_minus.pack(side="left", padx=2)
        entry_rank = customtkinter.CTkEntry(self.pb_rank_frame, textvariable=self.pb_rank_var, width=30, height=20); entry_rank.pack(side="left", padx=2)
        entry_rank.bind("<Return>", lambda e: self.on_display_option_change())
        btn_plus = customtkinter.CTkButton(self.pb_rank_frame, text="+", width=20, height=20, command=lambda: self.change_pb_rank(1)); btn_plus.pack(side="left", padx=2)

        modes = [("Personal Best", "mode_pb"), ("Average Score", "mode_avg"), ("Play Count", "mode_count")]
        for mode_val, loc_key in modes:
            text = locales.get_text(self.current_language, loc_key)
            customtkinter.CTkRadioButton(grid_mode_frame, text=text, variable=self.grid_display_mode_var, value=mode_val, command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        
        self.perc_frame = customtkinter.CTkFrame(grid_mode_frame, fg_color="transparent")
        self.perc_frame.pack(side="left", padx=5)
        
        p_text = locales.get_text(self.current_language, "mode_percentile", val="Nth Percentile") 
        customtkinter.CTkRadioButton(self.perc_frame, text=p_text, variable=self.grid_display_mode_var, value="Nth Percentile", command=self.on_display_option_change).pack(side="left")
        
        self.percentile_entry = customtkinter.CTkEntry(self.perc_frame, textvariable=self.percentile_var, width=40)
        self.percentile_var.trace_add("write", self._schedule_refresh)

        highlight_group = customtkinter.CTkFrame(analysis_modes_frame); highlight_group.grid(row=1, column=0, sticky="ew", pady=(5,0))
        customtkinter.CTkLabel(highlight_group, text=locales.get_text(self.current_language, "highlight")).pack(side="left", padx=(10,5), pady=5)
        
        hl_container = customtkinter.CTkFrame(highlight_group, fg_color="transparent")
        hl_container.pack(side="left", fill="both", expand=True)
        
        h_modes = [
            ("None", "hl_none"),
            ("Performance Drop", "hl_drop"),
            ("Row Heatmap", "hl_row_heat"),
            ("Global Heatmap", "hl_global_heat")
        ]
        for val, loc_key in h_modes:
            text = locales.get_text(self.current_language, loc_key)
            customtkinter.CTkRadioButton(hl_container, text=text, variable=self.highlight_mode_var, value=val, command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        
        self.ts_frame = customtkinter.CTkFrame(hl_container, fg_color="transparent")
        self.ts_frame.pack(side="left", padx=5)
        
        ts_text = locales.get_text(self.current_language, "hl_target")
        customtkinter.CTkRadioButton(self.ts_frame, text=ts_text, variable=self.highlight_mode_var, value="Target Score", command=self.on_display_option_change).pack(side="left")
        self.target_score_entry = customtkinter.CTkEntry(self.ts_frame, textvariable=self.target_score_var, width=80)
        self.target_score_var.trace_add("write", self._schedule_refresh)

        self.rs_frame = customtkinter.CTkFrame(hl_container, fg_color="transparent")
        self.rs_frame.pack(side="left", padx=5)
        
        rs_text = locales.get_text(self.current_language, "hl_recent_success", val="Recent Success")
        customtkinter.CTkRadioButton(self.rs_frame, text=rs_text, variable=self.highlight_mode_var, value="Recent Success", command=self.on_display_option_change).pack(side="left")
        self.recent_days_entry = customtkinter.CTkEntry(self.rs_frame, textvariable=self.recent_success_days_var, width=40)
        self.recent_success_days_var.trace_add("write", self._schedule_refresh)
        
        self.top_frame.grid_rowconfigure(4, weight=1)
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
        # Localized
        self.status_label.configure(text=locales.get_text(self.current_language, "loading_label"))
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
            # --- ENRICH DATA ---
            self.status_label.configure(text="Calculating Rank History (One-time)...")
            self.update_idletasks() # Force UI update so user sees message
            self.all_runs_df = engine.enrich_history_with_stats(all_runs_df)
            # -------------------
            
            unique_scenarios = self.all_runs_df['Scenario'].unique()
            self.scenario_list = sorted(list(unique_scenarios))
            self.update_user_lists_display()
            # Localized
            self.status_label.configure(text=locales.get_text(self.current_language, "loaded_label", count=len(self.all_runs_df)))
            self.scenario_entry.configure(state="normal")
            
            # Enable buttons
            self.session_report_button.configure(state="normal")
            self.session_history_button.configure(state="normal")
            self.profile_button.configure(state="normal")
            
            self.load_button.configure(text=locales.get_text(self.current_language, "refresh_btn"))
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
                    sid = self.current_report_window.session_id
                    data = self._generate_session_payload(sid)
                    if data:
                        self.current_report_window.update_content(*data)
                except Exception as e:
                    print(f"Error refreshing report window: {e}")

            for window in list(self.open_graph_windows):
                if window.winfo_exists():
                    try:
                        scen, sens_str = window.graph_id.split('|')
                        df = self.all_runs_df[self.all_runs_df['Scenario'] == scen].copy()
                        if sens_str != "ALL":
                            df = df[df['Sens'] == float(sens_str)]
                        df.sort_values(by='Timestamp', inplace=True)
                        window.update_data(df)
                    except Exception as e:
                        print(f"Error updating graph window {window.title_text}: {e}")
                else:
                    self.deregister_graph_window(window)

            if callback: callback()
        else:
            if all_runs_df is None: self.status_label.configure(text=locales.get_text(self.current_language, "load_err_label"))
            else: self.status_label.configure(text="Data loaded, but is missing 'Duration'. Please Refresh Stats (F5).")
            self.all_runs_df, self.scenario_list = None, []
            self.session_report_button.configure(state="disabled")
            self.session_history_button.configure(state="disabled")
            self.profile_button.configure(state="disabled")
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
        # Percentile
        if self.grid_display_mode_var.get() == "Nth Percentile":
            self.percentile_entry.pack(side="left", padx=(5,0))
        else:
            self.percentile_entry.pack_forget()

        # Target Score
        if self.highlight_mode_var.get() == "Target Score":
            self.target_score_entry.pack(side="left", padx=(5,0))
        else:
            self.target_score_entry.pack_forget()

        # Recent Success
        if self.highlight_mode_var.get() == "Recent Success":
            self.recent_days_entry.pack(side="left", padx=(5,0))
        else:
            self.recent_days_entry.pack_forget()

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

        self.filters_frame.grid(); customtkinter.CTkLabel(self.filters_frame, text=locales.get_text(self.current_language, "compare_by")).pack(side="left", padx=(10,5), pady=5)
        preferred_axis = self.variable_axis_var.get()
        if not preferred_axis or preferred_axis not in all_modifiers.keys(): self.variable_axis_var.set(list(all_modifiers.keys())[0])
        
        for key in sorted(list(all_modifiers.keys())):
            customtkinter.CTkRadioButton(self.filters_frame, text=key, variable=self.variable_axis_var, value=key, command=self.build_filters_and_get_data).pack(side="left", padx=5, pady=5)
        
        patterns_found = set(); variable_axis = self.variable_axis_var.get(); base_scenario = self.scenario_search_var.get()
        if variable_axis in all_modifiers:
            for value_tuple in all_modifiers[variable_axis]: patterns_found.add(value_tuple[1])
            
        if len(patterns_found) > 1:
            self.format_filter_frame.grid(); customtkinter.CTkLabel(self.format_filter_frame, text=locales.get_text(self.current_language, "filter_format")).pack(side="left", padx=(10,5), pady=5)
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
        
        # UI: Manage Rank/PB visibility
        if display_mode == "Personal Best":
            children = self.pb_rank_frame.master.winfo_children()
            if children: self.pb_rank_frame.pack(side="left", padx=(0, 5), after=children[0])
            else: self.pb_rank_frame.pack(side="left", padx=(0, 5))
        else:
            self.pb_rank_frame.pack_forget()

        # Data Preparation
        display_data_source = summary_data
        
        if display_mode == "Personal Best":
            try: target_rank = int(self.pb_rank_var.get())
            except ValueError: target_rank = 1
            if target_rank > 1 and self.current_filtered_runs is not None:
                def get_nth_score(group):
                    if len(group) < target_rank: return np.nan
                    return group.nlargest(target_rank).iloc[-1]
                nth_scores = self.current_filtered_runs.groupby(['Scenario', 'Sens'])['Score'].apply(get_nth_score).reset_index()
                nth_scores.rename(columns={'Score': 'PB_Score'}, inplace=True)
                display_data_source = nth_scores
        
        # --- NEW: Percentile Calculation ---
        elif display_mode == "Nth Percentile" and self.current_filtered_runs is not None:
            try: 
                p_val = float(self.percentile_var.get())
                p_val = max(0, min(100, p_val)) / 100.0
            except ValueError: p_val = 0.75
            
            def get_perc(group): return group.quantile(p_val)
            perc_scores = self.current_filtered_runs.groupby(['Scenario', 'Sens'])['Score'].apply(get_perc).reset_index()
            perc_scores.rename(columns={'Score': 'Percentile_Score'}, inplace=True)
            display_data_source = perc_scores
        # -----------------------------------

        value_map = {
            "Personal Best": "PB_Score", 
            "Average Score": "Avg_Score", 
            "Play Count": "Play_Count",
            "Nth Percentile": "Percentile_Score" # Mapped new mode
        }
        display_value_col = value_map.get(display_mode, "PB_Score")

        # Pivot tables
        display_df = display_data_source.pivot_table(index='Scenario', columns='Sens', values=display_value_col).fillna(np.nan)
        
        # highlight_df logic: For "Recent Success", it should contain the target scores (what is currently displayed)
        if display_mode == "Personal Best" and target_rank > 1:
             highlight_df = display_data_source.pivot_table(index='Scenario', columns='Sens', values='PB_Score').fillna(np.nan)
        elif display_mode == "Nth Percentile":
             highlight_df = display_data_source.pivot_table(index='Scenario', columns='Sens', values='Percentile_Score').fillna(np.nan)
        elif display_mode == "Average Score":
             highlight_df = summary_data.pivot_table(index='Scenario', columns='Sens', values='Avg_Score').fillna(np.nan)
        else: # PB or Count
             highlight_df = summary_data.pivot_table(index='Scenario', columns='Sens', values='PB_Score').fillna(np.nan)

        stats_source_df = display_data_source.pivot_table(index='Scenario', columns='Sens', values=display_value_col if display_mode != "Play Count" else 'PB_Score').fillna(np.nan)

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
            self.rating_label.configure(text=locales.get_text(self.current_language, "rating", val=round(rating)))
        else: self.rating_label.configure(text="Rating: -")

        current_scenario = self.scenario_search_var.get()
        current_axis = self.variable_axis_var.get()
        current_recent_entry = {"name": current_scenario, "axis": current_axis}
        if current_scenario and (not self.recents or self.recents[0] != current_recent_entry):
            self.add_to_recents(current_scenario, current_axis)

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
            avg_row_series['Scenario'] = locales.get_text(self.current_language, "avg_row")

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
        
        formatted_columns = []
        for col in grid_data.columns:
            if self.is_float(col): formatted_columns.append(f"{col}cm")
            elif col == "AVG": formatted_columns.append(locales.get_text(self.current_language, "col_avg"))
            elif col == "Best": formatted_columns.append(locales.get_text(self.current_language, "col_best"))
            elif col == "cm": formatted_columns.append(locales.get_text(self.current_language, "col_cm"))
            else: formatted_columns.append(col)

        table_values = [formatted_columns] + values

        self.detailed_stats_cache = {}
        base_df_for_stats = self.current_filtered_runs if self.current_filtered_runs is not None else self.current_family_runs
        if base_df_for_stats is not None:
            for row in grid_data.itertuples(index=False):
                scenario_name = getattr(row, 'Scenario', None)
                if not scenario_name or scenario_name == locales.get_text(self.current_language, "avg_row"): continue
                
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
            
        avg_row_name = locales.get_text(self.current_language, "avg_row")
        is_avg_row_present = avg_row_name in display_df['Scenario'].values
        if is_avg_row_present:
            avg_row_data = display_df[display_df['Scenario'] == avg_row_name]
            if not avg_row_data.empty:
                data_rows = highlight_df[highlight_df.index != avg_row_name]
                highlight_avg_row = data_rows[heatmap_cols].mean()
                highlight_df.loc[avg_row_name, heatmap_cols] = highlight_avg_row

        perf_drop_cols = heatmap_cols
        values_only, global_min, global_max = highlight_df.values, None, None
        
        if mode == "Global Heatmap":
            data_rows = highlight_df[highlight_df.index != avg_row_name]
            all_scores = data_rows[sens_cols].to_numpy().flatten()
            all_scores = all_scores[~np.isnan(all_scores)]
            if all_scores.size > 0:
                global_min, global_max = np.min(all_scores), np.max(all_scores)

        target_score_val, is_target_mode, grid_min_score = 0, mode == "Target Score", 0
        if is_target_mode:
            try:
                target_score_val = float(self.target_score_var.get())
                data_rows = highlight_df[highlight_df.index != avg_row_name]
                all_scores_in_grid = data_rows[sens_cols].to_numpy().flatten()
                all_scores_in_grid = all_scores_in_grid[~np.isnan(all_scores_in_grid)]
                if all_scores_in_grid.size > 0: grid_min_score = np.min(all_scores_in_grid)
            except (ValueError, TypeError): is_target_mode = False

        # --- NEW: Recent Success Logic Prep ---
        is_recent_success_mode = (mode == "Recent Success")
        recent_success_runs = None
        if is_recent_success_mode and self.current_filtered_runs is not None:
            try: days = int(self.recent_success_days_var.get())
            except ValueError: days = 14
            cutoff_date = pd.Timestamp.now() - pd.Timedelta(days=days)
            recent_runs = self.current_filtered_runs[self.current_filtered_runs['Timestamp'] >= cutoff_date]
            # Group by Scenario/Sens and get max score in period
            recent_success_runs = recent_runs.groupby(['Scenario', 'Sens'])['Score'].max()
        # --------------------------------------

        for r_idx, row_data in enumerate(highlight_df.itertuples(index=True)):
            scenario_name = row_data.Index
            
            if is_avg_row_present and scenario_name == avg_row_name:
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
                
                # --- NEW: Recent Success Coloring ---
                elif is_recent_success_mode:
                    if col_name not in sens_cols: continue # Only color sensitivity cells
                    
                    # Logic: Option B (Green if hit target, Red if played but missed, Grey if not played)
                    
                    # Check if played recently at all
                    was_played_recently = False
                    hit_target = False
                    
                    if recent_success_runs is not None:
                        try:
                            # Try to find sens as float
                            s_val = float(col_name)
                            if (scenario_name, s_val) in recent_success_runs.index:
                                was_played_recently = True
                                max_recent_score = recent_success_runs.loc[(scenario_name, s_val)]
                                if max_recent_score >= val: # val is the 'displayed score' (PB, Percentile, etc)
                                    hit_target = True
                        except (ValueError, KeyError): pass

                    if was_played_recently:
                        if hit_target:
                            # Green
                            self.results_table.frame[r_idx + 1, table_col_idx].configure(fg_color="#2e6931")
                        else:
                            # Red (Played but missed)
                            self.results_table.frame[r_idx + 1, table_col_idx].configure(fg_color="#531F1F")
                    else:
                        # Grey (Not played recently) - standard alternating color handled by CTkTable usually, 
                        # but we can leave it transparent/default or dim it.
                        # Since user wants "Grey", the default row color is usually fine.
                        pass
                # ------------------------------------

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
            # Localized Check
            if not scenario_name or scenario_name == locales.get_text(self.current_language, "avg_row"): continue
            
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
                # Localized
                sens_display = locales.get_text(self.current_language, "opt_all") if sens_val == "ALL" else f"{sens_val}cm"
                
                # Localized Tooltips
                text_lines = [f"{scen_name}", locales.get_text(self.current_language, "tooltip_sens", val=sens_display), "-" * 30]
                pb_date_str = stats['pb_date'].strftime('%Y-%m-%d')
                text_lines.append(locales.get_text(self.current_language, "tooltip_pb", val=f"{stats['max']:.1f}", date=pb_date_str))
                text_lines.append(locales.get_text(self.current_language, "tooltip_runs", val=f"{stats['count']}"))
                if 'avg' in stats: 
                    text_lines.append(locales.get_text(self.current_language, "tooltip_avg", val=f"{stats['avg']:.1f} (±{stats.get('std', 0):.1f})"))
                
                p50_text = f"{stats['p50']:.1f}" if 'p50' in stats else "N/A"
                p75_text = f"{stats['p75']:.1f}" if 'p75' in stats else "N/A"
                text_lines.append(locales.get_text(self.current_language, "tooltip_med", val=p50_text, val2=p75_text))

                if 'launchpad_avg' in stats:
                    text_lines.append("-" * 30)
                    text_lines.append(locales.get_text(self.current_language, "tooltip_launchpad", val=f"{stats['launchpad_avg']:.1f}"))
                if 'recent_avg' in stats:
                   text_lines.append(locales.get_text(self.current_language, "tooltip_recent", val=f"{stats['recent_avg']:.1f}"))

                   #commenting out until cooked
                #oracle_msg = stats.get('oracle')
                #if oracle_msg:
                #    text_lines.append("-" * 30)
                    # Oracle messages might need translation too, but they come from engine. 
                    # For now, let's assume they stay English or we update engine later.
                 #   text_lines.append(oracle_msg)
                
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
            # Localized Check
            if not scenario_name or scenario_name == locales.get_text(self.current_language, "avg_row"): continue

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
        win = customtkinter.CTkToplevel(self); win.title(locales.get_text(self.current_language, "manage_hidden")); win.geometry("600x400"); win.transient(self); win.grid_columnconfigure(0, weight=1); win.grid_rowconfigure(1, weight=1)
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

        # Localized
        customtkinter.CTkLabel(self.recently_played_frame, text=locales.get_text(self.current_language, "recently_played"), font=customtkinter.CTkFont(weight="bold")).pack(anchor="w", padx=10)
        recently_played = self._get_recently_played_bases()
        for scen in recently_played:
            selection = {"name": scen, "axis": ""} 
            btn = customtkinter.CTkButton(self.recently_played_frame, text=scen, fg_color="transparent", anchor="w", command=lambda s=selection: self.select_from_list(s))
            btn.pack(fill="x", padx=5)

        # Localized
        customtkinter.CTkLabel(self.favorites_frame, text=locales.get_text(self.current_language, "favorites"), font=customtkinter.CTkFont(weight="bold")).pack(anchor="w", padx=10)
        for fav in self.favorites:
            display_text = f"{fav['name']}" + (f"  [{fav['axis']}]" if fav.get('axis') else "")
            btn = customtkinter.CTkButton(self.favorites_frame, text=display_text, fg_color="transparent", anchor="w", command=lambda f=fav: self.select_from_list(f)); btn.pack(fill="x", padx=5)
        
        # Localized
        customtkinter.CTkLabel(self.recents_frame, text=locales.get_text(self.current_language, "recents"), font=customtkinter.CTkFont(weight="bold")).pack(anchor="w", padx=10)
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
        
        # 1. Build the filters FIRST (This updates self.format_filter_vars to match the new scenario)
        self.build_filters_and_get_data()
        
        # 2. Update Button State
        self.update_fav_button_state()

        # 3. NOW add to recents (Safe to save now, because UI vars match the Scenario Name)
        current_axis = self.variable_axis_var.get()
        current_recent_entry = {"name": base_scenario, "axis": current_axis}
        if not self.recents or self.recents[0] != current_recent_entry:
            self.add_to_recents(base_scenario, current_axis)
        
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
        
        # --- DEFINE HEADER METRICS EARLY ---
        header_metrics = {
            "total_duration_str": self.format_timedelta(total_duration),
            "active_playtime_str": self.format_timedelta(active_playtime),
            "play_density": (active_playtime / total_duration.total_seconds() * 100) if total_duration.total_seconds() > 0 else 0,
            "total_plays_grid": len(session_df),
            "total_plays_scenario": session_df['Scenario'].nunique()
        }
        
        # --- PREPARE DATA FOR GRAPH AND RANKS ---
        relevant_keys = set(zip(session_df['Scenario'], session_df['Sens']))
        relevant_history = history_before_session[history_before_session.set_index(['Scenario', 'Sens']).index.isin(relevant_keys)]

        # 1. PRE-SESSION AVG MAPS (Grid AND Scenario)
        pre_session_avgs_grid = {}
        if not relevant_history.empty:
            pre_session_avgs_grid = relevant_history.groupby(['Scenario', 'Sens'])['Score'].mean().to_dict()
            
        # For Scenario mode, we need history grouped just by Scenario
        # Filter all history for relevant scenarios
        relevant_scenarios = set(session_df['Scenario'])
        hist_scen_only = history_before_session[history_before_session['Scenario'].isin(relevant_scenarios)]
        pre_session_avgs_scen = {}
        if not hist_scen_only.empty:
            pre_session_avgs_scen = hist_scen_only.groupby('Scenario')['Score'].mean().to_dict()
        
        # 2. Rank Logic Helpers
        history_scores_map = defaultdict(list)
        if not relevant_history.empty:
            for (scen, sens), group in relevant_history.groupby(['Scenario', 'Sens']):
                history_scores_map[(scen, sens)] = sorted(group['Score'].tolist())

        rank_definitions = [
            ("SINGULARITY", 100),
            ("ARCADIA", 95),
            ("UBER", 90),
            ("EXALTED", 82),
            ("BLESSED", 75),
            ("TRANSMUTE", 55)
        ]
        gated_ranks = {"SINGULARITY", "ARCADIA", "UBER"}
        min_runs_for_gate = 10 
        session_rank_counts = {name: 0 for name, _ in rank_definitions}
        # ----------------------------------------

        graph_data_grid = []
        graph_data_scenario = []
        
        sorted_session = session_df.sort_values('Timestamp')
        
        # Accumulators
        acc_grid = defaultdict(lambda: {'sum': 0.0, 'count': 0})
        acc_scen = defaultdict(lambda: {'sum': 0.0, 'count': 0})
        
        global_pct_history = [] 
        previous_pulse = 0.0 
        
        for i, row in enumerate(sorted_session.itertuples()):
            # --- GLOBAL METRICS CALCULATION (Based on Grid Performance) ---
            # Note: Global Flow/Pulse usually track the "Grid" performance (most specific context).
            # We calculate the pct stats first to use in global metrics.
            
            key_grid = (row.Scenario, row.Sens)
            base_grid = pre_session_avgs_grid.get(key_grid, 0)
            
            # Update Grid Accumulator
            g_acc = acc_grid[key_grid]
            g_acc['sum'] += row.Score; g_acc['count'] += 1
            curr_avg_grid = g_acc['sum'] / g_acc['count']
            
            # Calc Grid PCT (With Fallback)
            effective_base_grid = base_grid if base_grid > 0 else curr_avg_grid
            if effective_base_grid > 0:
                score_pct_grid = ((row.Score - effective_base_grid) / effective_base_grid) * 100
                trend_pct_grid = ((curr_avg_grid - effective_base_grid) / effective_base_grid) * 100
            else:
                score_pct_grid, trend_pct_grid = 0.0, 0.0

            # Update Global Flow/Pulse using Grid PCT
            global_pct_history.append(score_pct_grid)
            
            try: w_size = int(self.graph_flow_window_var.get())
            except ValueError: w_size = 5
            if w_size < 1: w_size = 5
            
            recent_global = global_pct_history[-w_size:]
            flow_pct = sum(recent_global) / len(recent_global)
            
            k = 0.5
            if i == 0: pulse_pct = score_pct_grid
            else: pulse_pct = (score_pct_grid * k) + (previous_pulse * (1 - k))
            previous_pulse = pulse_pct

            # --- APPEND GRID DATA ---
            graph_data_grid.append({
                'time': row.Timestamp, 
                'pct': score_pct_grid,       
                'trend_pct': trend_pct_grid, 
                'flow_pct': flow_pct,   
                'pulse_pct': pulse_pct, 
                'scenario': row.Scenario, 
                'sens': row.Sens
            })
            
            # --- SCENARIO GRAPH CALCULATION ---
            key_scen = row.Scenario
            base_scen = pre_session_avgs_scen.get(key_scen, 0)
            
            s_acc = acc_scen[key_scen]
            s_acc['sum'] += row.Score; s_acc['count'] += 1
            curr_avg_scen = s_acc['sum'] / s_acc['count']
            
            # Fallback Logic for Scenario
            effective_base_scen = base_scen if base_scen > 0 else curr_avg_scen
            
            if effective_base_scen > 0:
                score_pct_scen = ((row.Score - effective_base_scen) / effective_base_scen) * 100
                trend_pct_scen = ((curr_avg_scen - effective_base_scen) / effective_base_scen) * 100
            else:
                score_pct_scen, trend_pct_scen = 0.0, 0.0
            
            graph_data_scenario.append({
                'time': row.Timestamp, 
                'pct': score_pct_scen,       
                'trend_pct': trend_pct_scen, 
                'flow_pct': flow_pct,   # Use same global flow/pulse
                'pulse_pct': pulse_pct, 
                'scenario': row.Scenario, 
                'sens': row.Sens
            })

            # -- Rank Logic (Unchanged) --
            hist_list = history_scores_map[key_grid]
            current_run_count = len(hist_list) + 1 if hist_list else 1
            
            if hist_list:
                current_pb = hist_list[-1]
                is_singularity = row.Score >= current_pb
                
                idx = bisect.bisect_left(hist_list, row.Score)
                percentile = (idx / len(hist_list)) * 100
                
                if is_singularity:
                    for rank_name, _ in rank_definitions:
                        if current_run_count < min_runs_for_gate and rank_name in gated_ranks: continue
                        session_rank_counts[rank_name] += 1
                else:
                    for rank_name, threshold in rank_definitions:
                        if rank_name == "SINGULARITY": continue
                        if current_run_count < min_runs_for_gate and rank_name in gated_ranks: continue
                        if percentile >= threshold:
                            session_rank_counts[rank_name] += 1
                
                bisect.insort(hist_list, row.Score)
            else:
                history_scores_map[key_grid] = [row.Score]
                for rank_name, _ in rank_definitions:
                    if current_run_count < min_runs_for_gate and rank_name in gated_ranks: continue
                    session_rank_counts[rank_name] += 1

        report_data = {"grid": defaultdict(list), "scenario": defaultdict(list)}
        report_data["rank_counts"] = session_rank_counts
        report_data["rank_gate_val"] = min_runs_for_gate 
        report_data["rank_defs"] = rank_definitions
        
        # --- PBs and Lists Logic (Unchanged) ---
        all_time_grid_stats = self.all_runs_df.groupby(['Scenario', 'Sens'])['Score'].agg(['mean', 'size'])
        prev_grid_pb = history_before_session.groupby(['Scenario', 'Sens'])['Score'].max()
        all_time_scen_stats = self.all_runs_df.groupby('Scenario')['Score'].agg(['mean', 'size'])
        prev_scen_pb = history_before_session.groupby('Scenario')['Score'].max()
        
        total_grid_pbs_count = 0
        total_scen_pbs_count = 0
        
        # Grid Loop
        for (scenario, sens), group in session_df.groupby(['Scenario', 'Sens']):
            session_pb = group['Score'].max()
            is_first_time_grid = (scenario, sens) not in prev_grid_pb.index
            
            prev_pb_val = 0
            is_pb = False
            global_prev_pb = prev_scen_pb.loc[scenario] if scenario in prev_scen_pb.index else 0
            
            if is_first_time_grid:
                if global_prev_pb > 0 and session_pb >= global_prev_pb:
                    is_pb = True
                    prev_pb_val = global_prev_pb
                else:
                    is_pb = False
            else:
                prev_pb_val = prev_grid_pb.loc[(scenario, sens)]
                is_pb = session_pb >= prev_pb_val

            if is_pb: total_grid_pbs_count += 1

            session_avg = group['Score'].mean()
            all_time_avg = all_time_grid_stats.loc[(scenario, sens)]['mean'] if (scenario, sens) in all_time_grid_stats.index else 0
            all_time_count = all_time_grid_stats.loc[(scenario, sens)]['size'] if (scenario, sens) in all_time_grid_stats.index else 0

            item = { "name": scenario, "sens": sens, "play_count": len(group), "first_played": group['Timestamp'].min(), 
                        "session_avg": session_avg, "all_time_avg": all_time_avg, "all_time_play_count": all_time_count,
                        "perf_vs_avg": (session_avg / all_time_avg - 1) * 100 if all_time_avg > 0 else 0, "is_pb": is_pb }
            report_data["grid"]["played"].append(item)
            if not is_first_time_grid: report_data["grid"]["averages"].append(item)
            if is_pb:
                item_pb = item.copy()
                item_pb.update({ "new_score": session_pb, "prev_score": prev_pb_val, "improvement_pts": session_pb - prev_pb_val, "improvement_pct": (session_pb / prev_pb_val - 1) * 100 if prev_pb_val > 0 else float('inf') })
                report_data["grid"]["pbs"].append(item_pb)

        # Scenario Loop
        for scenario, group in session_df.groupby('Scenario'):
            session_pb = group['Score'].max()
            is_first_time_scen = scenario not in prev_scen_pb.index
            prev_pb_val = 0 if is_first_time_scen else prev_scen_pb.loc[scenario]
            is_pb = not is_first_time_scen and session_pb >= prev_pb_val
            if is_pb: total_scen_pbs_count += 1
            
            session_avg = group['Score'].mean()
            all_time_avg = all_time_scen_stats.loc[scenario]['mean'] if scenario in all_time_scen_stats.index else 0
            all_time_count = all_time_scen_stats.loc[scenario]['size'] if scenario in all_time_scen_stats.index else 0
            
            item = { "name": scenario, "play_count": len(group), "first_played": group['Timestamp'].min(), 
                        "session_avg": session_avg, "all_time_avg": all_time_avg, "all_time_play_count": all_time_count,
                        "perf_vs_avg": (session_avg / all_time_avg - 1) * 100 if all_time_avg > 0 else 0, "is_pb": is_pb }
            report_data["scenario"]["played"].append(item)
            if not is_first_time_scen: report_data["scenario"]["averages"].append(item)
            if is_pb:
                item_pb = item.copy()
                item_pb.update({ "new_score": session_pb, "prev_score": prev_pb_val, "improvement_pts": session_pb - prev_pb_val, "improvement_pct": (session_pb / prev_pb_val - 1) * 100 if prev_pb_val > 0 else float('inf') })
                report_data["scenario"]["pbs"].append(item_pb)
        
        header_metrics["total_pbs_grid"] = total_grid_pbs_count
        header_metrics["total_pbs_scenario"] = total_scen_pbs_count

        session_date_str = session_start_time.strftime('%B %d, %Y')
        
        # Return dictionary for graph_data to handle both modes
        graph_data_payload = {
            "grid": graph_data_grid,
            "scenario": graph_data_scenario
        }
        
        return (header_metrics, report_data, session_date_str, graph_data_payload)
    
    def _calculate_and_show_report(self, session_id):
        self.status_label.configure(text="Calculating session report...")
        try:
            data = self._generate_session_payload(session_id)
            if data:
                self.after(0, self._show_session_report_window, session_id, *data)
        finally:
            self.after(0, self.status_label.configure, {"text": "Report ready."})

    def _show_session_report_window(self, session_id, header_metrics, report_data, session_date_str, graph_data):
        self.current_report_window = windows.SessionReportWindow(self, session_id, header_metrics, report_data, session_date_str, graph_data)

    def trigger_report_refresh(self, report_window, session_id):
        self.load_stats_thread()
    
    def _schedule_refresh(self, *args):
        if hasattr(self, '_refresh_job') and self._refresh_job:
            self.after_cancel(self._refresh_job)
        self._refresh_job = self.after(600, self.on_display_option_change)