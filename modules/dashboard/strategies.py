from PyQt6.QtWidgets import QSpinBox, QDoubleSpinBox, QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
import pandas as pd
import numpy as np

# --- BASE CLASSES ---

class StrategyBase:
    name = "Base"
    def get_setting_widget(self): return None
    def get_setting_value(self, widget): return None
    def set_setting_value(self, widget, value): pass

class AggregationMode(StrategyBase):
    def calculate(self, df, setting_val): pass

class HighlightMode(StrategyBase):
    def get_color(self, val, ctx, setting_val): pass

# --- 1. AGGREGATION MODES ---

# FIX: All modes now strictly group by ['Scenario', 'Sens']
# This ensures the pivot table columns are always Sensitivities.

class ModePB(AggregationMode):
    name = "Personal Best"
    def get_setting_widget(self):
        sb = QSpinBox(); sb.setRange(1, 100); sb.setPrefix("#")
        return sb
    def get_setting_value(self, w): return w.value()
    def set_setting_value(self, w, v): w.setValue(v)

    def calculate(self, df, rank):
        rank = rank if rank else 1
        grouper = ['Scenario', 'Sens']
        
        if rank == 1:
            return df.groupby(grouper)['Score'].max().reset_index()
        
        def get_nth(g): return g.nlargest(rank).iloc[-1] if len(g) >= rank else np.nan
        return df.groupby(grouper)['Score'].apply(get_nth).reset_index()

class ModeAvg(AggregationMode):
    name = "Average Score"
    def calculate(self, df, val):
        return df.groupby(['Scenario', 'Sens'])['Score'].mean().reset_index()

class ModeCount(AggregationMode):
    name = "Play Count"
    def calculate(self, df, val):
        return df.groupby(['Scenario', 'Sens'])['Score'].size().reset_index()

class ModePercentile(AggregationMode):
    name = "Nth Percentile"
    def get_setting_widget(self):
        sb = QDoubleSpinBox(); sb.setRange(0, 100); sb.setValue(75.0); sb.setSuffix("%")
        return sb
    def get_setting_value(self, w): return w.value()
    def set_setting_value(self, w, v): w.setValue(v)

    def calculate(self, df, p):
        p = (p / 100.0) if p else 0.75
        return df.groupby(['Scenario', 'Sens'])['Score'].quantile(p).reset_index()

# --- 2. HIGHLIGHT MODES ---

class HLRowHeatmap(HighlightMode):
    name = "Row Heatmap"
    def get_color(self, val, ctx, setting):
        r_min, r_max = ctx['r_min'], ctx['r_max']
        if r_max <= r_min: return None
        ratio = (val - r_min)/(r_max - r_min)
        return get_traffic_light_color(ratio)

class HLGlobalHeatmap(HighlightMode):
    name = "Global Heatmap"
    def get_color(self, val, ctx, setting):
        g_min, g_max = ctx['g_min'], ctx['g_max']
        if g_max <= g_min: return None
        ratio = (val - g_min)/(g_max - g_min)
        return get_traffic_light_color(ratio)

class HLDrop(HighlightMode):
    name = "Performance Drop"
    def get_color(self, val, ctx, setting):
        if ctx.get('prev_val') is not None:
            if val < ctx['prev_val']:
                return QColor(89, 32, 32) # Dark Red
        return None

class HLTarget(HighlightMode):
    name = "Target Score"
    def get_setting_widget(self):
        # FIX: Container with Label + SpinBox (Integers only)
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0,0,0,0)
        l.addWidget(QLabel("Target:"))
        
        sb = QSpinBox() # Use QSpinBox for integers, not Double
        sb.setRange(0, 999999)
        sb.setValue(3000)
        
        l.addWidget(sb)
        w.spin = sb # Store ref
        return w

    def get_setting_value(self, w): return w.spin.value()
    def set_setting_value(self, w, v): w.spin.setValue(v)

    def get_color(self, val, ctx, target):
        if not target: target = 1000
        # FIX: Binary logic
        if val >= target: return QColor(46, 105, 49) # Green
        else: return QColor(83, 31, 31) # Red
    
class HLRecent(HighlightMode):
    name = "Recent Success"
    def get_setting_widget(self):
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0,0,0,0)
        l.addWidget(QLabel("Days:"))
        sb = QSpinBox()
        sb.setRange(1, 365); sb.setValue(14)
        l.addWidget(sb)
        w.spin = sb
        return w

    def get_setting_value(self, w): return w.spin.value()
    def set_setting_value(self, w, v):
        try:
            val = int(float(v if v is not None else 14))
            w.spin.setValue(val)
        except: w.spin.setValue(14)

    def get_color(self, val, ctx, setting):
        # Value from the map passed by GridWidget
        recent = ctx.get('recent_max')
        
        # 1. Not Played Recently -> Gray (Default)
        if recent is None or pd.isna(recent): 
            return None
            
        # 2. Played Recently
        if recent >= val: 
            return QColor(46, 105, 49) # Green (Hit the target)
        else: 
            return QColor(83, 31, 31) # Red (Missed the target)

class HLNone(HighlightMode):
    name = "None"
    def get_color(self, val, ctx, setting): return None

# --- UTILS ---
def get_traffic_light_color(ratio):
    ratio = max(0.0, min(1.0, ratio))
    c_red = np.array([120, 47, 47])
    c_yel = np.array([122, 118, 50])
    c_grn = np.array([54, 107, 54])
    
    if ratio < 0.5:
        local_r = ratio * 2
        res = (1 - local_r) * c_red + local_r * c_yel
    else:
        local_r = (ratio - 0.5) * 2
        res = (1 - local_r) * c_yel + local_r * c_grn
    return QColor(int(res[0]), int(res[1]), int(res[2]))

AGGREGATION_MODES = [ModePB, ModePercentile, ModeAvg, ModeCount]
HIGHLIGHT_MODES = [HLRowHeatmap, HLGlobalHeatmap, HLDrop, HLTarget, HLRecent, HLNone]