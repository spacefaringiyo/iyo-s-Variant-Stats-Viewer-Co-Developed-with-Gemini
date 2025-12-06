from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
                             QCheckBox, QScrollArea, QComboBox, QSizePolicy, QGridLayout, QPushButton)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
import pandas as pd
import numpy as np
from collections import defaultdict
from core.analytics import stats
from core.config_manager import ConfigManager
from modules.charts.chart_widget import ChartWidget, COLORS_CYCLE_10

class ClickableCard(QFrame):
    clicked = pyqtSignal(str, object) 
    def __init__(self, scenario, sens):
        super().__init__()
        self.scenario = scenario
        self.sens = sens
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.scenario, self.sens)
        super().mousePressEvent(event)

class SessionToolbar(QFrame):
    def __init__(self, parent_widget, config_manager):
        super().__init__()
        self.config = config_manager
        self.setStyleSheet("background: #1e222d; border-bottom: 1px solid #363a45;")
        self.setFixedHeight(50)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5,5,5,5)
        
        # --- NEW: NAV ARROWS ---
        self.btn_prev = QPushButton("◀")
        self.btn_prev.setFixedWidth(30)
        self.btn_prev.clicked.connect(parent_widget.nav_prev_session)
        layout.addWidget(self.btn_prev)
        
        self.btn_next = QPushButton("▶")
        self.btn_next.setFixedWidth(30)
        self.btn_next.clicked.connect(parent_widget.nav_next_session)
        layout.addWidget(self.btn_next)
        
        layout.addSpacing(10)
        # -----------------------
        
        # Load Defaults
        g_scen = self.config.get("session_group_scen", default=False)
        c_scen = self.config.get("session_color_scen", default=True)
        show_trend = self.config.get("session_show_trend", default=True)
        show_flow = self.config.get("session_show_flow", default=True)
        
        self.chk_group_scen = QCheckBox("Group by Scenario")
        self.chk_group_scen.setChecked(g_scen)
        self.chk_group_scen.stateChanged.connect(parent_widget.save_and_refresh)
        layout.addWidget(self.chk_group_scen)
        
        layout.addSpacing(10)
        
        layout.addWidget(QLabel("Sort:"))
        self.cb_sort = QComboBox()
        self.cb_sort.addItems(["Performance", "Most Played", "Time", "A-Z"])
        self.cb_sort.currentIndexChanged.connect(parent_widget.refresh_view)
        layout.addWidget(self.cb_sort)
        
        layout.addSpacing(10)
        
        self.cb_vis = QComboBox()
        self.cb_vis.addItems(["Line Plot", "Dot Only", "Filled Area"])
        self.cb_vis.currentIndexChanged.connect(parent_widget.refresh_view)
        layout.addWidget(self.cb_vis)
        
        self.chk_color = QCheckBox("Color by Scenario")
        self.chk_color.setChecked(c_scen)
        self.chk_color.stateChanged.connect(parent_widget.save_and_refresh)
        layout.addWidget(self.chk_color)
        
        self.chk_trend = QCheckBox("Trend")
        self.chk_trend.setChecked(show_trend)
        # NEW: Tooltip
        self.chk_trend.setToolTip("Session Cumulative Average.\n"
                                  "Shows if you are generally improving or declining throughout this specific session.")
        self.chk_trend.stateChanged.connect(parent_widget.save_and_refresh)
        layout.addWidget(self.chk_trend)
        
        self.chk_flow = QCheckBox("Flow")
        self.chk_flow.setChecked(show_flow)
        # NEW: Tooltip
        self.chk_flow.setToolTip("Short-term Rhythm (5-run Rolling Average).\n"
                                 "Visualizes your immediate consistency within this session.")
        self.chk_flow.stateChanged.connect(parent_widget.save_and_refresh)
        layout.addWidget(self.chk_flow)
        
        layout.addStretch()

