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
import locales # --- NEW: Import Locales ---

class SessionHistoryWindow(customtkinter.CTkToplevel):
    def __init__(self, master, session_list):
        super().__init__(master)
        # Retrieve language from master app
        self.lang = master.current_language 
        
        self.title(locales.get_text(self.lang, "session_hist_btn"))
        self.geometry("600x500")
        self.transient(master)

        self.app_master = master

        if not session_list:
            customtkinter.CTkLabel(self, text=locales.get_text(self.lang, "load_err_label")).pack(expand=True, padx=20, pady=20)
            return

        scroll_frame = customtkinter.CTkScrollableFrame(self)
        scroll_frame.pack(expand=True, fill="both", padx=10, pady=10)

        for i, session in enumerate(session_list):
            card = customtkinter.CTkFrame(scroll_frame, cursor="hand2")
            card.pack(fill="x", pady=(0, 5))
            card.grid_columnconfigure(0, weight=1)

            date_label = customtkinter.CTkLabel(card, text=session['date_str'], font=customtkinter.CTkFont(size=16, weight="bold"), anchor="w")
            date_label.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=(5,0))

            # Note: 'total_duration_str' comes pre-formatted from app.py logic, but labels need loc
            # For the info string, we can construct it manually or use a localized format string.
            # Let's assume strictly formatted for now or reconstruct:
            # But easiest is to just use the pre-calculated strings and localize labels?
            # Actually, the strings in session_list are just values.
            # Let's construct the label using locales.
            
            # Since session_list passes pre-formatted strings like "00:30:00" and "N/A", we just label them.
            # We might not have specific keys for "Duration:" in the list items, but we can reuse report keys or add generic ones.
            # For simplicity/safety, I will leave the generic "Duration: X | Plays: Y" English-ish structure for the history card 
            # UNLESS we add specific keys. 
            # Let's use the keys from Session Report as best fit.
            
            # Reuse report keys for consistency
            dur_lbl = locales.get_text(self.lang, "rep_duration")
            plays_lbl = locales.get_text(self.lang, "rep_plays")
            
            info_text = (f"{dur_lbl}: {session['total_duration_str']}  |  "
                         f"{plays_lbl}: {session['play_count']}  |  "
                         f"{session['top_scenario']}")
                         
            info_label = customtkinter.CTkLabel(card, text=info_text, font=customtkinter.CTkFont(size=12), anchor="w")
            info_label.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=(0,5))
            
            command = lambda event, sid=session['id']: self.app_master.open_session_report(session_id=sid)
            card.bind("<Button-1>", command)
            date_label.bind("<Button-1>", command)
            info_label.bind("<Button-1>", command)

