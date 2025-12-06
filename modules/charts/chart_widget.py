import datetime
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
                             QCheckBox, QSpinBox, QFrame, QDoubleSpinBox, QPushButton, QButtonGroup)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QPen, QFont
from core.config_manager import ConfigManager
import time

# --- COLOR PALETTES ---
COLORS_CYCLE_10 = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', 
    '#9467bd', '#8c564b', '#e377c2', '#7f7f0f', 
    '#bcbd22', '#17becf'
]
COLORS_CYCLE_4 = [
    '#1f77b4', '#ff7f0e', '#9467bd', '#d62728'
]

class DateAxis(pg.AxisItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.index_to_time = {}
    def set_lookup(self, lookup_dict): self.index_to_time = lookup_dict
    def tickStrings(self, values, scale, spacing):
        strings = []
        for v in values:
            idx = int(v)
            if idx in self.index_to_time:
                dt = datetime.datetime.fromtimestamp(self.index_to_time[idx])
                strings.append(dt.strftime('%b %d'))
            else: strings.append("")
        return strings

class ChartToolbar(QFrame):
    param_changed = pyqtSignal()
    
    def __init__(self, config_manager):
        super().__init__()
        self.config = config_manager
        self.setStyleSheet("background: #1e222d; border-bottom: 1px solid #363a45;")
        self.setFixedHeight(85)
        main_layout = QVBoxLayout(self); main_layout.setContentsMargins(5, 5, 5, 5); main_layout.setSpacing(5)
        
        # ROW 1
        row1 = QHBoxLayout(); row1.setSpacing(5)
        self.mode_group = QButtonGroup(); self.mode_group.setExclusive(True); self.mode_group.buttonClicked.connect(self.param_changed)
        modes = ["Raw Data", "Grouped Avg", "Daily Avg", "Weekly Avg", "Monthly Avg", "Session Avg"]
        self.mode_btns = {}
        for m in modes:
            btn = QPushButton(m); btn.setCheckable(True)
            btn.setStyleSheet("""QPushButton { background: #2a2e39; border: none; padding: 4px 8px; color: #787b86; font-size: 11px; } QPushButton:checked { background: #2962FF; color: white; font-weight: bold; } QPushButton:hover { background: #363a45; }""")
            self.mode_group.addButton(btn); row1.addWidget(btn); self.mode_btns[m] = btn
        self.mode_btns["Raw Data"].setChecked(True)
        
        row1.addSpacing(10)
        
        self.cb_visual = QComboBox(); self.cb_visual.addItems(["Line Plot", "Dot Only", "Filled Area"])
        self.cb_visual.currentIndexChanged.connect(self.param_changed)
        # NEW: Save on change
        self.cb_visual.currentIndexChanged.connect(self.save_global_state)
        row1.addWidget(self.cb_visual)
        
        row1.addStretch()
        
        self.chk_color = QCheckBox("Color by Session"); self.chk_color.setChecked(True); self.chk_color.stateChanged.connect(self.on_color_toggled); self.chk_color.stateChanged.connect(self.param_changed); row1.addWidget(self.chk_color)
        self.chk_4color = QCheckBox("4-Color Cycle"); self.chk_4color.setVisible(True); self.chk_4color.stateChanged.connect(self.param_changed); row1.addWidget(self.chk_4color)
        main_layout.addLayout(row1)
        
        # ROW 2
        row2 = QHBoxLayout(); row2.setSpacing(15)
        row2.addWidget(QLabel("Hide <")); self.sb_hide = QDoubleSpinBox(); self.sb_hide.setRange(0, 999999); self.sb_hide.setValue(5); self.sb_hide.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons); self.sb_hide.setFixedWidth(60); self.sb_hide.valueChanged.connect(self.param_changed); row2.addWidget(self.sb_hide)
        self.chk_connect = QCheckBox("Connect Sessions"); self.chk_connect.stateChanged.connect(self.param_changed); row2.addWidget(self.chk_connect)
        self.lbl_group = QLabel("N="); self.sb_group = QSpinBox(); self.sb_group.setRange(2, 100); self.sb_group.setValue(5); self.sb_group.valueChanged.connect(self.param_changed); row2.addWidget(self.lbl_group); row2.addWidget(self.sb_group); self.set_group_visible(False)
        row2.addStretch()

        self.chk_trend = QCheckBox("Trend")
        self.chk_trend.setStyleSheet("color: #FF9800; font-weight: bold;")
        # NEW: Tooltip
        self.chk_trend.setToolTip("Expanding Mean (Cumulative Average).\n"
                                  "Shows your 'All-Time Average' up to that specific point in time.\n"
                                  "Useful for seeing long-term improvement baseline.")
        self.chk_trend.stateChanged.connect(self.param_changed)
        row2.addWidget(self.chk_trend)

        self.smas = []
        colors = ['#FFFFFF', '#00E5FF', '#76FF03']; defaults = [5, 10, 50]
        for i in range(3):
            f = QFrame(); l = QHBoxLayout(f); l.setContentsMargins(0,0,0,0); l.setSpacing(5)
            chk = QCheckBox("SMA")
            # NEW: Tooltip
            chk.setToolTip("Simple Moving Average.\n"
                           "Calculates the average of the last N runs.\n"
                           "Smoothes out volatility to show medium-term performance.")
            
            chk.setStyleSheet(f"color: {colors[i]}")
            chk.stateChanged.connect(self.param_changed)
            
            sb = QSpinBox(); sb.setRange(2, 999); sb.setValue(defaults[i]); sb.setFixedWidth(60); sb.valueChanged.connect(self.param_changed)
            l.addWidget(chk); l.addWidget(sb); row2.addWidget(f); self.smas.append({'chk': chk, 'sb': sb, 'color': colors[i]})
        main_layout.addLayout(row2)
        
        self.on_color_toggled()
        self.load_global_state()

    def on_color_toggled(self): self.chk_4color.setVisible(self.chk_color.isChecked())
    def set_group_visible(self, visible): self.lbl_group.setVisible(visible); self.sb_group.setVisible(visible)
    def get_mode(self): btn = self.mode_group.checkedButton(); return btn.text() if btn else "Raw Data"
    
    def save_global_state(self):
        state = {
            "group_n": self.sb_group.value(), 
            "color_by_session": self.chk_color.isChecked(), 
            "use_4_color": self.chk_4color.isChecked(), 
            "connect_sessions": self.chk_connect.isChecked(), 
            "career_trend": self.chk_trend.isChecked(),
            # NEW: Save Visual Style
            "visual_style": self.cb_visual.currentText(),
            "smas": [{'on': s['chk'].isChecked(), 'val': s['sb'].value()} for s in self.smas]
        }
        self.config.set_global("chart_global", state)

    def load_global_state(self):
        state = self.config.get("chart_global", default={})
        if not state: return
        
        if "group_n" in state: self.sb_group.setValue(state["group_n"])
        if "color_by_session" in state: self.chk_color.setChecked(state["color_by_session"])
        if "use_4_color" in state: self.chk_4color.setChecked(state["use_4_color"])
        if "connect_sessions" in state: self.chk_connect.setChecked(state["connect_sessions"])
        if "career_trend" in state: self.chk_trend.setChecked(state["career_trend"])
        # NEW: Load Visual Style
        if "visual_style" in state: self.cb_visual.setCurrentText(state["visual_style"])
        
        if "smas" in state:
            for i, d in enumerate(state["smas"]):
                if i < len(self.smas): self.smas[i]['chk'].setChecked(d['on']); self.smas[i]['sb'].setValue(d['val'])
        
        self.on_color_toggled()

