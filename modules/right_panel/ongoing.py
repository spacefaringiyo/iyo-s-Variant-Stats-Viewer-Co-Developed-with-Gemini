from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QLabel, QFrame, 
                             QPushButton, QButtonGroup, QAbstractItemView, 
                             QCheckBox, QComboBox, QSpinBox, QDoubleSpinBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
import pandas as pd
import numpy as np
from core.config_manager import ConfigManager
from modules.charts.chart_widget import ChartWidget, COLORS_CYCLE_10

class OngoingToolbar(QFrame):
    def __init__(self, parent_widget):
        super().__init__()
        self.parent_widget = parent_widget
        self.setStyleSheet("background: #1e222d; border-bottom: 1px solid #363a45;")
        self.setFixedHeight(50)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5,5,5,5)
        
        # 1. Baseline (Converted to Toggle Buttons)
        layout.addWidget(QLabel("Base:"))
        
        # Consistent "Tab-like" style for toggles
        btn_style = """
            QPushButton { 
                background-color: #2a2e39; 
                border: none; 
                padding: 4px 12px; 
                color: #787b86; 
                border-radius: 4px;
            }
            QPushButton:checked { 
                background-color: #2962FF; 
                color: white; 
                font-weight: bold; 
            }
            QPushButton:hover { background-color: #363a45; }
        """

        self.btn_avg = QPushButton("Avg")
        self.btn_avg.setCheckable(True)
        self.btn_avg.setChecked(True)
        self.btn_avg.setStyleSheet(btn_style)
        self.btn_avg.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_75 = QPushButton("75th")
        self.btn_75.setCheckable(True)
        self.btn_75.setStyleSheet(btn_style)
        self.btn_75.setCursor(Qt.CursorShape.PointingHandCursor)

        # QButtonGroup ensures only one can be checked at a time (Radio behavior)
        self.bg = QButtonGroup()
        self.bg.addButton(self.btn_avg)
        self.bg.addButton(self.btn_75)
        self.bg.buttonClicked.connect(parent_widget.refresh_view)
        
        layout.addWidget(self.btn_avg)
        layout.addWidget(self.btn_75)
        
        layout.addSpacing(10)
        
        # 2. Visual Style
        self.cb_vis = QComboBox()
        self.cb_vis.addItems(["Line Plot", "Dot Only", "Filled Area"])
        self.cb_vis.currentIndexChanged.connect(parent_widget.refresh_view)
        layout.addWidget(self.cb_vis)
        
        # 3. Color
        self.chk_color = QCheckBox("Color by Scenario")
        self.chk_color.setChecked(True)
        self.chk_color.stateChanged.connect(parent_widget.refresh_view)
        layout.addWidget(self.chk_color)
        
        # hide spin box is removed. moved to settings
        
        # 5. Indicators
        self.chk_trend = QCheckBox("Trend"); self.chk_trend.setChecked(True)
        # NEW: Tooltip
        self.chk_trend.setToolTip("Cumulative Average.\n"
                                  "Shows your average score accumulating over the displayed runs.")
        self.chk_trend.stateChanged.connect(parent_widget.refresh_view)
        layout.addWidget(self.chk_trend)
        
        self.chk_flow = QCheckBox("Flow"); self.chk_flow.setChecked(True)
        # NEW: Tooltip
        self.chk_flow.setToolTip("Short-term Rhythm (5-run Rolling Average).\n"
                                 "Visualizes your immediate consistency and warm-up/fatigue cycles.")
        self.chk_flow.stateChanged.connect(parent_widget.refresh_view)
        layout.addWidget(self.chk_flow)
        
        self.chk_sma = QCheckBox("SMA")
        # NEW: Tooltip
        self.chk_sma.setToolTip("Simple Moving Average.\n"
                                "Averages the last N runs to reduce noise.")
        self.chk_sma.stateChanged.connect(parent_widget.refresh_view)
        layout.addWidget(self.chk_sma)
        
        self.sb_sma = QSpinBox(); self.sb_sma.setRange(2, 50); self.sb_sma.setValue(5)
        self.sb_sma.valueChanged.connect(parent_widget.refresh_view)
        layout.addWidget(self.sb_sma)
        
        layout.addStretch()