class SessionReportWindow(customtkinter.CTkToplevel):
    def __init__(self, master, session_id, header_metrics, report_data, session_date_str, graph_data_payload):
        super().__init__(master)
        self.lang = master.current_language
        
        self.title(locales.get_text(self.lang, "rep_title", date=session_date_str))
        
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

        if isinstance(graph_data_payload, dict):
            self.graph_data_payload = graph_data_payload
            self.graph_data = graph_data_payload.get("grid", [])
        else:
            # Fallback
            self.graph_data_payload = {"grid": graph_data_payload, "scenario": graph_data_payload}
            self.graph_data = graph_data_payload
        
        # --- BIND TO MASTER PERSISTENT VARS ---
        # This was likely missing, causing the crash
        self.show_trend_var = master.graph_show_trend_var
        self.show_flow_var = master.graph_show_flow_var
        self.show_pulse_var = master.graph_show_pulse_var
        self.flow_window_var = master.graph_flow_window_var
        # --------------------------------------
        
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

        customtkinter.CTkButton(control_frame, text=locales.get_text(self.lang, "rep_browse"), command=self.app_master.open_session_history).pack(side="left", padx=10, pady=5)
        customtkinter.CTkButton(control_frame, text=locales.get_text(self.lang, "rep_refresh"), width=100, command=self.request_refresh).pack(side="left", padx=0, pady=5)

        self.summary_toggle_var = customtkinter.StringVar(value="Off")
        customtkinter.CTkSwitch(control_frame, text=locales.get_text(self.lang, "rep_summarize"), variable=self.summary_toggle_var, onvalue="On", offvalue="Off", command=self._redraw_report).pack(side="right", padx=10, pady=5)
        
        self.sort_var = customtkinter.StringVar(value="performance")
        sort_options = { 
            locales.get_text(self.lang, "sort_perf"): "performance", 
            locales.get_text(self.lang, "sort_count"): "play_count", 
            locales.get_text(self.lang, "sort_order"): "time", 
            locales.get_text(self.lang, "sort_alpha"): "alpha" 
        }
        
        sort_frame = customtkinter.CTkFrame(control_frame, fg_color="transparent")
        sort_frame.pack(side="right", padx=10)
        customtkinter.CTkLabel(sort_frame, text=locales.get_text(self.lang, "rep_sort")).pack(side="left", padx=(10,5), pady=5)
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

    def update_content(self, header_metrics, report_data, session_date_str, graph_data_payload):
        self.header_metrics = header_metrics
        self.report_data = report_data
        
        # Store the full payload
        self.graph_data_payload = graph_data_payload
        # Default to grid data for safety until redraw
        self.graph_data = graph_data_payload.get("grid", [])
        
        self.title(locales.get_text(self.lang, "rep_title", date=session_date_str))
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
        create_metric_display(self.header_frame, locales.get_text(self.lang, "rep_duration"), self.header_metrics["total_duration_str"]).grid(row=0, column=0, pady=10)
        create_metric_display(self.header_frame, locales.get_text(self.lang, "rep_active"), self.header_metrics["active_playtime_str"]).grid(row=0, column=1, pady=10)
        create_metric_display(self.header_frame, locales.get_text(self.lang, "rep_density"), f"{self.header_metrics['play_density']:.1f}%").grid(row=0, column=2, pady=10)
        create_metric_display(self.header_frame, locales.get_text(self.lang, "rep_plays"), "", self.total_plays_var).grid(row=0, column=3, pady=10)
        create_metric_display(self.header_frame, locales.get_text(self.lang, "rep_pbs"), "", self.total_pbs_var).grid(row=0, column=4, pady=10)

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
        content = self._create_collapsible_section(parent, locales.get_text(self.lang, "rep_graph_title"))
        content.pack(fill="x", expand=True)
        
        # --- CONTROLS ---
        controls = customtkinter.CTkFrame(content, fg_color="transparent")
        controls.pack(fill="x", pady=(0,5))
        
        customtkinter.CTkCheckBox(controls, text="Show Session Trend", variable=self.show_trend_var, command=self._redraw_and_save, checkbox_height=18, checkbox_width=18, font=("Arial", 11)).pack(side="left", padx=10)
        
        # Flow + Window Input
        flow_frame = customtkinter.CTkFrame(controls, fg_color="transparent")
        flow_frame.pack(side="left", padx=10)
        customtkinter.CTkCheckBox(flow_frame, text="Show Global Flow (N=)", variable=self.show_flow_var, command=self._redraw_and_save, checkbox_height=18, checkbox_width=18, font=("Arial", 11)).pack(side="left")
        
        # Small entry for Window
        w_entry = customtkinter.CTkEntry(flow_frame, textvariable=self.flow_window_var, width=30, height=20, font=("Arial", 11))
        w_entry.pack(side="left", padx=(2,0))
        
        # Auto-Refresh Trace (Only add once)
        if not hasattr(self, 'flow_trace_added'):
            self.flow_window_var.trace_add("write", self._schedule_refresh)
            self.flow_trace_added = True
        
        customtkinter.CTkCheckBox(controls, text="Show The Pulse", variable=self.show_pulse_var, command=self._redraw_and_save, checkbox_height=18, checkbox_width=18, font=("Arial", 11)).pack(side="left", padx=10)
        # ------------------------------
        
        times = [d['time'] for d in self.graph_data]
        pcts = [d['pct'] for d in self.graph_data]
        trend_pcts = [d['trend_pct'] for d in self.graph_data]
        flow_pcts = [d['flow_pct'] for d in self.graph_data]
        pulse_pcts = [d['pulse_pct'] for d in self.graph_data]
        
        plt.style.use('dark_background' if customtkinter.get_appearance_mode() == "Dark" else 'seaborn-v0_8-whitegrid')
        fig = Figure(figsize=(8, 6.5), dpi=100) 
        ax = fig.add_subplot(111)
        
        # Plot Lines based on Toggle
        if self.show_trend_var.get():
            ax.plot(times, trend_pcts, color='#FF9800', linestyle='-', linewidth=2, alpha=0.8, label="Session Trend")
        
        if self.show_flow_var.get():
            ax.plot(times, flow_pcts, color='#9C27B0', linestyle='-', linewidth=2, alpha=0.9, label="Global Flow")

        if self.show_pulse_var.get():
            ax.plot(times, pulse_pcts, color='#00E5FF', linestyle='-', linewidth=1.5, alpha=0.9, label="Pulse")

        line, = ax.plot(times, pcts, color='#4aa3df', marker='o', markersize=3, linestyle='-', linewidth=1.0, alpha=0.7, picker=5, label="Score")
        
        ax.axhline(0, color='gray', linestyle='--', linewidth=1, alpha=0.5) 
        ax.fill_between(times, pcts, 0, where=(np.array(pcts) >= 0), color='green', alpha=0.15, interpolate=True)
        ax.fill_between(times, pcts, 0, where=(np.array(pcts) < 0), color='red', alpha=0.15, interpolate=True)

        ax.legend(loc='upper left', fontsize='small', framealpha=0.5)

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
            sens_txt = f"{data_point['sens']}cm"
            text = f"{data_point['scenario']}\n{sens_txt}\n{data_point['pct']:.1f}%"
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
        
        view_mode = "scenario" if self.summary_toggle_var.get() == "On" else "grid"
        
        # --- SWITCH GRAPH DATA ---
        if hasattr(self, 'graph_data_payload'):
            self.graph_data = self.graph_data_payload.get(view_mode, [])
        # -------------------------
        
        self._draw_performance_graph()

        sort_mode = self.sort_var.get()
        data = self.report_data[view_mode]
        
        self.total_plays_var.set(str(self.header_metrics['total_plays_grid']))
        pb_count = self.header_metrics.get(f'total_pbs_{view_mode}', len(data['pbs']))
        self.total_pbs_var.set(str(pb_count))
        
        # ... (rest of sorting and populating logic unchanged) ...
        sort_key_map = {"play_count": "play_count", "time": "first_played", "alpha": "name"}
        reverse_sort_map = {"performance": True, "play_count": True, "time": False, "alpha": False}
        
        data['played'].sort(key=lambda x: x['perf_vs_avg'] if sort_mode == 'performance' else x[sort_key_map.get(sort_mode, 'name')], reverse=reverse_sort_map.get(sort_mode, False))
        data['averages'].sort(key=lambda x: x['perf_vs_avg'] if sort_mode == 'performance' else x[sort_key_map[sort_mode]], reverse=reverse_sort_map.get(sort_mode, False))
        data['pbs'].sort(key=lambda x: x['improvement_pct'] if sort_mode == 'performance' else x[sort_key_map[sort_mode]], reverse=reverse_sort_map.get(sort_mode, False))
        
        if 'rank_counts' in self.report_data:
            self._populate_ranks_section(
                self.report_data['rank_counts'], 
                self.report_data.get('rank_gate_val', 1),
                self.report_data.get('rank_defs', [])
            )
            
        self._populate_pbs_section(data['pbs'])
        self._populate_averages_section(data['averages'])
        self._populate_played_section(data['played'])

    def _populate_ranks_section(self, rank_counts, gate_val=1, rank_defs=None):
        if rank_counts.get("TRANSMUTE", 0) == 0: return

        parent = customtkinter.CTkFrame(self.scroll_frame, fg_color="transparent"); parent.pack(fill="x")
        # Note: loc_key "sec_ranks" needs to be added to locales.py
        title = locales.get_text(self.lang, "sec_ranks", val="Rank Achieved") 
        content = self._create_collapsible_section(parent, title)
        
        # --- DYNAMIC EXPLANATION TEXT ---
        if rank_defs:
            # Sort lowest to highest for reading left-to-right
            # rank_defs is usually [("SINGULARITY", 100)...], so we reverse it
            sorted_defs = sorted(rank_defs, key=lambda x: x[1])
            
            # Build string like: "Transmute: 55% | Blessed: 75% | ..."
            parts = []
            for name, val in sorted_defs:
                if name == "SINGULARITY": continue # Skip 100/PB for threshold text usually? Or show it?
                # User asked for thresholds, usually Singularity implies PB/100, let's include all except maybe PB if redundant
                # Let's include it as "Singularity: 100%" or "PB"
                parts.append(f"{name.capitalize()}: {val}%")
            
            threshold_text = "  •  ".join(parts)
            
            # Combine with Gate info
            full_info_text = threshold_text
            if gate_val > 1:
                full_info_text += f"   |   *Uber+ requires {gate_val} runs"
            
            info_lbl = customtkinter.CTkLabel(content, text=full_info_text, font=customtkinter.CTkFont(size=11), text_color="gray")
            info_lbl.pack(anchor="w", padx=10, pady=(0, 5))
        # ------------------------------
        
        content_grid = customtkinter.CTkFrame(content, fg_color="transparent")
        content_grid.pack(fill="x")
        content_grid.grid_columnconfigure((0,1,2,3,4,5), weight=1, uniform="rank_group")
        
        rank_order = ["TRANSMUTE", "BLESSED", "EXALTED", "UBER", "ARCADIA", "SINGULARITY"]
        
        rank_styles = {
            "TRANSMUTE":   ("#448AFF", "black"), 
            "BLESSED":     ("#FF5252", "black"), 
            "EXALTED":     ("#FDD835", "black"), 
            "UBER":        ("#673AB7", "white"), 
            "ARCADIA":     ("#2E7D32", "white"), 
            "SINGULARITY": ("#000000", "white")  
        }
        
        for i, rank_name in enumerate(rank_order):
            count = rank_counts.get(rank_name, 0)
            bg_col, txt_col = rank_styles.get(rank_name, ("gray", "white"))
            
            frame = customtkinter.CTkFrame(content_grid, fg_color=bg_col)
            frame.grid(row=0, column=i, padx=5, pady=5, sticky="ew")
            
            lbl_name = customtkinter.CTkLabel(frame, text=rank_name, font=customtkinter.CTkFont(size=10, weight="bold"), text_color=txt_col)
            lbl_name.pack(pady=(5,0))
            
            lbl_count = customtkinter.CTkLabel(frame, text=str(count), font=customtkinter.CTkFont(size=18, weight="bold"), text_color=txt_col)
            lbl_count.pack(pady=(0,5))

    def _populate_played_section(self, played_data):
        parent = customtkinter.CTkFrame(self.scroll_frame, fg_color="transparent"); parent.pack(fill="x")
        title = locales.get_text(self.lang, "sec_played", count=len(played_data))
        content = self._create_collapsible_section(parent, title)
        content.grid_columnconfigure((0, 1), weight=1)
        num_items = len(played_data); num_rows = (num_items + 1) // 2
        for i, item in enumerate(played_data):
            name = item['name'] + (f" ({item['sens']}cm)" if 'sens' in item else "")
            
            # Localize "runs"
            runs_lbl = locales.get_text(self.lang, "tooltip_runs", val=item['play_count']) # "Runs: 16"
            # Strip "Runs: " prefix if we just want "(16 runs)" format or assume standard format?
            # Let's standard format: "Scenario (16 runs)"
            # We need a generic "X runs" key or reuse existing. 
            # Let's use a new on-the-fly format since we didn't make a specific key for this list item.
            # Actually, let's just use English for the brackets for safety or reuse rep_plays logic.
            # Ideally, we add "lbl_list_item": "{name} ({count} runs)" to locales. 
            # But for now, let's stick to structure:
            name_with_count = f"{name} ({item['play_count']})" # Simplified
            
            if item['is_pb']: name_with_count = "🏆 " + name_with_count
            row = i % num_rows; column = i // num_rows
            label = customtkinter.CTkLabel(content, text=name_with_count, font=customtkinter.CTkFont(size=12), anchor="w")
            label.grid(row=row, column=column, sticky="ew", padx=10)

    def _populate_pbs_section(self, pbs_data):
        parent = customtkinter.CTkFrame(self.scroll_frame, fg_color="transparent"); parent.pack(fill="x")
        title = locales.get_text(self.lang, "sec_pbs", count=len(pbs_data))
        content = self._create_collapsible_section(parent, title)
        for i, item in enumerate(pbs_data):
            card = customtkinter.CTkFrame(content); card.pack(fill="x", pady=(0, 5))
            card.grid_columnconfigure(1, weight=1)
            name = item['name'] + (f" ({item['sens']}cm)" if 'sens' in item else "")
            customtkinter.CTkLabel(card, text=name, font=customtkinter.CTkFont(size=14, weight="bold"), anchor="w").grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(5,0))
            imp_pts_str = f"{item['improvement_pts']:+.0f} pts"; imp_pct_str = f"({item['improvement_pct']:+.1f}%)"
            
            # Localized "New PB: X (vs Y)"
            pb_text = locales.get_text(self.lang, "lbl_new_pb", new=f"{item['new_score']:.0f}", old=f"{item['prev_score']:.0f}")
            
            customtkinter.CTkLabel(card, text=pb_text, anchor="w").grid(row=1, column=0, padx=10, pady=(0,5))
            customtkinter.CTkLabel(card, text=f"{imp_pts_str} {imp_pct_str}", text_color="gold", font=customtkinter.CTkFont(weight="bold"), anchor="e").grid(row=1, column=1, padx=10, pady=(0,5))

    def _populate_averages_section(self, averages_data):
        parent = customtkinter.CTkFrame(self.scroll_frame, fg_color="transparent"); parent.pack(fill="x")
        title = locales.get_text(self.lang, "sec_avgs", count=len(averages_data))
        content = self._create_collapsible_section(parent, title)
        for i, item in enumerate(averages_data):
            card = customtkinter.CTkFrame(content); card.pack(fill="x", pady=(0, 5))
            card.grid_columnconfigure(0, weight=1)
            name = item['name'] + (f" ({item['sens']}cm)" if 'sens' in item else "")
            customtkinter.CTkLabel(card, text=name, font=customtkinter.CTkFont(size=14, weight="bold"), anchor="w").grid(row=0, column=0, sticky="ew", padx=10, pady=(5,0))
            stats_frame = customtkinter.CTkFrame(card, fg_color="transparent"); stats_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0,5))
            stats_frame.grid_columnconfigure((0,1,2), weight=1, uniform="group1")
            
            # Localized Strings
            session_text = locales.get_text(self.lang, "lbl_session", val=f"{item['session_avg']:.0f}", count=item['play_count'])
            all_time_text = locales.get_text(self.lang, "lbl_alltime", val=f"{item['all_time_avg']:.0f}", count=int(item.get('all_time_play_count', 0)))
            
            perf_str = f"{item['perf_vs_avg']:+.1f}%"; perf_color = "lightgreen" if item['perf_vs_avg'] >= 0 else "#F47174"
            customtkinter.CTkLabel(stats_frame, text=session_text, anchor="w").grid(row=0, column=0, sticky="ew", padx=5)
            customtkinter.CTkLabel(stats_frame, text=all_time_text, anchor="center").grid(row=0, column=1, sticky="ew")
            customtkinter.CTkLabel(stats_frame, text=perf_str, font=customtkinter.CTkFont(weight="bold"), text_color=perf_color, anchor="e").grid(row=0, column=2, sticky="ew", padx=5)

    def _redraw_and_save(self, event=None):
        self.app_master.save_user_data()
        self._redraw_report()

    def _schedule_refresh(self, *args):
        if hasattr(self, '_refresh_job') and self._refresh_job:
            self.after_cancel(self._refresh_job)
        self._refresh_job = self.after(800, self.request_refresh)

