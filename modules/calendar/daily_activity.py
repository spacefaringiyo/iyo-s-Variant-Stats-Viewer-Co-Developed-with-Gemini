import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

class DailyActivityWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Slightly taller to accommodate icons comfortably
        self.setFixedHeight(120) 
        
        # Plot Setup
        pg.setConfigOption('background', '#131722')
        pg.setConfigOption('foreground', '#d1d4dc')
        pg.setConfigOptions(antialias=True)
        
        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=False, y=False)
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.hideButtons()
        
        # Axis Style
        ax_b = self.plot.getAxis('bottom')
        ax_b.setTicks([
            [(0, '00:00'), (6, '06:00'), (12, '12:00'), (18, '18:00'), (24, '24:00')],
            []
        ])
        ax_b.setPen(color='#363a45')
        ax_b.setTextPen(color='#787b86')
        
        self.plot.getAxis('left').hide()

        # --- VIEWPORT SETTINGS ---
        # 0.00 to 0.50 = The Graph (Green Mountain)
        # 0.50 to 0.75 = The Sky (Where icons live)
        self.plot.setYRange(0, 0.75)
        self.plot.setXRange(0, 24)
        
        layout.addWidget(self.plot)

    def load_data(self, day_df, stack_pbs=True, valid_scen_pbs=None, valid_sens_pbs=None):
        self.plot.clear()
        if day_df is None or day_df.empty: return
        
        # 1. Activity Curve (30m bins)
        bins = np.zeros(48)
        day_start = day_df['Timestamp'].min().floor('D')
        start_ts = day_start.timestamp()
        
        for _, row in day_df.iterrows():
            rel_sec = row['Timestamp'].timestamp() - start_ts
            rel_hour = rel_sec / 3600.0
            bin_idx = int(rel_hour * 2) 
            if 0 <= bin_idx < 48: bins[bin_idx] += row['Duration'] / 1800.0

        data = pd.Series(bins)
        
        # 2. SMOOTHING & CLIPPING
        # Rolling average for smoothness
        smoothed = data.rolling(window=3, center=True, min_periods=1).mean().values
        
        # FORCE PLATEAU: Clip values to 0.50 max.
        # This ensures the graph never touches the icons at > 0.50
        smoothed = np.clip(smoothed, 0, 0.50)

        x_axis = np.linspace(0, 24, 48)
        c = QColor("#4CAF50"); c.setAlpha(50)
        brush = pg.mkBrush(c); pen = pg.mkPen("#4CAF50", width=2)
        self.plot.plot(x_axis, smoothed, pen=pen, brush=brush, fillLevel=0)
        
        # 3. PB Markers (10m bins)
        pb_bins = {}
        
        def add_to_bins(df, type_key):
            if df is None or df.empty: return
            work_df = df.copy()
            if not stack_pbs:
                # Group by [Scenario, Sens], pick Max Score
                idx_to_keep = work_df.groupby(['Scenario', 'Sens'])['Score'].idxmax()
                work_df = work_df.loc[idx_to_keep]
            
            for _, row in work_df.iterrows():
                rel_sec = row['Timestamp'].timestamp() - start_ts
                bin_idx = int((rel_sec / 3600.0) * 6)
                if bin_idx not in pb_bins: pb_bins[bin_idx] = {'scen': 0, 'sens': 0}
                pb_bins[bin_idx][type_key] += 1

        add_to_bins(valid_scen_pbs, 'scen')
        add_to_bins(valid_sens_pbs, 'sens')
                
        # Draw Icons
        for b_idx, counts in pb_bins.items():
            x_pos = (b_idx / 6.0) + (1/12.0)
            
            def get_font(cnt):
                f = QFont()
                if cnt >= 3: f.setPointSize(18)
                elif cnt == 2: f.setPointSize(14)
                else: f.setPointSize(10)
                return f

            # Scen (Top) -> Sits at 0.65
            if counts['scen'] > 0:
                item = pg.TextItem("🏆", color="#FFD700", anchor=(0.5, 0.5))
                item.setFont(get_font(counts['scen']))
                item.setPos(x_pos, 0.65)
                self.plot.addItem(item)
                
            # Sens (Bottom) -> Sits at 0.55 (Just above the 0.50 plateau)
            if counts['sens'] > 0:
                item = pg.TextItem("🎯", color="#00E5FF", anchor=(0.5, 0.5))
                item.setFont(get_font(counts['sens']))
                item.setPos(x_pos, 0.55)
                self.plot.addItem(item)