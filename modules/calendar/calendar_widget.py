import datetime
import calendar
import pandas as pd
import numpy as np
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QPushButton, QLabel, QFrame, QScrollArea, 
                             QTableWidget, QTableWidgetItem, QHeaderView, 
                             QAbstractItemView, QComboBox, QCheckBox)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QColor
from modules.calendar.day_cell import DayCell
from modules.calendar.daily_activity import DailyActivityWidget
from core.analytics import stats

class DayDetailWidget(QWidget):
    def __init__(self, state_manager, config_manager):
        super().__init__()
        self.state_manager = state_manager
        self.config = config_manager
        self.day_df = None; self.full_df = None
        self.current_date_str = None
        
        layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0)
        h_layout = QHBoxLayout()
        self.lbl_title = QLabel("Select a day")
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #d1d4dc;")
        
        self.chk_group = QCheckBox("Group by Scenario")
        self.chk_group.stateChanged.connect(self.save_state)
        self.chk_group.stateChanged.connect(self.refresh_table)
        self.chk_group.setVisible(False)
        
        self.cb_sort = QComboBox()
        self.cb_sort.addItems(["Most Played", "Performance", "Time", "A-Z"])
        self.cb_sort.currentIndexChanged.connect(self.save_state)
        self.cb_sort.currentIndexChanged.connect(self.refresh_table)
        self.cb_sort.setVisible(False)
        
        h_layout.addWidget(self.lbl_title); h_layout.addStretch()
        h_layout.addWidget(self.chk_group); h_layout.addSpacing(10)
        h_layout.addWidget(QLabel("Sort:")); h_layout.addWidget(self.cb_sort)
        layout.addLayout(h_layout)
        
        self.sess_container = QFrame()
        self.sess_layout = QHBoxLayout(self.sess_container)
        self.sess_layout.setContentsMargins(0,5,0,5); self.sess_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.sess_container)
        
        self.table = QTableWidget()
        cols = ["Scenario", "Runs", "Best", "Avg", "vs Avg", "vs 75th", "vs PB", "Gain"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection) 
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        h = self.table.horizontalHeader(); h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, len(cols)): h.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)
        
        self.table.itemClicked.connect(self.on_table_clicked)
        self.load_state()

    def on_table_clicked(self, item):
        row = item.row()
        scen_txt = self.table.item(row, 0).text()
        scenario = scen_txt
        sens = None
        if "(" in scen_txt and "cm)" in scen_txt:
            parts = scen_txt.rsplit(" (", 1)
            scenario = parts[0]
            sens_str = parts[1].replace("cm)", "")
            try: sens = float(sens_str)
            except: pass
        self.state_manager.variant_selected.emit({'scenario': scenario, 'sens': sens})

    def save_state(self):
        state = {"group_by": self.chk_group.isChecked(), "sort_mode": self.cb_sort.currentText()}
        self.config.set_global("calendar_detail", state)

    def load_state(self):
        state = self.config.get("calendar_detail", default={})
        if "group_by" in state: self.chk_group.setChecked(state["group_by"])
        if "sort_mode" in state: self.cb_sort.setCurrentText(state["sort_mode"])

    def load_day(self, date_str, daily_df, full_df):
        self.day_df = daily_df; self.full_df = full_df; self.current_date_str = date_str
        self.lbl_title.setText(f"Activity for {date_str}")
        self.cb_sort.setVisible(True); self.chk_group.setVisible(True)
        while self.sess_layout.count(): child = self.sess_layout.takeAt(0); child.widget().deleteLater() if child.widget() else None
        sessions = sorted(daily_df['SessionID'].unique())
        self.sess_layout.addWidget(QLabel("Sessions:"))
        for sid in sessions:
            btn = QPushButton(f"#{int(sid)}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("QPushButton { background: #2a2e39; border: 1px solid #363a45; padding: 2px 8px; color: #4aa3df; font-weight: bold; } QPushButton:hover { background: #363a45; border: 1px solid #4aa3df; }")
            btn.clicked.connect(lambda ch, s=sid: self.state_manager.session_selected.emit(s))
            self.sess_layout.addWidget(btn)
        self.refresh_table()

    def refresh_table(self):
        if self.day_df is None or self.day_df.empty: return
        group_by_scen = self.chk_group.isChecked()
        pb_icon = "🏆" if group_by_scen else "🎯"
        if group_by_scen: grouped = self.day_df.groupby('Scenario')
        else: grouped = self.day_df.groupby(['Scenario', 'Sens'])
        day_start_ts = pd.Timestamp(self.current_date_str)
        
        # Load Comparison Mode
        comp_mode = self.config.get("calendar_compare_mode", default="Average")
        
        rows = []
        for key, group in grouped:
            scen = key if group_by_scen else key[0]
            sens = None if group_by_scen else key[1]
            
            # Day Stats
            day_best = group['Score'].max()
            day_avg = group['Score'].mean()
            run_count = len(group)
            
            # Select what we compare against history (Best vs Avg)
            day_compare_val = day_avg if comp_mode == "Average" else day_best
            
            if group_by_scen: hist = self.full_df[self.full_df['Scenario'] == scen]
            else: hist = self.full_df[(self.full_df['Scenario'] == scen) & (self.full_df['Sens'] == sens)]
            
            prev_runs = hist[hist['Timestamp'] < day_start_ts]
            
            hist_pb = 0; hist_avg = 0; hist_p75 = 0
            gain_val = 0; gain_pct = 0; pb_status = "NONE"; vs_pb_pct = 0
            
            if not prev_runs.empty:
                hist_pb = prev_runs['Score'].max()
                hist_avg = prev_runs['Score'].mean()
                hist_p75 = prev_runs['Score'].quantile(0.75)
                
                # PB Logic (Always compares Best vs Hist PB)
                if day_best > hist_pb:
                    pb_status = "PB"
                    gain_val = day_best - hist_pb
                    if hist_pb > 0: gain_pct = (gain_val / hist_pb) * 100
                else:
                    if hist_pb > 0: vs_pb_pct = ((day_best - hist_pb) / hist_pb) * 100
            else:
                # New Content Logic
                sorted_group = group.sort_values('Timestamp')
                first_run_score = sorted_group.iloc[0]['Score']
                pb_status = "NEW"
                if day_best > first_run_score:
                    gain_val = day_best - first_run_score
                    if first_run_score > 0: gain_pct = (gain_val / first_run_score) * 100

            # Comparison Logic (Dynamic)
            vs_avg_pct = -999.0
            if hist_avg > 0: vs_avg_pct = ((day_compare_val - hist_avg) / hist_avg) * 100
            
            vs_p75_pct = -999.0
            if hist_p75 > 0: vs_p75_pct = ((day_compare_val - hist_p75) / hist_p75) * 100

            rows.append({
                'name': scen, 'sens': sens, 'count': run_count, 
                'best': day_best, 'avg': day_avg, # Track both
                'hist_avg': hist_avg, 'hist_p75': hist_p75,
                'pb_status': pb_status, 'gain_val': gain_val, 'gain_pct': gain_pct, 'vs_pb_pct': vs_pb_pct,
                'vs_avg_pct': vs_avg_pct, 'vs_p75_pct': vs_p75_pct,
                'time': group['Timestamp'].min()
            })
            
        mode = self.cb_sort.currentText()
        if mode == "Most Played": rows.sort(key=lambda x: x['count'], reverse=True)
        elif mode == "Performance": 
            pbs = [r for r in rows if r['pb_status'] == 'PB']
            news = [r for r in rows if r['pb_status'] == 'NEW']
            others = [r for r in rows if r['pb_status'] not in ('PB', 'NEW')]
            pbs.sort(key=lambda x: x['gain_pct'], reverse=True)
            others.sort(key=lambda x: x['vs_avg_pct'], reverse=True)
            news.sort(key=lambda x: x['name'].lower()) 
            rows = pbs + others + news
        elif mode == "Time": rows.sort(key=lambda x: x['time']) 
        elif mode == "A-Z": rows.sort(key=lambda x: x['name'].lower())
        
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            name_txt = r['name']; 
            if r['sens']: name_txt += f" ({r['sens']}cm)"
            self.table.setItem(i, 0, QTableWidgetItem(name_txt))
            
            item_runs = QTableWidgetItem(str(r['count']))
            item_runs.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 1, item_runs)
            
            item_best = QTableWidgetItem(f"{r['best']:.0f}")
            item_best.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 2, item_best)
            
            # NEW: Avg Column
            item_avg = QTableWidgetItem(f"{r['avg']:.0f}")
            item_avg.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 3, item_avg)
            
            def set_cell(col, val, color=None):
                it = QTableWidgetItem(val); it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if color: it.setForeground(QColor(color))
                self.table.setItem(i, col, it)
                
            if r['pb_status'] == "NEW":
                gain_str = f"+{r['gain_pct']:.1f}%" if r['gain_pct'] > 0 else "-"
                set_cell(4, "NEW!", "#4aa3df")
                set_cell(5, "NEW!", "#4aa3df")
                set_cell(6, "NEW!", "#4aa3df")
                set_cell(7, gain_str, "#4aa3df" if r['gain_pct'] > 0 else None)
            else:
                if r['hist_avg'] > 0:
                    set_cell(4, f"{r['vs_avg_pct']:+.1f}%", "#4CAF50" if r['vs_avg_pct']>0 else "#EF5350")
                else: set_cell(4, "-", None)
                
                if r['hist_p75'] > 0:
                    set_cell(5, f"{r['vs_p75_pct']:+.1f}%", "#4CAF50" if r['vs_p75_pct']>0 else "#EF5350")
                else: set_cell(5, "-", None)
                
                if r['pb_status'] == "PB":
                    set_cell(6, f"PB {pb_icon}", "#FFD700")
                    set_cell(7, f"+{r['gain_val']:.0f} (+{r['gain_pct']:.1f}%)", "#FFD700")
                else:
                    set_cell(6, f"{r['vs_pb_pct']:.1f}%", "#EF5350")
                    set_cell(7, "-")