class OngoingWidget(QWidget):
    def __init__(self, state_manager):
        super().__init__()
        self.state_manager = state_manager
        self.config_manager = ConfigManager()
        
        self.full_df = None
        self.display_df = None # Holds the processed rolling stats
        
        self.setup_ui()
        self.state_manager.data_updated.connect(self.on_data_updated)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        # Toolbar
        self.toolbar = OngoingToolbar(self)
        saved_vis = self.config_manager.get("ongoing_vis_style", default="Line Plot")
        self.toolbar.cb_vis.setCurrentText(saved_vis)
        layout.addWidget(self.toolbar)

        # Graph
        self.chart = ChartWidget(self.state_manager, listen_to_global_signals=False)
        self.chart.setMinimumHeight(250)
        layout.addWidget(self.chart, stretch=2)

        # Table
        self.table = QTableWidget()
        columns = ["Scenario", "Sens", "Score", "vs Avg", "vs 75th", "vs PB"]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.itemClicked.connect(self.on_table_clicked)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, len(columns)): header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self.table, stretch=3)

    def on_table_clicked(self, item):
        row = item.row()
        scen_item = self.table.item(row, 0)
        sens_item = self.table.item(row, 1)
        
        if scen_item and sens_item:
            scenario = scen_item.text()
            try:
                sens_str = sens_item.text().replace("cm", "").strip()
                sens_val = float(sens_str)
            except:
                sens_val = None
                
            self.state_manager.variant_selected.emit({
                'scenario': scenario,
                'sens': sens_val
            })

    def on_data_updated(self, df):
        if df is None: return
        
        # 1. Sort strictly by timestamp
        df = df.sort_values('Timestamp').copy()
        
        # 2. Define the Grouper
        g = df.groupby(['Scenario', 'Sens'])
        
        # 3. Calculate Rolling Stats using TRANSFORM
        # transform() applies the function and maps the result back to the 
        # original index automatically. This prevents the misalignment bug.
        
        # Note: We must use a lambda because 'expanding().mean()' returns a frame/series
        # that transform handles best this way for window operations.
        
        df['Rolling_Avg'] = g['Score'].transform(lambda x: x.expanding().mean().shift(1))
        df['Rolling_75'] = g['Score'].transform(lambda x: x.expanding().quantile(0.75).shift(1))
        df['Rolling_PB'] = g['Score'].transform(lambda x: x.expanding().max().shift(1))
        
        # 4. Filter to recent 50
        self.display_df = df.tail(50).iloc[::-1] # Reverse for table (Newest Top)
        
        self.refresh_view()


    def refresh_view(self):
        if self.display_df is None or self.display_df.empty: return
        
        self.config_manager.set_global("ongoing_vis_style", self.toolbar.cb_vis.currentText())
        
        is_avg_mode = self.toolbar.btn_avg.isChecked() 
        vis_style = self.toolbar.cb_vis.currentText()
        use_color = self.toolbar.chk_color.isChecked()
        
        # Load Filters
        min_pct = self.config_manager.get("ongoing_min_pct", default=-1000.0)
        max_pct = self.config_manager.get("ongoing_max_pct", default=1000.0)
        
        graph_points = []
        table_rows = []
        
        unique_scens = sorted(self.display_df['Scenario'].unique())
        color_map = {scen: COLORS_CYCLE_10[i % len(COLORS_CYCLE_10)] for i, scen in enumerate(unique_scens)}

        for idx, row in self.display_df.iterrows():
            score = row['Score']
            
            baseline = row['Rolling_Avg'] if is_avg_mode else row['Rolling_75']
            pct = 0.0
            is_new = False
            
            if pd.notna(baseline) and baseline > 0:
                pct = ((score - baseline) / baseline) * 100
            else:
                # Baseline is NaN = This is a New/Baseline Run
                is_new = True
                pct = 0.0 

            # --- FILTER LOGIC ---
            # FIX: Always show "New" runs, regardless of the % filter.
            if not is_new:
                if pct < min_pct or pct > max_pct:
                    continue
            # --------------------
            
            table_rows.append(row)
            
            vs_str = "Baseline Run" if is_new else f"{pct:+.1f}% vs {'Avg' if is_avg_mode else '75th'}"
            meta = {'scenario': row['Scenario'], 'sens': row['Sens'], 'score': score, 'subtext': vs_str}
            pt_color = color_map[row['Scenario']] if use_color else '#2962FF'
            
            graph_points.append({
                'time': int(row['Timestamp'].timestamp()),
                'value': pct,
                'label': row['Scenario'],
                'color': pt_color, 
                'meta': meta
            })

        # --- DRAW GRAPH (Reverse chronological for plotting) ---
        graph_points = graph_points[::-1]
        
        segments = []
        separators = []
        
        if graph_points:
            current_scen = graph_points[0]['label']
            current_segment = {'data': [], 'color': graph_points[0]['color']}
            
            for p in graph_points:
                scen = p['label']
                if scen != current_scen:
                    segments.append(current_segment)
                    current_segment = {'data': [], 'color': p['color']}
                    current_scen = scen
                    separators.append(p['time'])
                
                current_segment['data'].append(p)
            segments.append(current_segment)

        payload = []
        for i, seg in enumerate(segments):
            item = {
                'data': seg['data'],
                'color': seg['color'],
                'width': 2,
                'filled': (vis_style == "Filled Area"),
                'fill_negative': True,
            }
            if vis_style == "Dot Only": item['width'] = 0
            payload.append(item)
            
            if i < len(segments) - 1:
                next_seg = segments[i+1]
                last_pt = seg['data'][-1]
                first_pt = next_seg['data'][0]
                bridge_data = [last_pt, first_pt]
                bridge_item = {
                    'data': bridge_data,
                    'color': next_seg['color'], 
                    'width': 2,
                    'filled': (vis_style == "Filled Area"),
                    'fill_negative': True
                }
                if vis_style == "Dot Only": bridge_item['width'] = 0
                payload.append(bridge_item)

        # Indicators
        all_y = [p['value'] for p in graph_points]
        all_t = [p['time'] for p in graph_points]
        
        if len(all_y) > 1:
            series = pd.Series(all_y)
            if self.toolbar.chk_trend.isChecked():
                trend = series.expanding().mean().values
                trend_data = [{'time': t, 'value': v} for t, v in zip(all_t, trend)]
                payload.append({'data': trend_data, 'color': '#FF9800', 'width': 3})
            
            if self.toolbar.chk_flow.isChecked():
                flow = series.rolling(5).mean().values
                flow_data = [{'time': t, 'value': v} for t, v in zip(all_t, flow) if not np.isnan(v)]
                payload.append({'data': flow_data, 'color': '#E040FB', 'width': 3})
                
            if self.toolbar.chk_sma.isChecked():
                n = self.toolbar.sb_sma.value()
                sma = series.rolling(n).mean().values
                sma_data = [{'time': t, 'value': v} for t, v in zip(all_t, sma) if not np.isnan(v)]
                payload.append({'data': sma_data, 'color': '#00E5FF', 'width': 3})

        self.chart.plot_payload(payload, separators=separators)

        # --- DRAW TABLE ---
        self.table.setRowCount(len(table_rows))
        for row_idx, row in enumerate(table_rows):
            score = row['Score']
            
            self.table.setItem(row_idx, 0, QTableWidgetItem(row['Scenario']))
            self.table.setItem(row_idx, 1, QTableWidgetItem(f"{row['Sens']}cm"))
            self.table.setItem(row_idx, 2, QTableWidgetItem(f"{score:.0f}"))
            
            def set_cell(col_idx, baseline, is_pb_check=False):
                item = QTableWidgetItem()
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                
                # Check for New
                if pd.isna(baseline):
                    item.setText("NEW!")
                    item.setForeground(QColor("#4aa3df"))
                    self.table.setItem(row_idx, col_idx, item)
                    return

                # Check for PB
                if is_pb_check:
                    if score > baseline:
                        item.setText("🏆 PB")
                        item.setForeground(QColor("#FFD700"))
                        item.setToolTip(f"Previous Best: {baseline:.0f}")
                    else:
                        item.setText("-")
                    self.table.setItem(row_idx, col_idx, item)
                    return

                # Normal comparison
                if baseline > 0:
                    pct = ((score - baseline)/baseline)*100
                    item.setText(f"{pct:+.1f}%")
                    if pct > 0: item.setForeground(QColor("#4CAF50"))
                    elif pct < 0: item.setForeground(QColor("#EF5350"))
                    else: item.setForeground(QColor("#787b86"))
                    item.setToolTip(f"Baseline: {baseline:.1f}")
                else:
                    item.setText("-")
                
                self.table.setItem(row_idx, col_idx, item)

            set_cell(3, row['Rolling_Avg'])
            set_cell(4, row['Rolling_75'])
            set_cell(5, row['Rolling_PB'], is_pb_check=True)