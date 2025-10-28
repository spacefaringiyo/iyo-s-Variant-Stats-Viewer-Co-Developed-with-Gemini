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
import itertools
from datetime import timedelta
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

customtkinter.set_default_color_theme("blue")

USER_DATA_FILE = "user_data.json"

# --- HELPER CLASS: Tooltip ---
class Tooltip:
    def __init__(self, widget, text_func, bg="#242424", fg="white", delay=400):
        self.widget = widget
        self.text_func = text_func
        self.bg = bg
        self.fg = fg
        self.delay = delay
        self.tooltip_window = None
        self.id = None
        self.widget.bind("<Enter>", self.schedule_tip)
        self.widget.bind("<Leave>", self.hide_tip)
        self.widget.bind("<ButtonPress>", self.hide_tip)

    def schedule_tip(self, event=None):
        self.id = self.widget.after(self.delay, self.show_tip)

    def show_tip(self, event=None):
        if self.tooltip_window: return
        text = self.text_func()
        if not text: return
        
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        self.tooltip_window = tkinter.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        label = tkinter.Label(self.tooltip_window, text=text, justify='left',
                              background=self.bg, foreground=self.fg, relief='solid', borderwidth=1,
                              font=("Arial", 10, "normal"), padx=8, pady=5)
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

# --- WINDOW CLASS: SessionHistoryWindow ---
class SessionHistoryWindow(customtkinter.CTkToplevel):
    def __init__(self, master, session_list):
        super().__init__(master)
        self.title("Session History")
        self.geometry("600x500")
        self.transient(master)

        self.app_master = master

        if not session_list:
            customtkinter.CTkLabel(self, text="No session history found.").pack(expand=True, padx=20, pady=20)
            return

        scroll_frame = customtkinter.CTkScrollableFrame(self)
        scroll_frame.pack(expand=True, fill="both", padx=10, pady=10)

        for i, session in enumerate(session_list):
            card = customtkinter.CTkFrame(scroll_frame, cursor="hand2")
            card.pack(fill="x", pady=(0, 5))
            card.grid_columnconfigure(0, weight=1)

            date_label = customtkinter.CTkLabel(card, text=session['date_str'], font=customtkinter.CTkFont(size=16, weight="bold"), anchor="w")
            date_label.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=(5,0))

            info_text = (f"Duration: {session['total_duration_str']}  |  "
                         f"Plays: {session['play_count']}  |  "
                         f"Top Scenario: {session['top_scenario']}")
            info_label = customtkinter.CTkLabel(card, text=info_text, font=customtkinter.CTkFont(size=12), anchor="w")
            info_label.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=(0,5))
            
            command = lambda event, sid=session['id']: self.app_master.open_session_report(session_id=sid)
            card.bind("<Button-1>", command)
            date_label.bind("<Button-1>", command)
            info_label.bind("<Button-1>", command)