class GraphWindow(customtkinter.CTkToplevel):
    def __init__(self, master, full_data, hide_settings, save_callback, graph_id, title):
        super().__init__(master)
        self.lang = master.current_language
        self.title(title)
        self.geometry("950x700")
        self.transient(master)

        self.app_master = master 
        self.full_data = full_data
        self.hide_settings = hide_settings
        self.save_callback = save_callback
        self.graph_id = graph_id
        self.title_text = title
        
        # --- BIND TO MASTER PERSISTENT VARS ---
        self.show_trend_var = master.graph_grid_show_trend_var
        
        # SMA 1 (Purple)
        self.show_sma_var = master.graph_grid_show_sma_var
        self.sma_window_var = master.graph_grid_sma_window_var
        
        # SMA 2 (Cyan)
        self.show_sma2_var = master.graph_grid_show_sma2_var
        self.sma2_window_var = master.graph_grid_sma2_window_var
        
        # Auto-Refresh Traces
        if not hasattr(self, 'sma_trace_added'):
            self.sma_window_var.trace_add("write", self._schedule_refresh)
            self.sma2_window_var.trace_add("write", self._schedule_refresh)
            self.sma_trace_added = True
        # --------------------------------------
        
        self.view_key_map = {"Raw Data": "raw", "Daily Average": "daily", "Weekly Average": "weekly", "Monthly Average": "monthly", "Session Average": "session"}

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<F5>", self.request_refresh)
        self.app_master.register_graph_window(self)

        top_control_frame = customtkinter.CTkFrame(self); top_control_frame.pack(fill="x", padx=10, pady=(10,0))
        bottom_control_frame = customtkinter.CTkFrame(self); bottom_control_frame.pack(fill="x", padx=10, pady=(0,5))

        # Localized
        customtkinter.CTkLabel(top_control_frame, text=locales.get_text(self.lang, "graph_view_mode")).pack(side="left", padx=(10,5), pady=5)
        self.aggregation_var = customtkinter.StringVar(value="Raw Data")
        
        aggregation_menu = customtkinter.CTkOptionMenu(top_control_frame, variable=self.aggregation_var,
                                                       values=["Raw Data", "Daily Average", "Weekly Average", "Monthly Average", "Session Average"],
                                                       command=self.on_view_mode_change)
        aggregation_menu.pack(side="left", padx=5, pady=5)
        
        self.raw_display_mode_var = customtkinter.StringVar(value=self.hide_settings.get("raw_display_mode", "Line Plot"))
        self.raw_display_menu = customtkinter.CTkOptionMenu(top_control_frame, variable=self.raw_display_mode_var,
                                                            values=["Line Plot", "Dots Only", "Filled Area"],
                                                            command=self._on_graph_option_change)
        
        customtkinter.CTkButton(top_control_frame, text=locales.get_text(self.lang, "rep_refresh"), width=90, command=self.request_refresh).pack(side="right", padx=10, pady=5)
        
        customtkinter.CTkLabel(bottom_control_frame, text=locales.get_text(self.lang, "graph_hide_low")).pack(side="left", padx=(10,5), pady=5)
        self.hide_below_var = customtkinter.StringVar()
        hide_below_entry = customtkinter.CTkEntry(bottom_control_frame, textvariable=self.hide_below_var, width=80)
        hide_below_entry.pack(side="left", padx=5, pady=5)
        hide_below_entry.bind("<Return>", self.update_hide_below)
        
        self.connect_sessions_var = customtkinter.StringVar(value=self.hide_settings.get("connect_sessions", "Off"))
        self.connect_sessions_switch = customtkinter.CTkSwitch(bottom_control_frame, text=locales.get_text(self.lang, "graph_connect"), variable=self.connect_sessions_var, onvalue="On", offvalue="Off", command=self._on_graph_option_change)
        
        self.four_color_cycle_var = customtkinter.StringVar(value=self.hide_settings.get("four_color_cycle", "Off"))
        self.four_color_cycle_switch = customtkinter.CTkSwitch(bottom_control_frame, text=locales.get_text(self.lang, "graph_4color"), variable=self.four_color_cycle_var, onvalue="On", offvalue="Off", command=self._on_graph_option_change)
        
        # --- Trend Controls ---
        trend_frame = customtkinter.CTkFrame(bottom_control_frame, fg_color="transparent")
        trend_frame.pack(side="right", padx=10)
        
        def toggle_trend(): 
            self.app_master.save_user_data()
            self.redraw_plot()

        customtkinter.CTkCheckBox(trend_frame, text="Career Trend", variable=self.show_trend_var, command=toggle_trend, checkbox_height=18, checkbox_width=18, font=("Arial", 11)).pack(side="left", padx=5)
        
        # SMA 1
        sma_frame = customtkinter.CTkFrame(trend_frame, fg_color="transparent")
        sma_frame.pack(side="left", padx=5)
        customtkinter.CTkCheckBox(sma_frame, text="SMA (N=)", variable=self.show_sma_var, command=toggle_trend, checkbox_height=18, checkbox_width=18, font=("Arial", 11)).pack(side="left")
        sma_entry = customtkinter.CTkEntry(sma_frame, textvariable=self.sma_window_var, width=30, height=20, font=("Arial", 11))
        sma_entry.pack(side="left", padx=(2,0))
        
        # SMA 2
        sma2_frame = customtkinter.CTkFrame(trend_frame, fg_color="transparent")
        sma2_frame.pack(side="left", padx=5)
        customtkinter.CTkCheckBox(sma2_frame, text="SMA (N=)", variable=self.show_sma2_var, command=toggle_trend, checkbox_height=18, checkbox_width=18, font=("Arial", 11)).pack(side="left")
        sma2_entry = customtkinter.CTkEntry(sma2_frame, textvariable=self.sma2_window_var, width=30, height=20, font=("Arial", 11))
        sma2_entry.pack(side="left", padx=(2,0))
        # ---------------------
        
        self.plot_frame = customtkinter.CTkFrame(self); self.plot_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.fig, self.canvas, self.toolbar = None, None, None
        self.on_view_mode_change()

    def on_close(self):
        self.app_master.deregister_graph_window(self)
        self.destroy()

    def request_refresh(self, event=None):
        self.app_master.load_stats_thread()

    def update_data(self, new_full_data):
        # Called by App to refresh stats
        self.full_data = new_full_data
        self.redraw_plot()

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
                ax.plot(plot_x, plot_y, color=color, alpha=0.7, zorder=2)
                ax.scatter(group.index, group['Score'], color=color, s=20, zorder=3)
            elif display_mode == "Dots Only":
                ax.scatter(group.index, group['Score'], color=color, s=20, zorder=3)
            elif display_mode == "Filled Area":
                ax.plot(plot_x, plot_y, color=color, alpha=0.8, zorder=2)
                ax.fill_between(plot_x, plot_y, color=color, alpha=0.3, zorder=1)
                ax.scatter(group.index, group['Score'], color=color, s=20, zorder=3)
            
            last_point = (group.index[-1], group['Score'].iloc[-1])

        # --- TREND LINES (Draw ON TOP) ---
        
        # 1. Career Trend (Orange)
        if self.show_trend_var.get():
            cumulative_avg = plot_data['Score'].expanding().mean()
            ax.plot(plot_data.index, cumulative_avg, color='#FF9800', linestyle='-', linewidth=2.5, alpha=0.95, label="Career Trend", zorder=5)

        # 2. SMA 1 (White)
        if self.show_sma_var.get():
            try:
                w = int(self.sma_window_var.get())
                if w < 1: w = 20
            except ValueError: w = 20
            
            sma = plot_data['Score'].rolling(window=w).mean()
            ax.plot(plot_data.index, sma, color='white', linestyle='-', linewidth=2.5, alpha=0.95, label=f"SMA ({w})", zorder=5)

        # 3. SMA 2 (Cyan)
        if self.show_sma2_var.get():
            try:
                w2 = int(self.sma2_window_var.get())
                if w2 < 1: w2 = 10
            except ValueError: w2 = 10
            
            sma2 = plot_data['Score'].rolling(window=w2).mean()
            ax.plot(plot_data.index, sma2, color='#00E5FF', linestyle='-', linewidth=2.5, alpha=0.95, label=f"SMA ({w2})", zorder=5)
        
        # ---------------------------------

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
    
    def _schedule_refresh(self, *args):
        if hasattr(self, '_refresh_job') and self._refresh_job:
            self.after_cancel(self._refresh_job)
        self._refresh_job = self.after(800, lambda: (self.save_callback(), self.redraw_plot()))