class ChartWidget(QWidget):
    def __init__(self, state_manager, listen_to_global_signals=True):
        super().__init__()
        self.state_manager = state_manager
        self.listen_to_global = listen_to_global_signals
        self.config = ConfigManager()
        self.all_runs_df = None; self.current_data_df = None; self.active_scenario_key = None
        self.index_to_time_map = {}
        self.index_to_meta = {} 
        self.last_variant_time = 0 # NEW: For debouncing
        
        self.layout = QVBoxLayout(self); self.layout.setContentsMargins(0, 0, 0, 0); self.layout.setSpacing(0)
        self.toolbar = ChartToolbar(self.config); self.toolbar.param_changed.connect(self.reprocess_and_plot); self.toolbar.sb_hide.valueChanged.connect(self.save_per_graph_settings)
        self.toolbar.chk_color.stateChanged.connect(self.toolbar.save_global_state); self.toolbar.chk_4color.stateChanged.connect(self.toolbar.save_global_state); self.toolbar.chk_connect.stateChanged.connect(self.toolbar.save_global_state); self.toolbar.chk_trend.stateChanged.connect(self.toolbar.save_global_state); self.toolbar.sb_group.valueChanged.connect(self.toolbar.save_global_state)
        for s in self.toolbar.smas: s['chk'].stateChanged.connect(self.toolbar.save_global_state); s['sb'].valueChanged.connect(self.toolbar.save_global_state)
        if self.listen_to_global: self.layout.addWidget(self.toolbar)
        else: self.toolbar.hide()
        pg.setConfigOption('background', '#131722'); pg.setConfigOption('foreground', '#d1d4dc'); pg.setConfigOptions(antialias=True)
        self.date_axis = DateAxis(orientation='top'); self.plot_widget = pg.PlotWidget(axisItems={'top': self.date_axis}); self.plot_widget.showGrid(x=True, y=True, alpha=0.5); self.plot_widget.getAxis('bottom').setLabel("Run Number")
        for ax in ['bottom', 'left', 'top']: self.plot_widget.getAxis(ax).setPen(color='#363a45'); self.plot_widget.getAxis(ax).setTextPen(color='#787b86')
        self.layout.addWidget(self.plot_widget); self.setup_overlays()
        self.state_manager.data_updated.connect(self.on_data_updated)
        if self.listen_to_global: 
            self.state_manager.scenario_selected.connect(self.on_sidebar_selected)
            self.state_manager.variant_selected.connect(self.on_variant_selected)

    def setup_overlays(self):
        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('#787b86', style=Qt.PenStyle.DashLine)); self.h_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('#787b86', style=Qt.PenStyle.DashLine)); self.plot_widget.addItem(self.v_line, ignoreBounds=True); self.plot_widget.addItem(self.h_line, ignoreBounds=True)
        self.label = pg.TextItem(text="", color="#d1d4dc", anchor=(0, 1)); self.plot_widget.addItem(self.label, ignoreBounds=True)
        self.proxy = pg.SignalProxy(self.plot_widget.scene().sigMouseMoved, rateLimit=60, slot=self.mouse_moved)
        self.title_lbl = pg.TextItem(text="", color="#d1d4dc", anchor=(0, 0))
        font = QFont(); font.setBold(True); font.setPointSize(14); self.title_lbl.setFont(font); self.plot_widget.addItem(self.title_lbl)

    def mouse_moved(self, evt):
        pos = evt[0]
        if self.plot_widget.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            index = int(round(mouse_point.x()))
            self.v_line.setPos(index)
            self.h_line.setPos(mouse_point.y())
            
            text_lines = []
            idx_map = getattr(self, 'index_to_time_map', {})
            if index in idx_map:
                dt = datetime.datetime.fromtimestamp(idx_map[index])
                text_lines.append(dt.strftime('%Y-%m-%d %H:%M'))
            
            meta_map = getattr(self, 'index_to_meta', {})
            if index in meta_map:
                m = meta_map[index]
                if 'scenario' in m:
                    line = m['scenario']
                    if m.get('sens'): line += f" ({m['sens']}cm)"
                    text_lines.append(line)
                if 'score' in m: text_lines.append(f"Score: {m['score']:.1f}")
                if 'subtext' in m: text_lines.append(m['subtext'])
            else: text_lines.append(f"{mouse_point.y():.1f}")

            self.label.setText("\n".join(text_lines))
            self.label.setPos(index, mouse_point.y())

    def on_data_updated(self, df): self.all_runs_df = df
    
    def on_sidebar_selected(self, scenario_name): 
        # Check if a specific variant was selected very recently (debounce 200ms)
        if (time.time() - self.last_variant_time) < 0.2:
            return
        self.load_graph(scenario_name, None)

    def on_variant_selected(self, payload): 
        self.last_variant_time = time.time() 
        self.load_graph(payload['scenario'], payload['sens'])

    def load_graph(self, scenario_name, sens_val):
        if self.all_runs_df is None: return
        mask = self.all_runs_df['Scenario'] == scenario_name; df = self.all_runs_df[mask].copy()
        if sens_val is not None: df = df[df['Sens'] == sens_val]; self.active_scenario_key = f"{scenario_name}_{sens_val}cm"; display_title = f"{scenario_name} ({sens_val}cm)"
        else: self.active_scenario_key = scenario_name; display_title = f"{scenario_name} (All Sens)"
        if df.empty: self.plot_widget.clear(); self.state_manager.chart_title_changed.emit("No Data"); self.current_data_df = None; return
        df.sort_values('Timestamp', inplace=True); self.current_data_df = df; self.current_display_title = display_title
        saved = self.config.get("chart_settings", scenario=self.active_scenario_key, default={}); val = saved.get("hide_low", 5.0)
        self.toolbar.sb_hide.blockSignals(True); self.toolbar.sb_hide.setValue(val); self.toolbar.sb_hide.blockSignals(False); self.reprocess_and_plot()

    def save_per_graph_settings(self):
        if self.active_scenario_key: self.config.set_scenario(self.active_scenario_key, "chart_settings", {"hide_low": self.toolbar.sb_hide.value()})

    def reprocess_and_plot(self):
        if self.current_data_df is None: return
        df = self.current_data_df.copy()
        cutoff = self.toolbar.sb_hide.value()
        
        if cutoff > 0: df = df[df['Score'] >= cutoff]
        if df.empty: self.plot_widget.clear(); self.state_manager.chart_title_changed.emit("Filtered to Empty"); return
        
        # --- NEW: Calculate Global Min for Filling ---
        global_min_y = df['Score'].min()
        # ---------------------------------------------

        self.plot_widget.clear()
        self.plot_widget.addItem(self.v_line, ignoreBounds=True)
        self.plot_widget.addItem(self.h_line, ignoreBounds=True)
        self.plot_widget.addItem(self.label, ignoreBounds=True)
        self.index_to_time_map = {}
        self.index_to_meta = {} # Ensure meta dict is reset
        
        mode = self.toolbar.get_mode()
        vis_style = self.toolbar.cb_visual.currentText()
        use_connect = self.toolbar.chk_connect.isChecked()
        color_by_sess = self.toolbar.chk_color.isChecked()
        use_4_color = self.toolbar.chk_4color.isChecked()
        
        self.toolbar.set_group_visible(mode == "Grouped Avg")
        
        segments = []; ACTIVE_CYCLE = COLORS_CYCLE_4 if use_4_color else COLORS_CYCLE_10
        if 'SessionID' in df.columns: u_sess = sorted(df['SessionID'].unique()); sess_map = {sid: i for i, sid in enumerate(u_sess)}
        else: sess_map = {}
        
        def get_sess_color(sid):
            if not color_by_sess: return '#2962FF'
            seq_idx = sess_map.get(sid, 0); return ACTIVE_CYCLE[seq_idx % len(ACTIVE_CYCLE)]
            
        if mode == "Raw Data":
            y_all = df['Score'].values; x_all = np.arange(len(y_all));
            for i, ts in enumerate(df['Timestamp'].apply(lambda t: t.timestamp())): self.index_to_time_map[i] = ts
            
            # Populate Meta for Raw Data (Tooltip support)
            for i, row in enumerate(df.itertuples()):
                self.index_to_meta[i] = {'score': row.Score, 'scenario': row.Scenario, 'sens': row.Sens}

            if 'SessionID' in df.columns:
                df['idx'] = x_all
                for sid, group in df.groupby('SessionID', sort=False): segments.append({'x': group['idx'].values, 'y': group['Score'].values, 'color': get_sess_color(int(sid))})
            else: segments.append({'x': x_all, 'y': y_all, 'color': '#2962FF'})
        else:
            if mode == "Grouped Avg": n = self.toolbar.sb_group.value(); df['Group'] = np.arange(len(df)) // n; grouped = df.groupby('Group')
            elif mode == "Session Avg": grouped = df.groupby('SessionID')
            elif mode == "Daily Avg": grouped = df.groupby(pd.Grouper(key='Timestamp', freq='D'))
            elif mode == "Weekly Avg": grouped = df.groupby(pd.Grouper(key='Timestamp', freq='W'))
            elif mode == "Monthly Avg": grouped = df.groupby(pd.Grouper(key='Timestamp', freq='M'))
            agg = grouped['Score'].mean().dropna(); agg_t = grouped['Timestamp'].max().dropna(); common = agg.index.intersection(agg_t.index); agg = agg.loc[common]; agg_t = agg_t.loc[common]
            y_vals = agg.values; x_vals = np.arange(len(y_vals));
            for i, ts in enumerate(agg_t.apply(lambda t: t.timestamp())): self.index_to_time_map[i] = ts
            segments.append({'x': x_vals, 'y': y_vals, 'color': '#FF9800'})
            
        for i, seg in enumerate(segments):
            x = seg['x']; y = seg['y']; c = seg['color']
            
            # Scatter
            scatter = pg.ScatterPlotItem(x=x, y=y, size=6, brush=pg.mkBrush(c), pen=pg.mkPen(None))
            self.plot_widget.addItem(scatter)
            
            if vis_style in ["Line Plot", "Filled Area"]:
                pen = pg.mkPen(c, width=2); brush = None
                if vis_style == "Filled Area": 
                    col = QColor(c); col.setAlpha(50); brush = pg.mkBrush(col)
                
                # FIX: Use global_min_y instead of 0
                fill_level = global_min_y if brush else None
                self.plot_widget.plot(x, y, pen=pen, brush=brush, fillLevel=fill_level)
                
            if use_connect and i < len(segments) - 1:
                next_seg = segments[i+1]; x_b = [x[-1], next_seg['x'][0]]; y_b = [y[-1], next_seg['y'][0]]; c_b = next_seg['color']; pen_b = pg.mkPen(c_b, width=2)
                
                brush = None
                if vis_style == "Filled Area":
                    col = QColor(c_b); col.setAlpha(50); brush = pg.mkBrush(col)
                
                fill_level = global_min_y if brush else None
                self.plot_widget.plot(x_b, y_b, pen=pen_b, brush=brush, fillLevel=fill_level)
                
        if segments:
            y_full = np.concatenate([s['y'] for s in segments]); x_full = np.arange(len(y_full)); series = pd.Series(y_full)
            for sma in self.toolbar.smas:
                if sma['chk'].isChecked(): val = series.rolling(window=sma['sb'].value()).mean().values; self.plot_widget.plot(x_full, val, pen=pg.mkPen(sma['color'], width=3))
            if self.toolbar.chk_trend.isChecked(): tr = series.expanding().mean().values; self.plot_widget.plot(x_full, tr, pen=pg.mkPen('#FF9800', width=3))
            title_txt = f"{self.current_display_title} ({len(y_full)} runs)"; self.state_manager.chart_title_changed.emit(title_txt)
            self.plot_widget.addItem(pg.InfiniteLine(pos=np.mean(y_full), angle=0, pen=pg.mkPen('#787b86', style=Qt.PenStyle.DashLine))); self.plot_widget.addItem(pg.InfiniteLine(pos=np.percentile(y_full, 75), angle=0, pen=pg.mkPen('#4CAF50', style=Qt.PenStyle.DashLine)))
        
        self.date_axis.set_lookup(self.index_to_time_map)
        self.plot_widget.enableAutoRange()

    # --- PLOT PAYLOAD (With Zero Line) ---
    def plot_payload(self, payload_list, title=None, separators=None):
        self.plot_widget.clear()
        self.index_to_time_map = {}
        self.index_to_meta = {} 
        
        self.plot_widget.addItem(self.v_line, ignoreBounds=True)
        self.plot_widget.addItem(self.h_line, ignoreBounds=True)
        self.plot_widget.addItem(self.label, ignoreBounds=True)
        if title: self.state_manager.chart_title_changed.emit(title)

        # Explicit Zero Line
        zero_line = pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen('#d1d4dc', width=1, style=Qt.PenStyle.SolidLine))
        zero_line.setZValue(-5) 
        self.plot_widget.addItem(zero_line)
        
        global_max_y = -999999
        global_min_y = 999999 # NEW: Track global min

        # 1. First Pass: Collect Time & Range
        all_timestamps = set()
        for item in payload_list:
            if not item.get('data'): continue
            for p in item['data']:
                val = p['value']
                all_timestamps.add(p['time'])
                if not np.isnan(val):
                    global_max_y = max(global_max_y, val)
                    global_min_y = min(global_min_y, val) # Track min
        
        # Safety for empty data
        if global_min_y == 999999: global_min_y = 0

        sorted_times = sorted(list(all_timestamps))
        time_to_index = {t: i for i, t in enumerate(sorted_times)}
        self.index_to_time_map = {i: t for t, i in time_to_index.items()}
            
        for item in payload_list:
            if not item.get('data'): continue
            for p in item['data']:
                if 'meta' in p:
                    idx = time_to_index[p['time']]
                    self.index_to_meta[idx] = p['meta']

        # Draw Separators
        if separators:
            for sep_time in separators:
                if sep_time in time_to_index:
                    idx = time_to_index[sep_time]
                    vline = pg.InfiniteLine(pos=idx - 0.5, angle=90, pen=pg.mkPen('#363a45', width=1, style=Qt.PenStyle.DashLine))
                    self.plot_widget.addItem(vline)

        # 2. Second Pass: Plot
        for item in payload_list:
            if not item.get('data'): continue
            
            valid_points = [p for p in item['data'] if not np.isnan(p['value'])]
            if not valid_points: continue

            y = [p['value'] for p in valid_points]
            x = [time_to_index[p['time']] for p in valid_points]
            
            color = item.get('color', '#FFF')
            width = item.get('width', 2)
            pen = pg.mkPen(color, width=width)
            symbol = 'o' if width < 3 else None
            
            brush = None
            fill_val = None
            
            if item.get('filled', False):
                c = QColor(color); c.setAlpha(50)
                brush = pg.mkBrush(c)
                
                # Logic:
                # Session Report (fill_negative=True) -> Fill to 0
                # Main Grid (fill_negative=False) -> Fill to Global Min
                if item.get('fill_negative', False):
                    fill_val = 0
                else:
                    fill_val = global_min_y
                
            self.plot_widget.plot(x, y, pen=pen, symbol=symbol, symbolBrush=color, symbolSize=5, brush=brush, fillLevel=fill_val)
            
            if item.get('fill_negative', False):
                y_arr = np.array(y); y_neg = np.copy(y_arr); y_neg[y_neg > 0] = 0
                neg_col = QColor(255, 0, 0, 50)
                self.plot_widget.plot(x, y_neg, pen=None, brush=pg.mkBrush(neg_col), fillLevel=0)

        self.date_axis.set_lookup(self.index_to_time_map)
        self.plot_widget.enableAutoRange()