class SessionReportWindow(customtkinter.CTkToplevel):
    def __init__(self, master, header_metrics, report_data, session_date_str):
        super().__init__(master)
        self.title(f"Session Report - {session_date_str}")
        self.geometry("850x700")
        self.transient(master)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        self.app_master = master
        self.header_metrics = header_metrics
        self.report_data = report_data

        header_frame = customtkinter.CTkFrame(self, fg_color=("gray85", "gray20"))
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        header_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        def create_metric_display(parent, title, value, var=None):
            frame = customtkinter.CTkFrame(parent, fg_color="transparent")
            customtkinter.CTkLabel(frame, text=title, font=customtkinter.CTkFont(size=12, weight="bold")).pack()
            label = customtkinter.CTkLabel(frame, text=value, font=customtkinter.CTkFont(size=20), textvariable=var)
            label.pack()
            return frame

        self.total_plays_var = customtkinter.StringVar()
        self.total_pbs_var = customtkinter.StringVar()

        create_metric_display(header_frame, "Total Duration", self.header_metrics["total_duration_str"]).grid(row=0, column=0, pady=10)
        create_metric_display(header_frame, "Active Playtime", self.header_metrics["active_playtime_str"]).grid(row=0, column=1, pady=10)
        create_metric_display(header_frame, "Play Density", f"{self.header_metrics['play_density']:.1f}%").grid(row=0, column=2, pady=10)
        create_metric_display(header_frame, "Total Plays", "", self.total_plays_var).grid(row=0, column=3, pady=10)
        create_metric_display(header_frame, "Total PBs", "", self.total_pbs_var).grid(row=0, column=4, pady=10)
        
        control_frame = customtkinter.CTkFrame(self)
        control_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        control_frame.grid_columnconfigure(1, weight=1)

        customtkinter.CTkButton(control_frame, text="Browse History...", command=self.app_master.open_session_history).pack(side="left", padx=10, pady=5)

        self.summary_toggle_var = customtkinter.StringVar(value="Off")
        customtkinter.CTkSwitch(control_frame, text="Summarize by Scenario", variable=self.summary_toggle_var, onvalue="On", offvalue="Off", command=self._redraw_report).pack(side="right", padx=10, pady=5)
        
        self.sort_var = customtkinter.StringVar(value="performance")
        sort_options = { "Performance": "performance", "Play Count": "play_count", "Order Played": "time", "Alphabetical": "alpha" }
        
        sort_frame = customtkinter.CTkFrame(control_frame, fg_color="transparent")
        sort_frame.pack(side="right", padx=10)
        customtkinter.CTkLabel(sort_frame, text="Sort by:").pack(side="left", padx=(10,5), pady=5)
        for text, value in sort_options.items():
            customtkinter.CTkRadioButton(sort_frame, text=text, variable=self.sort_var, value=value, command=self._redraw_report).pack(side="left", padx=5)

        self.scroll_frame = customtkinter.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        self._redraw_report()

    def _create_collapsible_section(self, parent, title):
        header_frame = customtkinter.CTkFrame(parent, fg_color=("gray75", "gray22"), corner_radius=6)
        header_frame.pack(fill="x", pady=(5, 1))
        content_frame = customtkinter.CTkFrame(parent, fg_color="transparent")
        
        def toggle():
            if content_frame.winfo_viewable(): content_frame.pack_forget(); toggle_button.configure(text="▶")
            else: content_frame.pack(fill="x", padx=10, pady=5); toggle_button.configure(text="▼")

        toggle_button = customtkinter.CTkButton(header_frame, text="▼", width=28, height=28, command=toggle)
        toggle_button.pack(side="left", padx=(5, 0))
        header_label = customtkinter.CTkLabel(header_frame, text=title, font=customtkinter.CTkFont(weight="bold"))
        header_label.pack(side="left", padx=10, pady=5)
        header_frame.bind("<Button-1>", lambda e: toggle()); header_label.bind("<Button-1>", lambda e: toggle())
        content_frame.pack(fill="x", padx=10, pady=5); return content_frame

    def _redraw_report(self):
        for widget in self.scroll_frame.winfo_children(): widget.destroy()
        view_mode = "scenario" if self.summary_toggle_var.get() == "On" else "grid"
        sort_mode = self.sort_var.get()
        data = self.report_data[view_mode]
        self.total_plays_var.set(str(self.header_metrics[f'total_plays_{view_mode}']))
        self.total_pbs_var.set(str(len(data['pbs'])))
        sort_key_map = {"play_count": "play_count", "time": "first_played", "alpha": "name"}
        reverse_sort_map = {"performance": True, "play_count": True, "time": False, "alpha": False}
        data['played'].sort(key=lambda x: x['perf_vs_avg'] if sort_mode == 'performance' else x[sort_key_map.get(sort_mode, 'name')], reverse=reverse_sort_map.get(sort_mode, False))
        data['averages'].sort(key=lambda x: x['perf_vs_avg'] if sort_mode == 'performance' else x[sort_key_map[sort_mode]], reverse=reverse_sort_map.get(sort_mode, False))
        data['pbs'].sort(key=lambda x: x['improvement_pct'] if sort_mode == 'performance' else x[sort_key_map[sort_mode]], reverse=reverse_sort_map.get(sort_mode, False))
        self._populate_played_section(data['played'])
        self._populate_pbs_section(data['pbs'])
        self._populate_averages_section(data['averages'])

    def _populate_played_section(self, played_data):
        parent = customtkinter.CTkFrame(self.scroll_frame, fg_color="transparent"); parent.pack(fill="x")
        content = self._create_collapsible_section(parent, f"Scenarios Played ({len(played_data)})")
        content.grid_columnconfigure((0, 1), weight=1)
        num_items = len(played_data); num_rows = (num_items + 1) // 2
        for i, item in enumerate(played_data):
            name = item['name'] + (f" ({item['sens']}cm)" if 'sens' in item else "")
            name_with_count = f"{name} ({item['play_count']} runs)"
            if item['is_pb']: name_with_count = "🏆 " + name_with_count
            row = i % num_rows; column = i // num_rows
            label = customtkinter.CTkLabel(content, text=name_with_count, font=customtkinter.CTkFont(size=12), anchor="w")
            label.grid(row=row, column=column, sticky="ew", padx=10)

    def _populate_pbs_section(self, pbs_data):
        parent = customtkinter.CTkFrame(self.scroll_frame, fg_color="transparent"); parent.pack(fill="x")
        content = self._create_collapsible_section(parent, f"Personal Bests ({len(pbs_data)})")
        for i, item in enumerate(pbs_data):
            card = customtkinter.CTkFrame(content); card.pack(fill="x", pady=(0, 5))
            card.grid_columnconfigure(1, weight=1)
            name = item['name'] + (f" ({item['sens']}cm)" if 'sens' in item else "")
            customtkinter.CTkLabel(card, text=name, font=customtkinter.CTkFont(size=14, weight="bold"), anchor="w").grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(5,0))
            imp_pts_str = f"{item['improvement_pts']:+.0f} pts"; imp_pct_str = f"({item['improvement_pct']:+.1f}%)"
            customtkinter.CTkLabel(card, text=f"New PB: {item['new_score']:.0f} (vs. {item['prev_score']:.0f})", anchor="w").grid(row=1, column=0, padx=10, pady=(0,5))
            customtkinter.CTkLabel(card, text=f"{imp_pts_str} {imp_pct_str}", text_color="gold", font=customtkinter.CTkFont(weight="bold"), anchor="e").grid(row=1, column=1, padx=10, pady=(0,5))

    def _populate_averages_section(self, averages_data):
        parent = customtkinter.CTkFrame(self.scroll_frame, fg_color="transparent"); parent.pack(fill="x")
        content = self._create_collapsible_section(parent, f"Average Score Comparison ({len(averages_data)})")
        for i, item in enumerate(averages_data):
            card = customtkinter.CTkFrame(content); card.pack(fill="x", pady=(0, 5))
            card.grid_columnconfigure(0, weight=1)
            name = item['name'] + (f" ({item['sens']}cm)" if 'sens' in item else "")
            customtkinter.CTkLabel(card, text=name, font=customtkinter.CTkFont(size=14, weight="bold"), anchor="w").grid(row=0, column=0, sticky="ew", padx=10, pady=(5,0))
            stats_frame = customtkinter.CTkFrame(card, fg_color="transparent"); stats_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0,5))
            stats_frame.grid_columnconfigure((0,1,2), weight=1, uniform="group1")
            session_text = f"Session: {item['session_avg']:.0f} ({item['play_count']} runs)"
            all_time_text = f"All-Time: {item['all_time_avg']:.0f}"
            perf_str = f"{item['perf_vs_avg']:+.1f}%"; perf_color = "lightgreen" if item['perf_vs_avg'] >= 0 else "#F47174"
            customtkinter.CTkLabel(stats_frame, text=session_text, anchor="w").grid(row=0, column=0, sticky="ew", padx=5)
            customtkinter.CTkLabel(stats_frame, text=all_time_text, anchor="center").grid(row=0, column=1, sticky="ew")
            customtkinter.CTkLabel(stats_frame, text=perf_str, font=customtkinter.CTkFont(weight="bold"), text_color=perf_color, anchor="e").grid(row=0, column=2, sticky="ew", padx=5)