class SessionReportWidget(QWidget):
    def __init__(self, state_manager):
        super().__init__()
        self.state_manager = state_manager
        self.config_manager = ConfigManager()
        
        self.full_df = None
        self.summary = None
        self.current_session_id = None
        self.stack_pbs = False 
        self.count_new = False
        
        self.setup_ui()
        
        self.state_manager.data_updated.connect(self.on_data_updated)
        self.state_manager.session_selected.connect(self.on_session_selected)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0,0,0,0)
        
        # 1. Header (Metrics)
        self.header = QFrame()
        self.header.setStyleSheet("background: #1e222d; border-bottom: 1px solid #363a45;")
        self.header.setFixedHeight(80)
        self.header_layout = QHBoxLayout(self.header)
        main_layout.addWidget(self.header)
        
        # 2. Toolbar
        self.toolbar = SessionToolbar(self, self.config_manager)
        
        saved_vis = self.config_manager.get("session_vis_style", default="Line Plot")
        self.toolbar.cb_vis.setCurrentText(saved_vis)
        
        main_layout.addWidget(self.toolbar)

        # 3. Chart
        self.chart = ChartWidget(self.state_manager, listen_to_global_signals=False)
        self.chart.setMinimumHeight(300)
        main_layout.addWidget(self.chart, stretch=2)

        # 4. Lists
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: #131722; border: none;")
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(10, 10, 10, 10)
        self.scroll_layout.setSpacing(10)
        self.scroll.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll, stretch=3)

    def nav_prev_session(self):
        self._navigate_session(-1)

    def nav_next_session(self):
        self._navigate_session(1)

    def _navigate_session(self, direction):
        if self.full_df is None or self.current_session_id is None: return
        
        # Get sorted list of IDs
        all_ids = sorted(self.full_df['SessionID'].unique())
        
        try:
            curr_idx = all_ids.index(self.current_session_id)
            new_idx = curr_idx + direction
            
            if 0 <= new_idx < len(all_ids):
                new_id = all_ids[new_idx]
                # Emit signal to update everything (Manager title, List selection, Report)
                self.state_manager.session_selected.emit(int(new_id))
        except ValueError:
            pass

    def save_and_refresh(self):
        self.config_manager.set_global("session_group_scen", self.toolbar.chk_group_scen.isChecked())
        self.config_manager.set_global("session_color_scen", self.toolbar.chk_color.isChecked())
        self.config_manager.set_global("session_show_trend", self.toolbar.chk_trend.isChecked())
        self.config_manager.set_global("session_show_flow", self.toolbar.chk_flow.isChecked())
        self.refresh_view()

    # --- CRITICAL UPDATE: Handle Toggles ---
    def set_view_options(self, stack_pbs, count_new):
        needs_refresh = False
        if self.stack_pbs != stack_pbs:
            self.stack_pbs = stack_pbs
            needs_refresh = True
            
        if self.count_new != count_new:
            self.count_new = count_new
            needs_refresh = True
            
        if needs_refresh or True: # Force refresh to be safe
            if self.current_session_id is not None:
                self.on_session_selected(self.current_session_id)

    def on_data_updated(self, df): 
        self.full_df = df
        if self.current_session_id is not None:
            self.on_session_selected(self.current_session_id)

    def on_session_selected(self, session_id):
        self.current_session_id = session_id 
        if self.full_df is None: return
        if session_id not in self.full_df['SessionID'].values: return

        session_df = self.full_df[self.full_df['SessionID'] == session_id].copy()
        session_df.sort_values('Timestamp', inplace=True)
        
        # DIRECT PASS: No local filtering
        self.summary = stats.analyze_session(
            session_df, 
            self.full_df, 
            stack_pbs=self.stack_pbs, 
            count_new=self.count_new
        )
        
        if not self.summary: return
        self.refresh_view()

    def refresh_view(self):
        if not self.summary: return
        
        self.config_manager.set_global("session_vis_style", self.toolbar.cb_vis.currentText())
        
        # LOAD FILTERS
        min_pct = self.config_manager.get("session_min_pct", default=-1000.0)
        max_pct = self.config_manager.get("session_max_pct", default=1000.0)
        
        view_mode = 'scenario' if self.toolbar.chk_group_scen.isChecked() else 'grid'
        data = self.summary[view_mode]
        meta = self.summary['meta']
        
        vis_style = self.toolbar.cb_vis.currentText()
        use_color = self.toolbar.chk_color.isChecked()
        
        scen_pbs = self.summary['scenario']['pb_count']
        sens_pbs = self.summary['grid']['pb_count']
        self.refresh_metrics(meta, scen_pbs, sens_pbs)
        
        # 2. Plot
        raw_points = data['graph_data']
        unique_scens = sorted(list(set(p['scenario'] for p in raw_points)))
        color_map = {scen: COLORS_CYCLE_10[i % len(COLORS_CYCLE_10)] for i, scen in enumerate(unique_scens)}
        
        # Filtered Points List
        filtered_points = []
        
        for p in raw_points:
            # --- FILTER ---
            if p['pct'] < min_pct or p['pct'] > max_pct:
                continue
            # --------------
            
            p['color_hex'] = color_map[p['scenario']] if use_color else '#2962FF'
            p['meta'] = {
                'scenario': p['scenario'],
                'sens': p['sens'],
                'subtext': f"{p['pct']:.1f}% vs Avg"
            }
            filtered_points.append(p)
        
        # Re-assign filtered points to raw_points for the segment logic
        raw_points = filtered_points
        
        segments = []
        separators = []
        if raw_points:
            curr_scen_name = raw_points[0]['scenario']
            curr_seg = {'data': [], 'color': raw_points[0]['color_hex']}
            for p in raw_points:
                if p['scenario'] != curr_scen_name:
                    segments.append(curr_seg)
                    curr_seg = {'data': [], 'color': p['color_hex']}
                    curr_scen_name = p['scenario']
                    separators.append(p['time'])
                curr_seg['data'].append(p)
            segments.append(curr_seg)

        payload = []
        for i, seg in enumerate(segments):
            chart_data = [{'time': p['time'], 'value': p['pct'], 'meta': p['meta']} for p in seg['data']]
            item = {
                'data': chart_data,
                'color': seg['color'],
                'width': 2,
                'filled': (vis_style == "Filled Area"),
                'fill_negative': True
            }
            if vis_style == "Dot Only": item['width'] = 0
            payload.append(item)
            
            if i < len(segments) - 1:
                next_seg = segments[i+1]
                last_p = seg['data'][-1]
                first_p = next_seg['data'][0]
                bridge_data = [{'time': last_p['time'], 'value': last_p['pct']}, {'time': first_p['time'], 'value': first_p['pct']}]
                bridge = {'data': bridge_data, 'color': next_seg['color'], 'width': 2, 'filled': (vis_style == "Filled Area"), 'fill_negative': True}
                if vis_style == "Dot Only": bridge['width'] = 0
                payload.append(bridge)

        if self.toolbar.chk_trend.isChecked():
            trend_pts = [{'time': p['time'], 'value': p['trend_pct']} for p in raw_points]
            payload.append({'data': trend_pts, 'color': '#FF9800', 'width': 3})
            
        if self.toolbar.chk_flow.isChecked():
            flow_pts = [{'time': p['time'], 'value': p['flow_pct']} for p in raw_points]
            payload.append({'data': flow_pts, 'color': '#E040FB', 'width': 3})

        self.chart.plot_payload(payload, separators=separators)
        self.render_lists(data['lists'])

    def refresh_metrics(self, meta, scen_pb_count, sens_pb_count):
        while self.header_layout.count(): 
            child = self.header_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
            
        def add_metric(label, val, is_clickable=False):
            vbox = QVBoxLayout()
            vbox.setSpacing(2)
            
            l1 = QLabel(label)
            l1.setStyleSheet("color: #787b86; font-size: 10px; font-weight: bold;")
            l1.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # DATE CLICK LOGIC
            if is_clickable:
                # Need to import QPushButton at top of file
                from PyQt6.QtWidgets import QPushButton 
                btn = QPushButton(str(val))
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet("""
                    QPushButton { 
                        font-size: 16px; font-weight: bold; color: #4aa3df; 
                        border: none; background: transparent; 
                    }
                    QPushButton:hover { text-decoration: underline; color: #64b5f6; }
                """)
                # Parse date string for jump
                try:
                    dt = pd.to_datetime(val, format='%b %d, %Y')
                    btn.clicked.connect(lambda: self.state_manager.request_date_jump.emit(dt))
                except: pass
                vbox.addWidget(l1)
                vbox.addWidget(btn)
            else:
                l2 = QLabel(str(val))
                l2.setStyleSheet("font-size: 16px; font-weight: bold; color: #d1d4dc;")
                l2.setAlignment(Qt.AlignmentFlag.AlignCenter)
                vbox.addWidget(l1)
                vbox.addWidget(l2)
            
            container = QWidget()
            container.setLayout(vbox)
            self.header_layout.addWidget(container)
            self.header_layout.addStretch()

        date_str = meta['date_str']
        try:
            dt = pd.to_datetime(date_str, format='%B %d, %Y')
            date_str = dt.strftime('%b %d, %Y')
        except: pass

        def parse_dur(s):
            try:
                parts = list(map(int, s.split(':')))
                return parts[0]*3600 + parts[1]*60 + parts[2]
            except: return 0
        dur_sec = parse_dur(meta['duration_str'])
        act_sec = parse_dur(meta['active_str'])
        density = (act_sec / dur_sec * 100) if dur_sec > 0 else 0.0

        self.header_layout.addStretch()
        add_metric("DATE", date_str, is_clickable=True) # <--- Clickable
        add_metric("DURATION", meta['duration_str'])
        add_metric("ACTIVE", meta['active_str'])
        add_metric("DENSITY", f"{density:.1f}%")
        add_metric("PLAYS", meta['play_count'])
        add_metric("PBs", f"{scen_pb_count} 🏆   {sens_pb_count} 🎯")

    def render_lists(self, lists):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        sort_mode = self.toolbar.cb_sort.currentText()

        # PBs
        if lists['pbs']:
            self.add_header(f"Personal Bests ({len(lists['pbs'])})", "#4CAF50")
            
            grouped_pbs = defaultdict(list)
            for item in lists['pbs']:
                key = (item['name'], item.get('sens'))
                grouped_pbs[key].append(item)
            group_list = list(grouped_pbs.items())
            
            if sort_mode == "Performance":
                group_list.sort(key=lambda x: max(i['imp_pct'] for i in x[1]), reverse=True)
            elif sort_mode == "Most Played":
                group_list.sort(key=lambda x: len(x[1]), reverse=True)
            elif sort_mode == "Time":
                group_list.sort(key=lambda x: min(i['time'] for i in x[1]))
            elif sort_mode == "A-Z":
                group_list.sort(key=lambda x: x[0][0].lower())
            
            for key, items in group_list:
                self.add_pb_flow_card(key[0], key[1], items)

        # Avg Comparison
        if lists['avgs']:
            self.add_header("Average Comparison", "#FF9800")
            if sort_mode == "Performance":
                lists['avgs'].sort(key=lambda x: x['diff_pct'], reverse=True)
            elif sort_mode == "Time":
                lists['avgs'].sort(key=lambda x: x['time'])
            elif sort_mode == "A-Z":
                lists['avgs'].sort(key=lambda x: x['name'].lower())
            for item in lists['avgs']: self.add_avg_card(item)

        # Scenarios Played
        self.add_header("Scenarios Played", "#2962FF")
        if sort_mode == "Performance":
            lists['played'].sort(key=lambda x: ((x['best']-x['avg'])/x['avg'] if x['avg']>0 else -1), reverse=True)
        elif sort_mode == "Most Played":
            lists['played'].sort(key=lambda x: x['count'], reverse=True)
        elif sort_mode == "Time":
            lists['played'].sort(key=lambda x: x['time'])
        elif sort_mode == "A-Z":
            lists['played'].sort(key=lambda x: x['name'].lower())
        for item in lists['played']: self.add_played_card(item)
            
        self.scroll_layout.addStretch()

    def add_header(self, text, color):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 14px; margin-top: 10px; border-bottom: 1px solid #363a45; padding-bottom: 5px;")
        self.scroll_layout.addWidget(lbl)

    def add_pb_flow_card(self, name, sens, pb_items):
        pb_items.sort(key=lambda x: x['score'])
        start_pb = pb_items[0]['prev']
        end_pb = pb_items[-1]['score']
        total_gain = end_pb - start_pb
        total_gain_pct = (total_gain / start_pb * 100) if start_pb > 0 else 0
        
        frame = ClickableCard(name, sens)
        frame.clicked.connect(self.on_card_clicked)
        
        frame.setObjectName("pb_card")
        frame.setStyleSheet("""
            QFrame#pb_card {
                background: #1e222d; 
                border-radius: 4px; 
                border-left: 3px solid #4CAF50;
            }
            QFrame#pb_card:hover { background: #2a2e39; } 
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        
        r1 = QHBoxLayout()
        r1.setContentsMargins(0,0,0,0)
        name_txt = name
        if sens: name_txt += f" {sens}cm"
        lbl_name = QLabel(name_txt)
        lbl_name.setStyleSheet("font-weight: bold; font-size: 13px; color: #d1d4dc; border: none; background: transparent;")
        lbl_gain = QLabel(f"+{total_gain:.0f}  +{total_gain_pct:.1f}%")
        lbl_gain.setStyleSheet("font-weight: bold; color: #4CAF50; border: none; background: transparent;")
        r1.addWidget(lbl_name); r1.addStretch(); r1.addWidget(lbl_gain)
        layout.addLayout(r1)
        
        r2 = QHBoxLayout()
        r2.setContentsMargins(0,0,0,0)
        r2.setSpacing(5)
        
        def create_badge(score, gain_pct=None, is_trophy=False, is_ghost=False):
            badge = QFrame()
            badge.setMinimumWidth(80); badge.setMaximumWidth(120)
            badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            if is_ghost: bg, border, text_col = "transparent", "1px dashed #555", "#787b86"
            elif is_trophy: bg, border, text_col = "#332a00", "1px solid #FFD700", "#FFD700"
            else: bg, border, text_col = "#0d260d", "1px solid #2E7D32", "#4CAF50"
            badge.setStyleSheet(f".QFrame {{ background: {bg}; border: {border}; border-radius: 4px; }}")
            g = QGridLayout(badge); g.setContentsMargins(4, 4, 4, 4); g.setSpacing(0)
            if is_trophy:
                lbl_spacer = QLabel(); lbl_spacer.setFixedWidth(15); lbl_spacer.setStyleSheet("border: none; background: transparent;")
                g.addWidget(lbl_spacer, 0, 0)
            s_lbl = QLabel(f"{score:.0f}"); s_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s_lbl.setStyleSheet(f"color: {text_col}; font-weight: bold; font-size: 13px; border: none; background: transparent;")
            g.addWidget(s_lbl, 0, 1)
            if is_trophy:
                t_lbl = QLabel("🏆"); t_lbl.setFixedWidth(15); t_lbl.setStyleSheet("font-size: 11px; border: none; background: transparent;")
                g.addWidget(t_lbl, 0, 2)
            if gain_pct is not None:
                g_lbl = QLabel(f"+{gain_pct:.1f}%"); g_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                g_lbl.setStyleSheet(f"color: {text_col}; font-size: 10px; margin-top: 1px; border: none; background: transparent;")
                g.addWidget(g_lbl, 1, 0, 1, 3) 
            return badge

        r2.addWidget(create_badge(start_pb, is_ghost=True))
        prev_step_score = start_pb
        for i, item in enumerate(pb_items):
            current_score = item['score']; is_final = (i == len(pb_items) - 1)
            arrow = QLabel("➜"); arrow.setStyleSheet("color: #787b86; font-size: 16px; font-weight: bold; border: none; background: transparent;")
            r2.addWidget(arrow)
            step_gain_pct = 0
            if prev_step_score > 0: step_gain_pct = ((current_score - prev_step_score) / prev_step_score) * 100
            r2.addWidget(create_badge(current_score, step_gain_pct, is_trophy=is_final))
            prev_step_score = current_score 
        r2.addStretch()
        layout.addLayout(r2)
        self.scroll_layout.addWidget(frame)

    def add_avg_card(self, item):
        frame = ClickableCard(item['name'], item.get('sens'))
        frame.clicked.connect(self.on_card_clicked)
        frame.setStyleSheet("""
            QFrame { background: #1e222d; border-radius: 4px; }
            QFrame:hover { background: #2a2e39; }
        """)
        
        # Main Vertical Layout
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        
        # ROW 1: Scenario Name
        name = item['name']
        if item.get('sens'): name += f" ({item['sens']}cm)"
        lbl_name = QLabel(name)
        lbl_name.setStyleSheet("font-weight: bold; font-size: 13px; color: #d1d4dc;")
        layout.addWidget(lbl_name)
        
        # ROW 2: Stats Grid
        r2 = QHBoxLayout()
        r2.setSpacing(15)
        
        # Session Block (Using HTML formatting for colors)
        sess_txt = f"Session: <span style='color:#d1d4dc; font-weight:bold;'>{item['sess_avg']:.1f}</span> <span style='color:#787b86;'>({item['sess_cnt']})</span>"
        lbl_sess = QLabel(sess_txt)
        lbl_sess.setStyleSheet("font-size: 12px; color: #787b86;")
        r2.addWidget(lbl_sess)
        
        # All Time Block
        all_txt = f"All Time: <span style='color:#d1d4dc; font-weight:bold;'>{item['all_avg']:.1f}</span> <span style='color:#787b86;'>({item['all_cnt']})</span>"
        lbl_all = QLabel(all_txt)
        lbl_all.setStyleSheet("font-size: 12px; color: #787b86;")
        r2.addWidget(lbl_all)
        
        r2.addStretch()
        
        # Diff %
        color = "#4CAF50" if item['diff_pct'] > 0 else "#EF5350"
        diff_text = f"{item['diff_pct']:+.1f}%"
        lbl_diff = QLabel(diff_text)
        lbl_diff.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 13px;")
        r2.addWidget(lbl_diff)
        
        layout.addLayout(r2)
        self.scroll_layout.addWidget(frame)

    def add_played_card(self, item):
        border = "border-left: 3px solid gold;" if item['is_pb'] else ""
        frame = ClickableCard(item['name'], item.get('sens'))
        frame.clicked.connect(self.on_card_clicked)
        frame.setStyleSheet(f"""
            QFrame {{ background: #1e222d; border-radius: 4px; {border} }}
            QFrame:hover {{ background: #2a2e39; }}
        """)
        layout = QHBoxLayout(frame)
        name = item['name']
        if item.get('sens'): name += f" ({item['sens']}cm)"
        if item['is_pb']: name = "🏆 " + name
        layout.addWidget(QLabel(name))
        layout.addStretch()
        layout.addWidget(QLabel(f"{item['count']} runs | Best: {item['best']:.0f} | Avg: {item['avg']:.1f}"))
        self.scroll_layout.addWidget(frame)

    def on_card_clicked(self, scenario, sens):
        self.state_manager.variant_selected.emit({
            'scenario': scenario,
            'sens': sens
        })