class CareerProfileWindow(customtkinter.CTkToplevel):
    def __init__(self, master, all_runs_df):
        super().__init__(master)
        self.lang = master.current_language
        self.title("Career Profile")
        self.geometry("800x850")
        self.transient(master)
        
        self.df = all_runs_df
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self.header_frame = customtkinter.CTkFrame(self, fg_color=("gray85", "gray20"))
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        self.scroll_frame = customtkinter.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.scroll_frame.grid_columnconfigure(0, weight=1)
        
        # 1. Calculate All Time Stats
        self.all_time_stats = engine.calculate_profile_stats(self.df)
        
        # 2. Draw Top Section (All Time)
        self._draw_stats_block(self.header_frame, self.all_time_stats, title="All Time Career")
        
        # 3. Draw Monthly Archives
        self._draw_monthly_archives()



    def format_timedelta_hours(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

    def _draw_stats_block(self, parent, stats, title):
        if not stats: return

        # Title + Career Start
        title_frame = customtkinter.CTkFrame(parent, fg_color="transparent")
        title_frame.pack(pady=(10, 5))
        customtkinter.CTkLabel(title_frame, text=title, font=customtkinter.CTkFont(size=18, weight="bold")).pack(side="left")
        
        if title == "All Time Career":
            start_date = self.df['Timestamp'].min().strftime('%B %d, %Y')
            customtkinter.CTkLabel(title_frame, text=f"(Started: {start_date})", font=customtkinter.CTkFont(size=12), text_color="gray").pack(side="left", padx=10)
        
        # Grid for metrics
        metrics_frame = customtkinter.CTkFrame(parent, fg_color="transparent")
        metrics_frame.pack(fill="x", padx=10, pady=5)
        
        # Adjusted columns to 5 to fit the extra PB stat comfortably
        metrics_frame.grid_columnconfigure((0,1,2,3,4), weight=1)
        
        def add_metric(r, c, label, value):
            f = customtkinter.CTkFrame(metrics_frame, fg_color=("gray80", "gray25"))
            f.grid(row=r, column=c, padx=5, pady=5, sticky="ew")
            customtkinter.CTkLabel(f, text=label, font=customtkinter.CTkFont(size=11)).pack(pady=(5,0))
            customtkinter.CTkLabel(f, text=str(value), font=customtkinter.CTkFont(size=15, weight="bold")).pack(pady=(0,5))
            
        add_metric(0, 0, "Total Runs", f"{stats['total_runs']:,}")
        
        # Split PBs
        add_metric(0, 1, "Total PBs", f"{stats['total_pbs_scen']:,}")
        add_metric(0, 2, "Total PBs /cm", f"{stats['total_pbs_combo']:,}")
        
        # Time Stats
        add_metric(0, 3, "Active Playtime", f"{self.format_timedelta_hours(stats['active_playtime'])}")
        
        comp_rate = (stats['active_playtime'] / stats['total_session_time'] * 100) if stats['total_session_time'] > 0 else 0
        add_metric(0, 4, "Efficiency", f"{comp_rate:.1f}%")
        
        # Row 2 (Centered 3 items)
        # We can put them in columns 1, 2, 3 to center visually if we use 5 cols
        add_metric(1, 1, "Unique Scenarios", stats['unique_scenarios'])
        add_metric(1, 2, "Unique Combos", stats['unique_combos'])
        add_metric(1, 3, "Most Active Day", stats['most_active_day'])
        
        # Ranks Section
        self._draw_ranks(parent, stats['rank_counts'], stats['rank_defs'])
        
        # Top Scenarios
        self._draw_top_scenarios(parent, stats['top_scenarios'])

    def _draw_ranks(self, parent, rank_counts, rank_defs):
        f = customtkinter.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=10, pady=5)
        f.grid_columnconfigure((0,1,2,3,4,5), weight=1, uniform="rank_group_prof")
        
        # Use defs for order (lowest to highest? No, let's keep visual consistency)
        # Visual: Transmute -> Singularity
        rank_order = ["TRANSMUTE", "BLESSED", "EXALTED", "UBER", "ARCADIA", "SINGULARITY"]
        rank_styles = {
            "TRANSMUTE":   ("#448AFF", "black"), 
            "BLESSED":     ("#FF5252", "black"), 
            "EXALTED":     ("#FDD835", "black"), 
            "UBER":        ("#673AB7", "white"), 
            "ARCADIA":     ("#2E7D32", "white"), 
            "SINGULARITY": ("#000000", "white")  
        }
        
        for i, r_name in enumerate(rank_order):
            count = rank_counts.get(r_name, 0)
            bg, txt = rank_styles.get(r_name, ("gray", "white"))
            
            if count == 0: bg = ("gray90", "gray30"); txt = "gray"
            
            cell = customtkinter.CTkFrame(f, fg_color=bg)
            cell.grid(row=0, column=i, padx=2, pady=2, sticky="ew")
            # Full Name
            customtkinter.CTkLabel(cell, text=r_name, font=customtkinter.CTkFont(size=12, weight="bold"), text_color=txt).pack(pady=2)
            customtkinter.CTkLabel(cell, text=f"{count}", font=customtkinter.CTkFont(size=12), text_color=txt).pack(pady=(0,2))

    def _draw_top_scenarios(self, parent, top_dict):
        if not top_dict: return
        f = customtkinter.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=10, pady=(5,10))
        
        btn = customtkinter.CTkButton(f, text="Show Top 10 Scenarios ▶", fg_color="transparent", text_color=("black", "white"), height=20)
        btn.pack(anchor="w")
        
        content = customtkinter.CTkFrame(f)
        
        def toggle():
            if content.winfo_viewable(): content.pack_forget(); btn.configure(text="Show Top 10 Scenarios ▶")
            else: content.pack(fill="x", pady=5); btn.configure(text="Hide Top 10 Scenarios ▼")
        btn.configure(command=toggle)
        
        for i, (name, count) in enumerate(top_dict.items()):
            row = customtkinter.CTkFrame(content, fg_color="transparent")
            row.pack(fill="x", padx=5, pady=1)
            customtkinter.CTkLabel(row, text=f"{i+1}. {name}", anchor="w").pack(side="left")
            customtkinter.CTkLabel(row, text=f"{count}", anchor="e", font=customtkinter.CTkFont(weight="bold")).pack(side="right")

    def _draw_monthly_archives(self):
        df_mod = self.df.copy()
        df_mod['Month'] = df_mod['Timestamp'].dt.to_period('M')
        
        months = sorted(df_mod['Month'].unique(), reverse=True)
        
        customtkinter.CTkLabel(self.scroll_frame, text="Monthly Archives", font=customtkinter.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        for m in months:
            month_str = m.strftime("%B %Y")
            month_df = df_mod[df_mod['Month'] == m]
            
            # Pre-calculate stats for the label
            stats = engine.calculate_profile_stats(month_df)
            
            # Construct summary label
            # Exalted Ratio = (Exalted / Total Runs) * 100
            # Note: "Exalted" count in enriched data is CUMULATIVE (includes Uber, etc)
            exalted_count = stats['rank_counts'].get('EXALTED', 0)
            exalted_ratio = (exalted_count / stats['total_runs'] * 100) if stats['total_runs'] > 0 else 0
            
            # Localize hours
            time_str = self.format_timedelta_hours(stats['active_playtime'])
            
            summary_text = f"Runs: {stats['total_runs']}  |  Time: {time_str}  |  Exalted+: {exalted_ratio:.1f}%"
            
            container = customtkinter.CTkFrame(self.scroll_frame)
            container.pack(fill="x", pady=2)
            
            content_frame = customtkinter.CTkFrame(container, fg_color="transparent")
            
            def toggle(c=content_frame, s=stats, b_wid=None):
                if c.winfo_viewable():
                    c.pack_forget()
                else:
                    c.pack(fill="x", padx=5, pady=5)
                    # We already have stats, just draw
                    if not c.winfo_children():
                        self._draw_stats_block(c, s, title="")
            
            # Custom Button layout to include summary text on right
            # Standard CTkButton text alignment is limited. 
            # Better to use a Frame with two labels acting as a button.
            
            btn_frame = customtkinter.CTkFrame(container, fg_color=("gray75", "gray30"), corner_radius=6)
            btn_frame.pack(fill="x", ipady=5)
            
            # Bind click events
            btn_frame.bind("<Button-1>", lambda e, c=content_frame, s=stats: toggle(c, s))
            
            lbl_left = customtkinter.CTkLabel(btn_frame, text=month_str, font=customtkinter.CTkFont(size=14, weight="bold"))
            lbl_left.pack(side="left", padx=10)
            lbl_left.bind("<Button-1>", lambda e, c=content_frame, s=stats: toggle(c, s))
            
            lbl_right = customtkinter.CTkLabel(btn_frame, text=summary_text, font=customtkinter.CTkFont(size=12), text_color="gray20")
            # Fix text color for dark mode manually or let it be auto
            if customtkinter.get_appearance_mode() == "Dark": lbl_right.configure(text_color="gray80")
            
            lbl_right.pack(side="right", padx=10)
            lbl_right.bind("<Button-1>", lambda e, c=content_frame, s=stats: toggle(c, s))
            
            # Hover effects
            def on_enter(e, f=btn_frame): f.configure(fg_color=("gray65", "gray40"))
            def on_leave(e, f=btn_frame): f.configure(fg_color=("gray75", "gray30"))
            btn_frame.bind("<Enter>", on_enter)
            btn_frame.bind("<Leave>", on_leave)
            # Propagate hover to labels
            lbl_left.bind("<Enter>", on_enter); lbl_left.bind("<Leave>", on_leave)
            lbl_right.bind("<Enter>", on_enter); lbl_right.bind("<Leave>", on_leave)