class GraphWindow(customtkinter.CTkToplevel):
    def __init__(self, master, full_data, hide_settings, save_callback, graph_id, title):
        super().__init__(master)
        self.title(title)
        self.geometry("950x700")
        self.transient(master)

        self.app_master = master 
        self.full_data = full_data
        self.hide_settings = hide_settings
        self.save_callback = save_callback
        self.graph_id = graph_id
        self.title_text = title
        
        self.view_key_map = {"Raw Data": "raw", "Daily Average": "daily", "Weekly Average": "weekly", "Monthly Average": "monthly", "Session Average": "session"}

        top_control_frame = customtkinter.CTkFrame(self); top_control_frame.pack(fill="x", padx=10, pady=(10,0))
        bottom_control_frame = customtkinter.CTkFrame(self); bottom_control_frame.pack(fill="x", padx=10, pady=(0,5))

        customtkinter.CTkLabel(top_control_frame, text="View Mode:").pack(side="left", padx=(10,5), pady=5)
        self.aggregation_var = customtkinter.StringVar(value="Raw Data")
        aggregation_menu = customtkinter.CTkOptionMenu(top_control_frame, variable=self.aggregation_var,
                                                       values=["Raw Data", "Daily Average", "Weekly Average", "Monthly Average", "Session Average"],
                                                       command=self.on_view_mode_change)
        aggregation_menu.pack(side="left", padx=5, pady=5)
        
        self.raw_display_mode_var = customtkinter.StringVar(value=self.hide_settings.get("raw_display_mode", "Line Plot"))
        self.raw_display_menu = customtkinter.CTkOptionMenu(top_control_frame, variable=self.raw_display_mode_var,
                                                            values=["Line Plot", "Dots Only", "Filled Area"],
                                                            command=self._on_graph_option_change)
        
        customtkinter.CTkLabel(bottom_control_frame, text="Hide scores below:").pack(side="left", padx=(10,5), pady=5)
        self.hide_below_var = customtkinter.StringVar()
        hide_below_entry = customtkinter.CTkEntry(bottom_control_frame, textvariable=self.hide_below_var, width=80)
        hide_below_entry.pack(side="left", padx=5, pady=5)
        hide_below_entry.bind("<Return>", self.update_hide_below)
        
        self.connect_sessions_var = customtkinter.StringVar(value=self.hide_settings.get("connect_sessions", "Off"))
        self.connect_sessions_switch = customtkinter.CTkSwitch(bottom_control_frame, text="Connect Sessions", variable=self.connect_sessions_var, onvalue="On", offvalue="Off", command=self._on_graph_option_change)
        
        self.four_color_cycle_var = customtkinter.StringVar(value=self.hide_settings.get("four_color_cycle", "Off"))
        self.four_color_cycle_switch = customtkinter.CTkSwitch(bottom_control_frame, text="4-Color Cycle", variable=self.four_color_cycle_var, onvalue="On", offvalue="Off", command=self._on_graph_option_change)
        
        self.plot_frame = customtkinter.CTkFrame(self); self.plot_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.fig, self.canvas, self.toolbar = None, None, None
        self.on_view_mode_change() 

    def get_current_hide_key(self):
        mode = self.aggregation_var.get()
        hide_prefix = self.view_key_map.get(mode, "raw")
        return f"{hide_prefix}_hide_below"
        
    def _on_graph_option_change(self, choice=None):
        self.hide_settings["raw_display_mode"] = self.raw_display_mode_var.get()
        self.hide_settings["connect_sessions"] = self.connect_sessions_var.get()
        self.hide_settings["four_color_cycle"] = self.four_color_cycle_var.get()
        self.save_callback()
        self.redraw_plot()

    def on_view_mode_change(self, choice=None):
        hide_key = self.get_current_hide_key()
        current_hide_value = self.hide_settings.get(hide_key, 5)
        self.hide_below_var.set(str(current_hide_value))
        
        if self.aggregation_var.get() == "Raw Data":
            self.raw_display_menu.pack(side="left", padx=5, pady=5)
            self.connect_sessions_switch.pack(side="left", padx=10, pady=5)
            self.four_color_cycle_switch.pack(side="left", padx=10, pady=5)
        else:
            self.raw_display_menu.pack_forget()
            self.connect_sessions_switch.pack_forget()
            self.four_color_cycle_switch.pack_forget()

        self.redraw_plot()

    def update_hide_below(self, event=None):
        hide_key = self.get_current_hide_key()
        try:
            score = float(self.hide_below_var.get())
            self.hide_settings[hide_key] = score
            self.save_callback()
            self.redraw_plot()
        except ValueError:
            self.hide_below_var.set(str(self.hide_settings.get(hide_key, 5)))

    def redraw_plot(self):
        if self.canvas: self.canvas.get_tk_widget().destroy()
        if self.toolbar: self.toolbar.destroy()
        
        hide_key = self.get_current_hide_key()
        try: 
            hide_below_score = float(self.hide_settings.get(hide_key, 5))
        except (ValueError, TypeError): 
            hide_below_score = 5.0
        
        self.visible_data = self.full_data[self.full_data['Score'] >= hide_below_score].copy()

        plt.style.use('dark_background' if customtkinter.get_appearance_mode() == "Dark" else 'seaborn-v0_8-whitegrid')
        self.fig = Figure(figsize=(8, 5), dpi=100)
        ax = self.fig.add_subplot(111)
        mode = self.aggregation_var.get()
        if mode == "Raw Data": self.draw_raw_data_plot(ax)
        else: self.draw_aggregated_plot(ax, mode)
        ax.set_title(self.title_text, fontsize=16); ax.set_ylabel("Score", fontsize=12)
        ax.grid(True, which='both', linestyle='--', linewidth=0.5); self.fig.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame); self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=True)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame); self.toolbar.update()

    def draw_raw_data_plot(self, ax):
        ax.set_xlabel("Run Number", fontsize=12)
        plot_data = self.visible_data.copy()
        if plot_data.empty: return

        plot_data.sort_values(by='Timestamp', inplace=True)
        plot_data.reset_index(drop=True, inplace=True)
        
        display_mode = self.raw_display_mode_var.get()
        connect_sessions = self.connect_sessions_var.get() == "On"
        use_4_color_cycle = self.four_color_cycle_var.get() == "On"

        four_colors = ['#1f77b4', '#ff7f0e', '#2ca0c2', '#d62728']
        rainbow_colors = itertools.cycle(['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f0f', '#bcbd22', '#17becf'])
        unique_sessions = sorted(plot_data['SessionID'].unique())
        
        session_colors = {}
        for i, sid in enumerate(unique_sessions):
            session_colors[sid] = four_colors[i % 4] if use_4_color_cycle else next(rainbow_colors)

        last_point = None
        for session_id in unique_sessions:
            group = plot_data[plot_data['SessionID'] == session_id]
            if group.empty: continue
            color = session_colors[session_id]
            
            plot_x, plot_y = group.index, group['Score']
            
            if connect_sessions and last_point is not None:
                plot_x = pd.Index([last_point[0]]).append(plot_x)
                plot_y = pd.concat([pd.Series([last_point[1]]), plot_y], ignore_index=True)

            if display_mode == "Line Plot":
                ax.plot(plot_x, plot_y, color=color, alpha=0.7)
                ax.scatter(group.index, group['Score'], color=color, s=20, zorder=3)
            elif display_mode == "Dots Only":
                ax.scatter(group.index, group['Score'], color=color, s=20, zorder=3)
            elif display_mode == "Filled Area":
                ax.plot(plot_x, plot_y, color=color, alpha=0.8)
                ax.fill_between(plot_x, plot_y, color=color, alpha=0.3)
                ax.scatter(group.index, group['Score'], color=color, s=20, zorder=3)
            
            last_point = (group.index[-1], group['Score'].iloc[-1])

        min_score, max_score = plot_data['Score'].min(), plot_data['Score'].max()
        padding = (max_score - min_score) * 0.05 if max_score > min_score else 10
        ax.set_ylim(min_score - padding, max_score + padding)
        ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))

        ax2 = ax.twiny()
        ax2.set_xlim(ax.get_xlim())
        date_ticks, date_labels, last_tick_pos = [], [], -np.inf
        min_dist = len(plot_data) * 0.05 
        for i, row in plot_data.iterrows():
            if i - last_tick_pos > min_dist:
                date_ticks.append(i)
                date_labels.append(row['Timestamp'].strftime('%b %d'))
                last_tick_pos = i
        ax2.set_xticks(date_ticks); ax2.set_xticklabels(date_labels, rotation=30, ha='left', fontsize=8)
        ax2.tick_params(axis='x', which='both', length=0)
        ax2.spines['top'].set_visible(False)

    def draw_aggregated_plot(self, ax, mode):
        period_map = {"Daily Average": "D", "Weekly Average": "W", "Monthly Average": "M", "Session Average": "Session"}
        agg_data = engine.aggregate_data(self.visible_data, period=period_map[mode])
        
        if period_map[mode] == "Session":
            agg_data['id'] = agg_data['SessionID'].astype(str)
        else:
            if period_map[mode] == 'D': agg_data['id'] = agg_data['Timestamp'].dt.strftime('%Y-%m-%d')
            elif period_map[mode] == 'W': agg_data['id'] = agg_data['Timestamp'].dt.strftime('%Y-W%U')
            elif period_map[mode] == 'M': agg_data['id'] = agg_data['Timestamp'].dt.strftime('%Y-%m')

        plot_data = agg_data
        if plot_data.empty: return

        self.colors = itertools.cycle(['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f0f', '#bcbd22', '#17becf'])
        bar_color = next(self.colors)
        min_score, max_score = plot_data['Score'].min(), plot_data['Score'].max()
        padding = (max_score - min_score) * 0.05 if max_score > min_score else 10
        ax.set_ylim(min_score - padding, max_score + padding)

        if period_map[mode] == "Session":
            ax.set_xlabel("Session", fontsize=12)
            ax.bar(np.arange(len(plot_data)), plot_data['Score'], color=bar_color)
            ax.set_xticks(np.arange(len(plot_data)))
            ax.set_xticklabels([f"S{int(sid)}" for sid in plot_data['SessionID']], rotation=45, ha='right')
        else:
            ax.set_xlabel("Date", fontsize=12)
            ax.bar(plot_data['Timestamp'], plot_data['Score'], width=self.get_bar_width(period_map[mode]), color=bar_color)
            self.fig.autofmt_xdate()
        
    def get_bar_width(self, period):
        if period == 'D': return 0.8
        if period == 'W': return 5
        if period == 'M': return 20
        return 1