class CalendarWidget(QWidget):
    def __init__(self, state_manager):
        super().__init__()
        self.state_manager = state_manager
        from core.config_manager import ConfigManager
        self.config_manager = ConfigManager()
        
        self.full_df = None
        
        self.current_date = QDate.currentDate(); self.selected_date = None; self.daily_stats = {} 
        self.setup_ui(); self.state_manager.data_updated.connect(self.on_data_updated)
        self.state_manager.request_date_jump.connect(self.on_date_jump_request)

    def setup_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(10,10,10,10)
        
        top_bar = QHBoxLayout()
        btn_prev = QPushButton("◀"); btn_prev.setFixedWidth(30); btn_prev.clicked.connect(self.prev_month)
        self.lbl_month = QLabel(); self.lbl_month.setFixedWidth(160) 
        self.lbl_month.setStyleSheet("font-weight: bold; font-size: 16px; color: #d1d4dc;")
        self.lbl_month.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_next = QPushButton("▶"); btn_next.setFixedWidth(30); btn_next.clicked.connect(self.next_month)
        btn_today = QPushButton("Today"); btn_today.clicked.connect(self.go_today)
        top_bar.addWidget(btn_prev); top_bar.addWidget(self.lbl_month); top_bar.addWidget(btn_next); top_bar.addWidget(btn_today)
        top_bar.addStretch()
        
        self.chk_stack = QCheckBox("Stack PBs")
        self.chk_stack.setChecked(self.config_manager.get("calendar_stack_pbs", default=False))
        self.chk_stack.stateChanged.connect(self.on_toggle_changed)
        
        self.chk_count_new = QCheckBox("Count New as PB")
        self.chk_count_new.setChecked(self.config_manager.get("calendar_count_new", default=False))
        self.chk_count_new.stateChanged.connect(self.on_toggle_changed)
        
        top_bar.addWidget(self.chk_stack)
        top_bar.addSpacing(10)
        top_bar.addWidget(self.chk_count_new)
        
        top_bar.addSpacing(20)
        lbl_legend = QLabel("🏆 Scen PB   🎯 Sens PB")
        lbl_legend.setStyleSheet("color: #787b86; font-size: 11px; margin-right: 5px;")
        top_bar.addWidget(lbl_legend)
        
        layout.addLayout(top_bar)
        
        self.grid_layout = QGridLayout(); self.grid_layout.setSpacing(5)
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, d in enumerate(days):
            lbl = QLabel(d); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); lbl.setStyleSheet("color: #787b86; font-weight: bold;")
            self.grid_layout.addWidget(lbl, 0, i)
        self.cells = []
        for row in range(1, 7):
            for col in range(7):
                cell = DayCell(); cell.clicked.connect(self.on_day_clicked)
                self.grid_layout.addWidget(cell, row, col); self.cells.append(cell)
        layout.addLayout(self.grid_layout)

        self.activity_graph = DailyActivityWidget()
        layout.addSpacing(10); layout.addWidget(self.activity_graph)
        self.detail_panel = DayDetailWidget(self.state_manager, self.config_manager)
        layout.addSpacing(10); layout.addWidget(self.detail_panel, stretch=1)
        self.update_calendar()

    def on_toggle_changed(self):
        self.config_manager.set_global("calendar_stack_pbs", self.chk_stack.isChecked())
        self.config_manager.set_global("calendar_count_new", self.chk_count_new.isChecked())
        # Re-process data with new toggle rules
        if self.full_df is not None:
            self.process_daily_stats(self.full_df)

    def on_data_updated(self, df):
        if df is None or df.empty: return
        self.full_df = df
        if 'DateStr' not in df.columns: df['DateStr'] = df['Timestamp'].dt.strftime('%Y-%m-%d')
        
        self.process_daily_stats(df)
        
        # Set initial date
        if self.daily_stats:
             # Default to last played date if not set
            if not self.selected_date:
                max_date_str = max(self.daily_stats.keys())
                self.selected_date = datetime.datetime.strptime(max_date_str, '%Y-%m-%d').date()
            
            target = self.selected_date
            self.current_date = QDate(target.year, target.month, 1)
            self.update_calendar()
            self.refresh_details()

    def process_daily_stats(self, df):
        """
        Rolling History Calculation (Option B: Day as Container).
        Iterates chronologically, updating baselines day by day.
        """
        self.daily_stats = {}
        
        stack_pbs = self.chk_stack.isChecked()
        count_new = self.chk_count_new.isChecked()

        # 1. Sort
        df = df.sort_values('Timestamp')
        
        # 2. History Trackers
        hist_scen_max = {}
        hist_grid_max = {}
        
        # 3. Group by Date
        # Using groupby(sort=False) respects the chronological sort we just did
        grouped = df.groupby('DateStr', sort=False)
        
        for date_str, group in grouped:
            
            # --- SCENARIO TRACK ---
            # Reuse core logic: _get_pb_indices handles "Start from Baseline" check
            # We must pass the baseline for each group
            scen_pb_count = 0
            unique_scen_pbs = set()
            
            for scen, s_group in group.groupby('Scenario'):
                baseline = hist_scen_max.get(scen)
                # This returns indices relative to s_group
                pb_idxs = stats._get_pb_indices(s_group['Score'], baseline, stack_pbs, count_new)
                
                if pb_idxs:
                    if stack_pbs:
                        scen_pb_count += len(pb_idxs)
                    else:
                        # Unstacked: 1 PB per scenario max
                        scen_pb_count += 1
                        unique_scen_pbs.add(scen)
                
                # Update Running Max for NEXT day (Standard PB logic: Max of All Time)
                day_max = s_group['Score'].max()
                if baseline is None or day_max > baseline:
                    hist_scen_max[scen] = day_max

            # --- SENS/COMBO TRACK ---
            sens_pb_count = 0
            unique_sens_pbs = set() # Store (Scen, Sens) tuples
            
            for (scen, sens), g_group in group.groupby(['Scenario', 'Sens']):
                baseline = hist_grid_max.get((scen, sens))
                pb_idxs = stats._get_pb_indices(g_group['Score'], baseline, stack_pbs, count_new)
                
                if pb_idxs:
                    if stack_pbs:
                        sens_pb_count += len(pb_idxs)
                    else:
                        sens_pb_count += 1
                        unique_sens_pbs.add((scen, sens))
                
                day_max = g_group['Score'].max()
                if baseline is None or day_max > baseline:
                    hist_grid_max[(scen, sens)] = day_max
            
            # Store Result
            self.daily_stats[date_str] = {
                'runs': len(group),
                'duration': group['Duration'].sum(),
                'pbs_scen': scen_pb_count,
                'pbs_sens': sens_pb_count,
                # Store these sets for graph rendering later if needed
                'unique_scen_pbs': unique_scen_pbs,
                'unique_sens_pbs': unique_sens_pbs
            }
        
        self.update_calendar()
        self.refresh_details()

    def update_calendar(self):
        year, month = self.current_date.year(), self.current_date.month()
        self.lbl_month.setText(f"{calendar.month_name[month]} {year}")
        month_prefix = f"{year}-{month:02d}"
        
        # Calculate max activity for month (for heatmap color)
        month_durations = [v['duration'] for k,v in self.daily_stats.items() if k.startswith(month_prefix)]
        max_act = max(month_durations) if month_durations else 3600
        
        first_day = QDate(year, month, 1)
        start_day_of_week = first_day.dayOfWeek() - 1
        current_grid_date = first_day.addDays(-start_day_of_week)
        
        for cell in self.cells:
            py_date = datetime.date(current_grid_date.year(), current_grid_date.month(), current_grid_date.day())
            date_str = py_date.strftime('%Y-%m-%d')
            
            stats = self.daily_stats.get(date_str, None)
            
            is_current = (current_grid_date.month() == month)
            is_sel = (self.selected_date == py_date)
            
            cell.set_data(py_date, stats, is_current, max_act, is_sel)
            current_grid_date = current_grid_date.addDays(1)

    def refresh_details(self):
        if self.selected_date and self.full_df is not None:
            date_str = self.selected_date.strftime('%Y-%m-%d')
            if date_str in self.daily_stats:
                day_df = self.full_df[self.full_df['DateStr'] == date_str].copy()
                
                # For the graph, we need "Valid PBs" lists to draw icons.
                # Since process_daily_stats aggregates counts, we need to reconstruct 
                # valid rows for the graph if we want dots.
                # For V2 simplicity, we can just pass the raw day_df to activity graph,
                # or we can do a mini-recalc for the visualization. 
                # Let's do a mini-recalc of the "Valid PB Rows" using the helper to match counts.
                # Wait, getting the *exact* rows for Stacking ON is easy (it's the indices).
                # But for Stacking OFF, we just want the Max.
                
                # Let's pass the raw df and let ActivityWidget calculate simple peaks for now,
                # OR to be perfect, we replicate the "Get PB Indices" logic for the graph dots.
                # Let's iterate the day_df once here to find the exact PB timestamps for the graph.
                
                stack = self.chk_stack.isChecked()
                count_new = self.chk_count_new.isChecked()
                
                # We need baselines again. This is inefficient (re-calculating history).
                # Optimization: We could store the "Day Start Baseline" in daily_stats.
                # But for a single day click, re-calculating history for one day is fast? 
                # Actually, filtering history < date is fast.
                
                history_df = self.full_df[self.full_df['DateStr'] < date_str]
                
                # Recalculate PB Rows for Graph Visualization
                # SCEN
                base_scen_max = {}
                if not history_df.empty: base_scen_max = history_df.groupby('Scenario')['Score'].max().to_dict()
                valid_scen_rows = []
                for scen, g in day_df.groupby('Scenario'):
                    base = base_scen_max.get(scen)
                    idxs = stats._get_pb_indices(g['Score'], base, stack, count_new)
                    if idxs: valid_scen_rows.append(g.loc[list(idxs)])
                
                # SENS
                base_grid_max = {}
                if not history_df.empty: base_grid_max = history_df.groupby(['Scenario', 'Sens'])['Score'].max().to_dict()
                valid_sens_rows = []
                for k, g in day_df.groupby(['Scenario', 'Sens']):
                    base = base_grid_max.get(k)
                    idxs = stats._get_pb_indices(g['Score'], base, stack, count_new)
                    if idxs: valid_sens_rows.append(g.loc[list(idxs)])
                
                v_scen_df = pd.concat(valid_scen_rows) if valid_scen_rows else pd.DataFrame()
                v_sens_df = pd.concat(valid_sens_rows) if valid_sens_rows else pd.DataFrame()
                
                self.activity_graph.load_data(day_df, stack, v_scen_df, v_sens_df)
                self.detail_panel.load_day(date_str, day_df, self.full_df)
            else:
                # Clear if no data
                self.activity_graph.load_data(None)
                # detail panel clear...

    def on_date_jump_request(self, target_date):
        if hasattr(target_date, 'date'): target_date = target_date.date()
        self.selected_date = target_date
        self.current_date = QDate(target_date.year, target_date.month, 1)
        self.update_calendar()
        self.refresh_details()

    def prev_month(self): self.current_date = self.current_date.addMonths(-1); self.update_calendar()
    def next_month(self): self.current_date = self.current_date.addMonths(1); self.update_calendar()
    def go_today(self): self.current_date = QDate.currentDate(); self.update_calendar()
    def on_day_clicked(self, py_date):
        self.selected_date = py_date
        self.update_calendar()
        self.refresh_details()