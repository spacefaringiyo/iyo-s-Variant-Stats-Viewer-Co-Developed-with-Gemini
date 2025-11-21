import customtkinter
import tkinter
import engine
import pandas as pd
import numpy as np
import itertools
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from datetime import timedelta

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
    def __init__(self, master, session_id, header_metrics, report_data, session_date_str, graph_data):
        super().__init__(master)
        self.title(f"Session Report - {session_date_str}")
        
        if hasattr(master, 'session_report_geometry') and master.session_report_geometry:
            self.geometry(master.session_report_geometry)
        else:
            self.geometry("900x800")
        
        self.transient(master)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        self.app_master = master
        self.session_id = session_id
        self.header_metrics = header_metrics
        self.report_data = report_data
        self.graph_data = graph_data
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<F5>", self.request_refresh)

        self.header_frame = customtkinter.CTkFrame(self, fg_color=("gray85", "gray20"))
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.header_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        self.total_plays_var = customtkinter.StringVar()
        self.total_pbs_var = customtkinter.StringVar()
        self._draw_header_metrics()

        control_frame = customtkinter.CTkFrame(self)
        control_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        control_frame.grid_columnconfigure(1, weight=1)

        customtkinter.CTkButton(control_frame, text="Browse History...", command=self.app_master.open_session_history).pack(side="left", padx=10, pady=5)
        customtkinter.CTkButton(control_frame, text="Refresh (F5)", width=100, command=self.request_refresh).pack(side="left", padx=0, pady=5)

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

        self._draw_performance_graph()
        self._redraw_report()

    def on_close(self):
        self.app_master.session_report_geometry = self.geometry()
        self.app_master.save_user_data()
        self.destroy()

    def request_refresh(self, event=None):
        if hasattr(self.app_master, 'trigger_report_refresh'):
            self.app_master.trigger_report_refresh(self, self.session_id)

    def update_content(self, header_metrics, report_data, session_date_str, graph_data):
        self.header_metrics = header_metrics
        self.report_data = report_data
        self.graph_data = graph_data
        self.title(f"Session Report - {session_date_str}")
        self._draw_header_metrics()
        self._redraw_report()

    def _draw_header_metrics(self):
        for w in self.header_frame.winfo_children(): w.destroy()
        def create_metric_display(parent, title, value, var=None):
            frame = customtkinter.CTkFrame(parent, fg_color="transparent")
            customtkinter.CTkLabel(frame, text=title, font=customtkinter.CTkFont(size=12, weight="bold")).pack()
            label = customtkinter.CTkLabel(frame, text=value, font=customtkinter.CTkFont(size=20), textvariable=var)
            label.pack()
            return frame
        create_metric_display(self.header_frame, "Total Duration", self.header_metrics["total_duration_str"]).grid(row=0, column=0, pady=10)
        create_metric_display(self.header_frame, "Active Playtime", self.header_metrics["active_playtime_str"]).grid(row=0, column=1, pady=10)
        create_metric_display(self.header_frame, "Play Density", f"{self.header_metrics['play_density']:.1f}%").grid(row=0, column=2, pady=10)
        create_metric_display(self.header_frame, "Total Plays", "", self.total_plays_var).grid(row=0, column=3, pady=10)
        create_metric_display(self.header_frame, "Total PBs", "", self.total_pbs_var).grid(row=0, column=4, pady=10)

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

    def _draw_performance_graph(self):
        if not self.graph_data: return
        
        parent = customtkinter.CTkFrame(self.scroll_frame, fg_color="transparent")
        parent.pack(fill="x", pady=(0, 10))
        content = self._create_collapsible_section(parent, "Session Performance Flow")
        content.pack(fill="x", expand=True)
        
        times = [d['time'] for d in self.graph_data]
        pcts = [d['pct'] for d in self.graph_data]
        
        plt.style.use('dark_background' if customtkinter.get_appearance_mode() == "Dark" else 'seaborn-v0_8-whitegrid')
        fig = Figure(figsize=(8, 6.5), dpi=100) 
        ax = fig.add_subplot(111)
        
        line, = ax.plot(times, pcts, color='#4aa3df', marker='o', markersize=3, linestyle='-', linewidth=1.5, alpha=0.8, picker=5)
        
        ax.axhline(0, color='gray', linestyle='--', linewidth=1, alpha=0.5) 
        ax.fill_between(times, pcts, 0, where=(np.array(pcts) >= 0), color='green', alpha=0.15, interpolate=True)
        ax.fill_between(times, pcts, 0, where=(np.array(pcts) < 0), color='red', alpha=0.15, interpolate=True)

        annot = ax.annotate("", xy=(0,0), xytext=(10,10), textcoords="offset points",
                            bbox=dict(boxstyle="round", fc="#242424", ec="white", alpha=0.9),
                            arrowprops=dict(arrowstyle="->", color="white"),
                            color="white", fontsize=9)
        annot.set_visible(False)

        def update_annot(ind):
            idx = ind["ind"][0]
            pos = line.get_xydata()[idx]
            annot.xy = pos
            data_point = self.graph_data[idx]
            text = f"{data_point['scenario']}\n{data_point['sens']}cm\n{data_point['pct']:.1f}%"
            annot.set_text(text)
            annot.get_bbox_patch().set_edgecolor('#4aa3df')

        def on_hover(event):
            vis = annot.get_visible()
            if event.inaxes == ax:
                cont, ind = line.contains(event)
                if cont:
                    update_annot(ind)
                    annot.set_visible(True)
                    fig.canvas.draw_idle()
                else:
                    if vis:
                        annot.set_visible(False)
                        fig.canvas.draw_idle()

        fig.canvas.mpl_connect("motion_notify_event", on_hover)

        def on_pick(event):
            if event.mouseevent.button != 1: return
            if event.artist != line: return
            ind = event.ind[0]
            if ind < len(self.graph_data):
                data_point = self.graph_data[ind]
                self.app_master.on_cell_click(None, data_point['scenario'], data_point['sens'])

        fig.canvas.mpl_connect('pick_event', on_pick)

        blocks = []
        if self.graph_data:
            current_block = {
                'scen': self.graph_data[0]['scenario'], 
                'sens': self.graph_data[0]['sens'],
                'start_time': self.graph_data[0]['time'],
                'end_time': self.graph_data[0]['time'],
                'count': 1
            }
            for i in range(1, len(self.graph_data)):
                d = self.graph_data[i]
                if d['scenario'] == current_block['scen'] and d['sens'] == current_block['sens']:
                    current_block['end_time'] = d['time']
                    current_block['count'] += 1
                else:
                    blocks.append(current_block)
                    current_block = {
                        'scen': d['scenario'], 'sens': d['sens'],
                        'start_time': d['time'], 'end_time': d['time'], 'count': 1
                    }
            blocks.append(current_block)

        y_min, y_max = ax.get_ylim()
        y_range = y_max - y_min
        if y_range < 5: y_range = 10 
        ax.set_ylim(y_min, y_max + (y_range * 1.8))

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        import matplotlib.dates as mdates
        for i, block in enumerate(blocks):
            if i > 0:
                mid_sep = block['start_time'] - (block['start_time'] - blocks[i-1]['end_time'])/2
                ax.axvline(mid_sep, color='gray', linestyle=':', alpha=0.3)

            if block['count'] == 1: center_time = block['start_time']
            else:
                total_sec = (block['end_time'] - block['start_time']).total_seconds()
                center_time = block['start_time'] + timedelta(seconds=total_sec/2)

            label_text = f"{block['scen']} ({block['sens']}cm)"
            base_y = y_max + (y_range * 0.10)
            offset_y = (y_range * 0.20) if i % 2 != 0 else 0
            text_y = base_y + offset_y

            ax.text(center_time, text_y, label_text, rotation=75, 
                    color='white' if customtkinter.get_appearance_mode() == "Dark" else 'black',
                    fontsize=10, ha='center', va='bottom', alpha=0.9)

        ax.set_ylabel("% vs Avg", fontsize=10)
        if len(times) > 1: ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

        fig.autofmt_xdate()
        fig.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, master=content)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, ipady=20)

    def _redraw_report(self):
        for widget in self.scroll_frame.winfo_children(): widget.destroy()
        
        self._draw_performance_graph()

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
            all_time_text = f"All-Time: {item['all_time_avg']:.0f} ({int(item.get('all_time_play_count', 0))} runs)"
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
        
        if not self.visible_data.empty:
            mean_val = self.visible_data['Score'].mean()
            p75_val = self.visible_data['Score'].quantile(0.75)
            
            ax.axhline(mean_val, color='gray', linestyle='--', linewidth=1, label=f'Avg ({mean_val:.0f})', alpha=0.7)
            
            p75_color = '#66bb6a' if customtkinter.get_appearance_mode() == "Dark" else '#2e7d32'
            ax.axhline(p75_val, color=p75_color, linestyle='--', linewidth=1, label=f'75th ({p75_val:.0f})', alpha=0.8)

        if mode == "Raw Data": self.draw_raw_data_plot(ax)
        else: self.draw_aggregated_plot(ax, mode)
        
        ax.set_title(self.title_text, fontsize=16); ax.set_ylabel("Score", fontsize=12)
        ax.grid(True, which='both', linestyle='--', linewidth=0.5)
        
        ax.legend(loc='best', fontsize='small', framealpha=0.5)

        self.fig.tight_layout()
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

        line_color = '#2ca0c2' 
        
        min_score, max_score = plot_data['Score'].min(), plot_data['Score'].max()
        padding = (max_score - min_score) * 0.05 if max_score > min_score else 10
        ax.set_ylim(min_score - padding, max_score + padding)

        if period_map[mode] == "Session":
            x_vals = np.arange(len(plot_data))
            ax.plot(x_vals, plot_data['Score'], color=line_color, marker='o', markersize=4, linestyle='-', alpha=0.8)
            ax.fill_between(x_vals, plot_data['Score'], color=line_color, alpha=0.2)
            
            ax.set_xlabel("Session", fontsize=12)
            ax.set_xticks(x_vals)
            if len(x_vals) > 20:
                n = len(x_vals) // 20 + 1
                ax.set_xticks(x_vals[::n])
                ax.set_xticklabels([f"S{int(sid)}" for sid in plot_data['SessionID']][::n], rotation=45, ha='right')
            else:
                ax.set_xticklabels([f"S{int(sid)}" for sid in plot_data['SessionID']], rotation=45, ha='right')
        else:
            ax.plot(plot_data['Timestamp'], plot_data['Score'], color=line_color, marker='o', markersize=4, linestyle='-', alpha=0.8)
            ax.fill_between(plot_data['Timestamp'], plot_data['Score'], color=line_color, alpha=0.2)
            
            ax.set_xlabel("Date", fontsize=12)
            self.fig.autofmt_xdate()
        
    def get_bar_width(self, period):
        if period == 'D': return 0.8
        if period == 'W': return 5
        if period == 'M': return 20
        return 1