# --- Main App Class ---
class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.is_first_load = True
        self.all_runs_df, self.scenario_list = None, []
        self.results_table, self.current_family_runs, self.current_summary_data = None, None, None
        
        self.variable_axis_var, self.sens_filter_var = customtkinter.StringVar(), customtkinter.StringVar(value="All")
        self.grid_display_mode_var = customtkinter.StringVar(value="Personal Best")
        self.highlight_mode_var, self.show_decimals_var = customtkinter.StringVar(value="Performance Drop"), customtkinter.StringVar(value="Off")
        self.cell_height_var = customtkinter.StringVar(value="28")
        self.appearance_mode_var = customtkinter.StringVar(value="System") # --- ADDED ---
        self.font_size_var = customtkinter.StringVar(value="12")
        
        self.target_score_var = customtkinter.StringVar(value="3000")
        self.session_gap_minutes_var = customtkinter.StringVar(value="30")
        self.target_scores_by_scenario, self.format_filter_vars, self.format_filter_preferences = {}, {}, {}
        self.favorites, self.recents, self.collapsed_states = [], [], {}
        self.hidden_scenarios, self.hidden_cms = set(), set()
        self.graph_hide_settings = {}
        self.tooltip_instances = []

        self.load_user_data() # Load user data first
        customtkinter.set_appearance_mode(self.appearance_mode_var.get()) # Apply theme before creating widgets
        
        self.title("iyo's Variant Stats Viewer co-developed with Gemini")
        if hasattr(self, 'saved_geometry') and self.saved_geometry:
            self.geometry(self.saved_geometry)
        else:
            self.geometry("1400x950")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1); self.grid_columnconfigure(0, weight=1)
        self.bind("<F5>", lambda event: self.load_stats_thread())
        self.top_frame = customtkinter.CTkFrame(self, corner_radius=0); self.top_frame.grid(row=0, column=0, sticky="new"); self.top_frame.grid_columnconfigure(0, weight=1)
        self.bottom_frame = customtkinter.CTkFrame(self); self.bottom_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10); self.bottom_frame.grid_columnconfigure(0, weight=1); self.bottom_frame.grid_rowconfigure(1, weight=1)
        self.rating_frame = customtkinter.CTkFrame(self.bottom_frame); self.rating_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(0, 5)); self.rating_frame.grid_columnconfigure(0, weight=1)
        self.rating_label = customtkinter.CTkLabel(self.rating_frame, text="Rating: -", font=("Arial", 24, "bold")); self.rating_label.grid(row=0, column=0, pady=10); self.rating_frame.grid_remove()
        self._build_path_and_load_controls()
        self.set_default_path()
        self.after(100, self.load_stats_thread)
    
    def load_user_data(self):
        if os.path.exists(USER_DATA_FILE):
            try:
                with open(USER_DATA_FILE, 'r') as f: data = json.load(f)
                self.saved_geometry = data.get("window_geometry")
                self.appearance_mode_var.set(data.get("appearance_mode", "System")) # --- ADDED ---
                self.favorites = [{"name": fav, "axis": ""} if isinstance(fav, str) else fav for fav in data.get("favorites", [])]
                self.recents = [{"name": rec, "axis": ""} if isinstance(rec, str) else rec for rec in data.get("recents", [])]
                self.sens_filter_var.set(data.get("sens_filter_preference", "All"))
                self.grid_display_mode_var.set(data.get("grid_display_mode_preference", "Personal Best"))
                self.highlight_mode_var.set(data.get("highlight_mode_preference", "Performance Drop"))
                self.show_decimals_var.set(data.get("show_decimals_preference", "Off"))
                self.cell_height_var.set(str(data.get("cell_height_preference", "28")))
                self.font_size_var.set(str(data.get("font_size_preference", "12")))
                self.session_gap_minutes_var.set(str(data.get("session_gap_minutes", "30")))
                self.target_scores_by_scenario = data.get("target_scores_by_scenario", {})
                self.collapsed_states = data.get("collapsed_states", {})
                self.hidden_scenarios = set(data.get("hidden_scenarios", [])); self.hidden_cms = set(data.get("hidden_cms", []))
                self.format_filter_preferences = data.get("format_filter_preferences", {})
                self.graph_hide_settings = data.get("graph_hide_settings", {})
                self.collapsed_states['main_controls'] = False
            except (json.JSONDecodeError, AttributeError): 
                self.favorites,self.recents,self.collapsed_states,self.target_scores_by_scenario,self.format_filter_preferences = [],[],{},{},{}
                self.hidden_scenarios,self.hidden_cms,self.graph_hide_settings = set(),set(),{}
    
    def save_user_data(self):
        current_scenario = self.scenario_search_var.get()
        if current_scenario:
            self.target_scores_by_scenario[current_scenario] = self.target_score_var.get()
            variable_axis = self.variable_axis_var.get()
            if variable_axis:
                unchecked_patterns = [p for p, v in self.format_filter_vars.items() if not v.get()]
                if current_scenario not in self.format_filter_preferences: self.format_filter_preferences[current_scenario] = {}
                if unchecked_patterns: self.format_filter_preferences[current_scenario][variable_axis] = unchecked_patterns
                elif variable_axis in self.format_filter_preferences.get(current_scenario, {}): del self.format_filter_preferences[current_scenario][variable_axis]
                if not self.format_filter_preferences.get(current_scenario): del self.format_filter_preferences[current_scenario]
        data_to_save = {
            "window_geometry": self.geometry(),
            "appearance_mode": self.appearance_mode_var.get(), # --- ADDED ---
            "favorites": self.favorites, "recents": self.recents, "sens_filter_preference": self.sens_filter_var.get(), 
            "grid_display_mode_preference": self.grid_display_mode_var.get(),
            "highlight_mode_preference": self.highlight_mode_var.get(), "show_decimals_preference": self.show_decimals_var.get(),
            "cell_height_preference": self.cell_height_var.get(), "font_size_preference": self.font_size_var.get(),
            "session_gap_minutes": self.session_gap_minutes_var.get(),
            "target_scores_by_scenario": self.target_scores_by_scenario, "collapsed_states": self.collapsed_states, 
            "hidden_scenarios": list(self.hidden_scenarios), "hidden_cms": list(self.hidden_cms), 
            "format_filter_preferences": self.format_filter_preferences, 
            "graph_hide_settings": self.graph_hide_settings,
        }
        with open(USER_DATA_FILE, 'w') as f: json.dump(data_to_save, f, indent=2)

    def on_cell_click(self, event, scenario_name, sensitivity):
        if self.all_runs_df is None or self.all_runs_df.empty: return
        sensitivity = float(sensitivity)
        graph_id = f"{scenario_name}|{sensitivity}"
        if graph_id not in self.graph_hide_settings:
            self.graph_hide_settings[graph_id] = {}
        hide_settings_for_graph = self.graph_hide_settings[graph_id]
        
        history_data = self.all_runs_df[(self.all_runs_df['Scenario'] == scenario_name) & (self.all_runs_df['Sens'] == sensitivity)].copy()
        history_data.sort_values(by='Timestamp', inplace=True)
        if history_data.empty:
            msg_win = customtkinter.CTkToplevel(self); msg_win.transient(self); msg_win.title("Info"); msg_win.geometry("300x100")
            customtkinter.CTkLabel(msg_win, text=f"No historical data for\n{scenario_name}\nat {sensitivity}cm.", justify="center").pack(expand=True, padx=20, pady=20)
            return
        history_data['unique_id'] = history_data.apply(lambda row: f"{row['Timestamp'].isoformat()}|{row['Score']}", axis=1)
        title = f"History: {scenario_name} at {sensitivity}cm"
        GraphWindow(self, full_data=history_data, hide_settings=hide_settings_for_graph, save_callback=self.save_user_data, graph_id=graph_id, title=title)
        
    def on_scenario_name_click(self, event, scenario_name):
        if self.all_runs_df is None or self.all_runs_df.empty: return
        
        graph_id = f"{scenario_name}|ALL"
        if graph_id not in self.graph_hide_settings:
            self.graph_hide_settings[graph_id] = {}
        hide_settings_for_graph = self.graph_hide_settings[graph_id]
        
        history_data = self.all_runs_df[self.all_runs_df['Scenario'] == scenario_name].copy()
        history_data.sort_values(by='Timestamp', inplace=True)
        
        if history_data.empty:
            msg_win = customtkinter.CTkToplevel(self); msg_win.transient(self); msg_win.title("Info"); msg_win.geometry("300x100")
            customtkinter.CTkLabel(msg_win, text=f"No historical data for\n{scenario_name}.", justify="center").pack(expand=True, padx=20, pady=20)
            return
            
        history_data['unique_id'] = history_data.apply(lambda row: f"{row['Timestamp'].isoformat()}|{row['Score']}", axis=1)
        title = f"History: {scenario_name} (All Sensitivities)"
        GraphWindow(self, full_data=history_data, hide_settings=hide_settings_for_graph, save_callback=self.save_user_data, graph_id=graph_id, title=title)
        
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

    def on_load_complete(self, all_runs_df):
        self.progress_bar.grid_remove()
        if not hasattr(self, 'main_controls_content'): self._build_main_ui_controls()
        
        if all_runs_df is not None and not all_runs_df.empty and 'Duration' in all_runs_df.columns:
            self.all_runs_df = all_runs_df
            unique_scenarios = self.all_runs_df['Scenario'].unique()
            
            potential_bases = {s for s in unique_scenarios if any(other.startswith(s + ' ') for other in unique_scenarios)}
            base_scenarios = {b for b in potential_bases if not any(b.startswith(p + ' ') for p in potential_bases)}
            standalone_scenarios = {s for s in unique_scenarios if not any(s.startswith(b + ' ') for b in base_scenarios)}
            self.scenario_list = sorted(list(base_scenarios.union(standalone_scenarios)))

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
            else: self.update_grid()
        else:
            if all_runs_df is None: self.status_label.configure(text="Load failed or no data found.")
            else: self.status_label.configure(text="Data loaded, but is missing 'Duration'. Please Refresh Stats (F5).")
            self.all_runs_df, self.scenario_list = None, []
            self.session_report_button.configure(state="disabled")
            self.session_history_button.configure(state="disabled")
        self.load_button.configure(state="normal"); self.select_path_button.configure(state="normal")
        
    def format_timedelta(self, td):
        if isinstance(td, (int, float)): td = timedelta(seconds=td)
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f'{hours:02}:{minutes:02}:{seconds:02}'
        
    def open_session_history(self):
        if self.all_runs_df is None or self.all_runs_df.empty or 'SessionID' not in self.all_runs_df.columns:
            return

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
        SessionHistoryWindow(self, summary_list)

    def open_session_report(self, event=None, session_id=None):
        if self.all_runs_df is None or self.all_runs_df.empty:
            return
        
        self.status_label.configure(text="Calculating session report...")
        thread = threading.Thread(target=self._calculate_and_show_report, args=(session_id,))
        thread.daemon = True
        thread.start()

    def _calculate_and_show_report(self, session_id):
        try:
            if self.all_runs_df is None or 'SessionID' not in self.all_runs_df.columns:
                return

            if session_id is None:
                session_id = self.all_runs_df['SessionID'].max()
            
            session_df = self.all_runs_df[self.all_runs_df['SessionID'] == session_id].copy()
            if session_df.empty: return

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
            
            report_data = {"grid": defaultdict(list), "scenario": defaultdict(list)}

            all_time_grid_avg = self.all_runs_df.groupby(['Scenario', 'Sens'])['Score'].mean()
            prev_grid_pb = history_before_session.groupby(['Scenario', 'Sens'])['Score'].max()
            all_time_scen_avg = self.all_runs_df.groupby('Scenario')['Score'].mean()
            prev_scen_pb = history_before_session.groupby('Scenario')['Score'].max()
            
            for (scenario, sens), group in session_df.groupby(['Scenario', 'Sens']):
                prev_pb = prev_grid_pb.get((scenario, sens), 0)
                session_pb = group['Score'].max()
                is_pb = session_pb > prev_pb
                session_avg = group['Score'].mean()
                all_time_avg = all_time_grid_avg.get((scenario, sens), 0)
                item = { "name": scenario, "sens": sens, "play_count": len(group), "first_played": group['Timestamp'].min(), "session_avg": session_avg, "all_time_avg": all_time_avg, "perf_vs_avg": (session_avg / all_time_avg - 1) * 100 if all_time_avg > 0 else 0, "is_pb": is_pb }
                report_data["grid"]["played"].append(item); report_data["grid"]["averages"].append(item)
                if is_pb:
                    item_pb = item.copy()
                    item_pb.update({ "new_score": session_pb, "prev_score": prev_pb, "improvement_pts": session_pb - prev_pb, "improvement_pct": (session_pb / prev_pb - 1) * 100 if prev_pb > 0 else float('inf') })
                    report_data["grid"]["pbs"].append(item_pb)

            for scenario, group in session_df.groupby('Scenario'):
                prev_pb = prev_scen_pb.get(scenario, 0)
                session_pb = group['Score'].max()
                is_pb = session_pb > prev_pb
                session_avg = group['Score'].mean()
                all_time_avg = all_time_scen_avg.get(scenario, 0)
                item = { "name": scenario, "play_count": len(group), "first_played": group['Timestamp'].min(), "session_avg": session_avg, "all_time_avg": all_time_avg, "perf_vs_avg": (session_avg / all_time_avg - 1) * 100 if all_time_avg > 0 else 0, "is_pb": is_pb }
                report_data["scenario"]["played"].append(item); report_data["scenario"]["averages"].append(item)
                if is_pb:
                    item_pb = item.copy()
                    item_pb.update({ "new_score": session_pb, "prev_score": prev_pb, "improvement_pts": session_pb - prev_pb, "improvement_pct": (session_pb / prev_pb - 1) * 100 if prev_pb > 0 else float('inf') })
                    report_data["scenario"]["pbs"].append(item_pb)
            
            session_date_str = session_start_time.strftime('%B %d, %Y')
            self.after(0, self._show_session_report_window, header_metrics, report_data, session_date_str)
        finally:
            self.after(0, self.status_label.configure, {"text": "Report ready."})

    def _show_session_report_window(self, header_metrics, report_data, session_date_str):
        SessionReportWindow(self, header_metrics, report_data, session_date_str)
    
    def _build_main_ui_controls(self):
        self.main_controls_header, self.main_controls_content = self._create_collapsible_section("Options & Analysis", "main_controls", 1); self.main_controls_content.grid_columnconfigure(0, weight=1)
        selection_content_frame = customtkinter.CTkFrame(self.main_controls_content); selection_content_frame.grid(row=0, column=0, sticky="ew", pady=(0,5)); selection_content_frame.grid_columnconfigure(0, weight=1)
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
        
        display_top_row_frame = customtkinter.CTkFrame(self.main_controls_content); display_top_row_frame.grid(row=1, column=0, sticky="ew"); display_top_row_frame.grid_columnconfigure((0, 1, 2), weight=1, uniform="group1")
        sens_filter_group = customtkinter.CTkFrame(display_top_row_frame); sens_filter_group.grid(row=0, column=0, padx=(0,5), pady=5, sticky="ew")
        customtkinter.CTkLabel(sens_filter_group, text="Sensitivity Filter:").pack(side="left", padx=(10,5), pady=5); customtkinter.CTkRadioButton(sens_filter_group, text="All", variable=self.sens_filter_var, value="All", command=self.on_display_option_change).pack(side="left", padx=5, pady=5); customtkinter.CTkRadioButton(sens_filter_group, text="5cm Inc.", variable=self.sens_filter_var, value="5cm", command=self.on_display_option_change).pack(side="left", padx=5, pady=5); customtkinter.CTkRadioButton(sens_filter_group, text="10cm Inc.", variable=self.sens_filter_var, value="10cm", command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        
        session_group = customtkinter.CTkFrame(display_top_row_frame); session_group.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        customtkinter.CTkLabel(session_group, text="Session Gap (min):").pack(side="left", padx=(10, 5));
        customtkinter.CTkEntry(session_group, textvariable=self.session_gap_minutes_var, width=50).pack(side="left")
        customtkinter.CTkLabel(session_group, text="(Requires Refresh)", font=customtkinter.CTkFont(size=10, slant="italic")).pack(side="left", padx=(5,10));
        
        misc_group = customtkinter.CTkFrame(display_top_row_frame); misc_group.grid(row=0, column=2, padx=(5,0), pady=5, sticky="ew")
        misc_group.grid_columnconfigure(0, weight=1)
        top_misc_frame = customtkinter.CTkFrame(misc_group, fg_color="transparent")
        top_misc_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        # --- MODIFIED: Added theme selector ---
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
        
        # This is where we create the "Grid Display Mode / Highlight Mode" section
        analysis_modes_frame = customtkinter.CTkFrame(self.top_frame)
        analysis_modes_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(5,5))
        analysis_modes_frame.grid_columnconfigure((0, 1), weight=1)

        # THIS IS THE FIX: We tell the top_frame grid how to handle empty space
        self.top_frame.grid_rowconfigure(4, weight=1)

        grid_mode_frame = customtkinter.CTkFrame(analysis_modes_frame); grid_mode_frame.grid(row=0, column=0, sticky="ew", padx=(0,5))
        customtkinter.CTkLabel(grid_mode_frame, text="Grid Display Mode:").pack(side="left", padx=(10,5), pady=5)
        modes = ["Personal Best", "Average Score", "Play Count"]
        for mode in modes:
            customtkinter.CTkRadioButton(grid_mode_frame, text=mode, variable=self.grid_display_mode_var, value=mode, command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        
        highlight_group = customtkinter.CTkFrame(analysis_modes_frame); highlight_group.grid(row=0, column=1, sticky="ew", padx=(5,0))
        customtkinter.CTkLabel(highlight_group, text="Highlight Mode:").pack(side="left", padx=(10,5), pady=5)
        h_modes = {"None": "None", "Perf. Drop": "Performance Drop", "Row Heatmap": "Row Heatmap", "Global Heatmap": "Global Heatmap", "Target Score": "Target Score"}
        for text, val in h_modes.items():
             customtkinter.CTkRadioButton(highlight_group, text=text, variable=self.highlight_mode_var, value=val, command=self.on_display_option_change).pack(side="left", padx=5, pady=5)
        self.target_score_entry = customtkinter.CTkEntry(highlight_group, textvariable=self.target_score_var, width=80); self.target_score_entry.pack(side="left", padx=(0,10), pady=5); self.target_score_entry.bind("<Return>", self.on_display_option_change)
        
        self._apply_initial_collapse_state(); self.on_display_option_change()
        
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
        # Redraw any open graph windows to match the new theme
        for child in self.winfo_children():
            if isinstance(child, GraphWindow):
                child.redraw_plot()
        self.save_user_data(); self.display_grid_data()
        
    def load_stats_thread(self):
        stats_path = self.path_entry.get()
        if not stats_path or not os.path.isdir(stats_path): return
        self.status_label.configure(text="Loading stats, please wait..."); self.load_button.configure(state="disabled"); self.select_path_button.configure(state="disabled")
        self.progress_bar.grid(row=4, column=0, columnspan=2, sticky="ew", padx=10, pady=(0,10)); self.progress_bar.start()
        thread = threading.Thread(target=self.perform_load, args=(stats_path,)); thread.daemon = True; thread.start()
        
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
            self.current_summary_data = pd.DataFrame()
        else:
            filtered_df = pd.DataFrame(filtered_rows)
            self.current_summary_data = filtered_df.groupby(['Scenario', 'Sens']).agg(
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

        if self.results_table:
            self.results_table.destroy()

        if self.current_summary_data is None or self.current_summary_data.empty:
            self.rating_frame.grid_remove()
            return
            
        self.rating_frame.grid()
        summary_data = self.current_summary_data.copy()

        try:
            cell_height = int(self.cell_height_var.get())
        except (ValueError, TypeError):
            cell_height = 28
        try:
            font_size = int(self.font_size_var.get())
        except (ValueError, TypeError):
            font_size = 12

        display_mode = self.grid_display_mode_var.get()
        value_map = {"Personal Best": "PB_Score", "Average Score": "Avg_Score", "Play Count": "Play_Count"}
        display_value_col = value_map[display_mode]
        highlight_value_col = value_map["Average Score"] if display_mode == "Average Score" else value_map["Personal Best"]

        display_df = summary_data.pivot_table(index='Scenario', columns='Sens', values=display_value_col).fillna(np.nan)
        highlight_df = summary_data.pivot_table(index='Scenario', columns='Sens', values=highlight_value_col).fillna(np.nan)
        pb_df = summary_data.pivot_table(index='Scenario', columns='Sens', values='PB_Score').fillna(np.nan)
        
        if self.hidden_cms:
            cols_to_drop = [c for c in display_df.columns if str(c) in self.hidden_cms]
            display_df.drop(columns=cols_to_drop, inplace=True, errors='ignore')
            highlight_df.drop(columns=cols_to_drop, inplace=True, errors='ignore')
            pb_df.drop(columns=cols_to_drop, inplace=True, errors='ignore')

        sens_filter = self.sens_filter_var.get()
        if sens_filter != "All":
            increment = 5 if sens_filter == "5cm" else 10
            sens_cols_str = [c for c in display_df.columns if self.is_float(c)]
            cols_to_keep = [c for c in sens_cols_str if float(c) % increment == 0]
            display_df = display_df[cols_to_keep]
            highlight_df = highlight_df[cols_to_keep]
            pb_df = pb_df[cols_to_keep]
            
        if display_df.empty: self.rating_frame.grid_remove(); return

        pb_df['Best'] = pb_df.max(axis=1)
        pb_df['cm'] = pb_df.idxmax(axis=1)
        base_scenario = self.scenario_search_var.get()
        base_pb_score = pb_df.loc[base_scenario, 'Best'] if base_scenario in pb_df.index else 1.0
        if pd.isna(base_pb_score) or base_pb_score == 0: base_pb_score = 1.0
        pb_df['%'] = (pb_df['Best'] / base_pb_score * 100)
        
        grid_data = display_df.join(pb_df[['Best', 'cm', '%']])

        sens_cols_for_rating = [c for c in grid_data.columns if self.is_float(c)]
        if sens_cols_for_rating and not grid_data.empty and display_mode != "Play Count":
            numeric_data_rating = grid_data[sens_cols_for_rating].apply(pd.to_numeric, errors='coerce').fillna(0)
            rating = numeric_data_rating.sum().sum() / (len(grid_data) * len(sens_cols_for_rating)) if len(grid_data) * len(sens_cols_for_rating) > 0 else 0
            self.rating_label.configure(text=f"Rating: {round(rating)}")
        else: self.rating_label.configure(text="Rating: -")

        avg_row_series = None
        sens_cols_for_avg = [c for c in pb_df.columns if self.is_float(c)]
        if sens_cols_for_avg and not pb_df.empty:
            column_averages = pb_df[sens_cols_for_avg].apply(pd.to_numeric, errors='coerce').mean()
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

        current_scenario = self.scenario_search_var.get(); current_axis = self.variable_axis_var.get()
        current_recent_entry = {"name": current_scenario, "axis": current_axis}
        if current_scenario and (not self.recents or self.recents[0] != current_recent_entry): self.add_to_recents(current_scenario, current_axis)

        grid_data.reset_index(inplace=True)
        
        def get_sort_key(scenario_name):
            if scenario_name == base_scenario: return 100.0
            modifier_str = scenario_name.replace(base_scenario, '').strip()
            numbers = re.findall(r'(\d+\.?\d*)', modifier_str)
            return float(numbers[-1]) if numbers else 999.0
        
        grid_data['sort_key'] = grid_data['Scenario'].apply(get_sort_key); grid_data.sort_values(by='sort_key', inplace=True); grid_data.drop(columns='sort_key', inplace=True)
        
        sens_cols_for_avg = [c for c in grid_data.columns if self.is_float(c)]
        if sens_cols_for_avg: grid_data['AVG'] = grid_data[sens_cols_for_avg].apply(pd.to_numeric, errors='coerce').mean(axis=1)
        else: grid_data['AVG'] = np.nan
        
        if avg_row_series is not None:
             grid_data = pd.concat([avg_row_series.to_frame().T, grid_data], ignore_index=True)
        
        grid_data = grid_data.fillna('')
        cols = grid_data.columns.tolist()
        summary_cols = ['AVG', 'Best', 'cm', '%']
        sens_cols = sorted([c for c in cols if self.is_float(c)], key=float)
        final_col_order = ['Scenario'] + sens_cols + summary_cols
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
        self.results_table = CTkTable(self.bottom_frame, values=table_values, 
                                      header_color=("gray80", "gray25"),
                                      font=("Arial", font_size))
        self.results_table.grid(row=1, column=0, sticky="new", padx=5, pady=5)

        for r in range(self.results_table.rows):
            for c in range(self.results_table.columns):
                cell = self.results_table.frame.get((r, c))
                if cell:
                    cell.configure(height=cell_height)

        if 'Scenario' in final_col_order: self.results_table.edit_column(0, width=350)
        
        self.bind_graph_events(grid_data)
        self.bind_hide_events(table_values)
        self.bind_tooltips(grid_data)
        self.apply_highlighting(highlight_df, grid_data)

    def apply_highlighting(self, highlight_df, display_df):
        mode = self.highlight_mode_var.get()
        if mode == "None" or highlight_df.empty: return
        
        highlight_df = highlight_df.reindex(index=display_df['Scenario'].values).fillna(np.nan)

        pb_df = self.current_summary_data.pivot_table(index='Scenario', columns='Sens', values='PB_Score').fillna(np.nan)
        pb_df = pb_df.reindex(index=display_df['Scenario'].values)
        highlight_df['Best'] = pb_df.max(axis=1)

        heatmap_cols = [c for c in highlight_df.columns if self.is_float(c)] + ['Best']
        if heatmap_cols:
            highlight_df['AVG'] = highlight_df[[c for c in highlight_df.columns if self.is_float(c)]].apply(pd.to_numeric, errors='coerce').mean(axis=1)
            heatmap_cols.append('AVG')
            
        is_avg_row_present = '-- Averages --' in display_df['Scenario'].values
        if is_avg_row_present:
            avg_row_data = display_df[display_df['Scenario'] == '-- Averages --']
            if not avg_row_data.empty:
                highlight_avg_row = highlight_df[highlight_df.index != '-- Averages --'][heatmap_cols].mean()
                highlight_df.loc['-- Averages --'] = highlight_avg_row

        perf_drop_cols = heatmap_cols
            
        values_only, global_min, global_max = highlight_df.values, None, None
        
        if mode == "Global Heatmap":
            all_scores = highlight_df[highlight_df.index != '-- Averages --'][heatmap_cols].to_numpy().flatten()
            all_scores = all_scores[~np.isnan(all_scores)]
            if all_scores.size > 0:
                global_min, global_max = np.min(all_scores), np.max(all_scores)

        target_score_val, is_target_mode, grid_min_score = 0, mode == "Target Score", 0
        if is_target_mode:
            try:
                target_score_val = float(self.target_score_var.get())
                all_scores_in_grid = highlight_df[highlight_df.index != '-- Averages --'][heatmap_cols].to_numpy().flatten()
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
                    if pd.isna(val):
                        continue
                except (ValueError, TypeError, IndexError):
                    continue

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
                    row_scores = [float(cell) for c, cell in enumerate(row_data[1:]) if highlight_df.columns[c] in heatmap_cols and pd.notna(cell)]
                    if len(row_scores) < 2: continue
                    min_score, max_score = min(row_scores), max(row_scores)
                    if min_score == max_score: continue
                    norm = (val - min_score) / (max_score - min_score); self.results_table.frame[r_idx + 1, table_col_idx].configure(fg_color=self.get_heatmap_color(norm))
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
        if not self.results_table or grid_data.empty or self.current_summary_data is None: return
        
        indexed_summary = self.current_summary_data.set_index(['Scenario', 'Sens'])
        
        for r_idx, row in enumerate(grid_data.itertuples(index=False)):
            scenario_name = getattr(row, 'Scenario', None)
            if not scenario_name or scenario_name == '-- Averages --': continue

            for c_idx, col_name in enumerate(grid_data.columns):
                if self.is_float(col_name):
                    cell_widget = self.results_table.frame[r_idx + 1, c_idx]
                    
                    def make_text_func(s_name, s_sens):
                        def get_tooltip_text():
                            try:
                                stats = indexed_summary.loc[(s_name, float(s_sens))]
                                pb = stats.get('PB_Score', 0)
                                avg = stats.get('Avg_Score', 0)
                                count = stats.get('Play_Count', 0)
                                return (f"PB: {pb:.1f}\n"
                                        f"Avg: {avg:.1f}\n"
                                        f"Runs: {count}")
                            except (KeyError, TypeError):
                                return ""
                        return get_tooltip_text

                    tooltip = Tooltip(cell_widget, make_text_func(scenario_name, col_name))
                    self.tooltip_instances.append(tooltip)

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
        
    def hide_cm(self, cm_value): self.hidden_cms.add(str(cm_value)); self.save_user_data(); self.display_grid_data()
    
    def hide_scenario(self, scenario_name): self.hidden_scenarios.add(scenario_name); self.save_user_data(); self.build_filters_and_get_data()
    
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
        self.save_user_data()
        self._populate_manage_hidden_window(tabview)
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
        if not base_scenario or self.all_runs_df is None: return
        saved_target = self.target_scores_by_scenario.get(base_scenario, "3000")
        self.target_score_var.set(saved_target)
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
        
    def perform_load(self, stats_path):
        try: gap_minutes = int(self.session_gap_minutes_var.get())
        except (ValueError, TypeError): gap_minutes = 30
        all_runs_df = engine.find_and_process_stats(stats_path, session_gap_minutes=gap_minutes)
        self.after(0, self.on_load_complete, all_runs_df)

if __name__ == "__main__":
    app = App()
    app.mainloop()