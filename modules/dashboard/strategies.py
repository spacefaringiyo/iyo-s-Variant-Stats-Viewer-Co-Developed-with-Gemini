from PyQt6.QtWidgets import QSpinBox, QDoubleSpinBox, QWidget, QHBoxLayout, QLabel, QPushButton
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

# --- HELPER FOR UI CONSISTENCY ---
def make_spin_container(val, min_v, max_v, label_text=None, label_after=False):
    """
    Creates a container with [Label] [SpinBox] OR [SpinBox] [Label]
    Returns the container widget. The SpinBox is accessible via widget.spin
    """
    w = QWidget()
    l = QHBoxLayout(w)
    l.setContentsMargins(0,0,0,0)
    l.setSpacing(5)
    
    sb = QSpinBox()
    sb.setRange(min_v, max_v)
    sb.setValue(val)
    
    lbl = QLabel(label_text) if label_text else None
    
    if label_text and not label_after: l.addWidget(lbl)
    l.addWidget(sb)
    if label_text and label_after: l.addWidget(lbl)
    
    w.spin = sb # Expose for easy access
    return w

# --- FIX: Helpers now accept 'self' to match method signature ---
def standard_get_val(self, w): 
    return w.spin.value()

def standard_set_val(self, w, v): 
    w.spin.setValue(int(v) if v is not None else 0)
# ---------------------------------------------------------------

# --- 1. AGGREGATION MODES ---

class ModePB(AggregationMode):
    name = "Personal Best"
    def get_setting_widget(self):
        # [Rank:] [ 5 ] [ 1 ]
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0,0,0,0)
        l.setSpacing(5)

        l.addWidget(QLabel("Rank:"))
        
        sb = QSpinBox()
        sb.setRange(1, 100)
        sb.setValue(1)
        l.addWidget(sb)

        # Toggle Button
        btn = QPushButton("1")
        btn.setFixedWidth(24) 
        btn.setToolTip("Toggle between Rank 1 and previous value")
        
        def on_toggle():
            current = sb.value()
            if current > 1:
                # Save and jump to 1
                sb.saved_val = current
                sb.setValue(1)
            else:
                # Restore if saved, otherwise default to 5
                target = getattr(sb, 'saved_val', 5)
                sb.setValue(target)

        btn.clicked.connect(on_toggle)
        l.addWidget(btn)

        w.spin = sb 
        return w
    
    # --- NEW: Save Both Numbers ---
    def get_setting_value(self, w):
        # Returns [Current Value, The Hidden "Toggle-Back" Value]
        # We default the hidden value to 5 if it hasn't been set yet
        hidden_val = getattr(w.spin, 'saved_val', 5)
        return [w.spin.value(), hidden_val]

    def set_setting_value(self, w, v):
        # Handle new format [current, hidden] AND old format (int)
        if isinstance(v, list) and len(v) == 2:
            current, hidden = v
            w.spin.setValue(int(current))
            w.spin.saved_val = int(hidden)
        else:
            # Legacy fallback
            val = int(v) if v is not None else 1
            w.spin.setValue(val)
            w.spin.saved_val = 5 # Default if we don't know
    # ------------------------------

    def calculate(self, df, rank):
        # Handle the list input if it comes straight from the widget
        if isinstance(rank, list):
            rank = rank[0] # The first number is the actual rank to calculate
            
        rank = rank if rank else 1
        grouper = ['Scenario', 'Sens']
        if rank == 1: return df.groupby(grouper)['Score'].max().reset_index()
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
        # [ 75] [%]
        return make_spin_container(75, 0, 100, "%", label_after=True)
    
    get_setting_value = standard_get_val
    set_setting_value = standard_set_val

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
            if val < ctx['prev_val']: return QColor(89, 32, 32)
        return None

class HLTarget(HighlightMode):
    name = "Target Score"
    def get_setting_widget(self):
        # [Target:] [ 3000]
        return make_spin_container(3000, 0, 999999, "Target:")

    get_setting_value = standard_get_val
    set_setting_value = standard_set_val

    def get_color(self, val, ctx, target):
        if not target: target = 1000
        if val >= target: return QColor(46, 105, 49)
        else: return QColor(83, 31, 31)
    
class HLRecent(HighlightMode):
    name = "Recent Success"
    def get_setting_widget(self):
        # [Days:] [ 14]
        return make_spin_container(14, 1, 365, "Days:")

    get_setting_value = standard_get_val
    set_setting_value = standard_set_val

    def get_color(self, val, ctx, setting):
        recent = ctx.get('recent_max')
        if recent is None or pd.isna(recent): return None
        if recent >= val: return QColor(46, 105, 49)
        else: return QColor(83, 31, 31)

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