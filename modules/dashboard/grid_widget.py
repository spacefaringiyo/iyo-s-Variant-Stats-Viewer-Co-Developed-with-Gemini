from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QLabel, QFrame, QHBoxLayout, 
                             QAbstractItemView, QComboBox, QRadioButton, 
                             QCheckBox, QButtonGroup, QMenu, QDialog, QListWidget, QPushButton,
                             QGridLayout, QToolTip)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QCursor
import pandas as pd
import numpy as np
import re
from core.analytics import parsers, stats
from modules.dashboard import strategies
from modules.dashboard.tooltip import CustomTooltip

# --- DIALOGS ---
class ManageHiddenDialog(QDialog):
    def __init__(self, hidden_scens, hidden_cms, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Hidden Items")
        self.resize(500, 400)
        self.hidden_scens = list(hidden_scens)
        self.hidden_cms = list(hidden_cms)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        grid = QGridLayout()
        layout.addLayout(grid)
        
        # Scenarios
        grid.addWidget(QLabel("Hidden Scenarios:"), 0, 0)
        self.list_scens = QListWidget()
        self.list_scens.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_scens.addItems(sorted(self.hidden_scens))
        grid.addWidget(self.list_scens, 1, 0)
        
        btn_unhide_scen = QPushButton("Unhide Selected Scenario(s)")
        btn_unhide_scen.clicked.connect(self.unhide_scen)
        grid.addWidget(btn_unhide_scen, 2, 0)
        
        # CMs
        grid.addWidget(QLabel("Hidden Sens/CMs:"), 0, 1)
        self.list_cms = QListWidget()
        self.list_cms.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_cms.addItems(sorted(self.hidden_cms))
        grid.addWidget(self.list_cms, 1, 1)
        
        btn_unhide_cm = QPushButton("Unhide Selected CM(s)")
        btn_unhide_cm.clicked.connect(self.unhide_cm)
        grid.addWidget(btn_unhide_cm, 2, 1)
        
        # Close
        btn_box = QHBoxLayout()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_box.addStretch()
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)

    def unhide_scen(self):
        items = self.list_scens.selectedItems()
        if not items: return
        texts_to_remove = [item.text() for item in items]
        for txt in texts_to_remove:
            if txt in self.hidden_scens: self.hidden_scens.remove(txt)
        self.list_scens.clear()
        self.list_scens.addItems(sorted(self.hidden_scens))

    def unhide_cm(self):
        items = self.list_cms.selectedItems()
        if not items: return
        texts_to_remove = [item.text() for item in items]
        for txt in texts_to_remove:
            if txt in self.hidden_cms: self.hidden_cms.remove(txt)
        self.list_cms.clear()
        self.list_cms.addItems(sorted(self.hidden_cms))

# --- MAIN WIDGET ---
class GridWidget(QWidget):
    def __init__(self, state_manager, config_manager):
        super().__init__()
        self.state_manager = state_manager
        self.config_manager = config_manager
        
        self.all_runs_df = None
        self.current_family_df = None # Used for Family View
        self.playlist_scenarios = []  # Used for Playlist View
        
        self.base_name = "" # Represents Scenario Name OR Playlist Name
        self.is_playlist_mode = False # Toggle
        
        self.is_loading_state = False
        self.recent_data_map = {}
        
        self.agg_strategies = {cls.name: cls() for cls in strategies.AGGREGATION_MODES}
        self.hl_strategies = {cls.name: cls() for cls in strategies.HIGHLIGHT_MODES}
        self.active_agg = self.agg_strategies["Personal Best"]
        self.active_hl = self.hl_strategies["Row Heatmap"]

        self.hidden_scenarios = set()
        self.hidden_cms = set()

        self.agg_setting_widget = None
        self.hl_setting_widget = None
        self.format_checkboxes = {} 
        self.current_axis = "Sens"
        self.axis_filter_cache = {} 
        
        self.tooltip = CustomTooltip(self)
        self.tooltip.hide()

        self.setup_ui()
        
        self.state_manager.data_updated.connect(self.on_data_updated)
        
        # --- FIX: REMOVED GLOBAL LISTENER ---
        # self.state_manager.scenario_selected.connect(self.on_scenario_selected)
        # Tabs should only update when explicitly commanded by the Container,
        # not by eavesdropping on global navigation events.
        # ------------------------------------

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        
        # Row 1
        self.row1 = self.create_toolbar_row("Compare by:")
        self.axis_container = QHBoxLayout()
        self.row1.layout().addLayout(self.axis_container)
        self.row1.layout().addStretch()
        self.axis_group = QButtonGroup(self)
        self.axis_group.buttonClicked.connect(self.on_axis_changed)
        layout.addWidget(self.row1)

        # Row 2
        self.row2 = self.create_toolbar_row("Filter Format:")
        self.format_container = QHBoxLayout()
        self.row2.layout().addLayout(self.format_container)
        self.row2.layout().addStretch()
        layout.addWidget(self.row2)
        self.row2.setVisible(False)

        # Row 3
        self.row3 = self.create_toolbar_row("Sens Step:")
        self.sens_combo = QComboBox()
        self.sens_combo.addItems(["All", "2cm", "3cm", "5cm", "10cm"])
        self.sens_combo.currentIndexChanged.connect(self.on_control_changed)
        self.row3.layout().addWidget(self.sens_combo)
        self.row3.layout().addSpacing(20)
        self.row3.layout().addWidget(QLabel("Mode:"))
        self.mode_group = QButtonGroup(self)
        self.mode_group.buttonClicked.connect(self.on_mode_changed)
        for mode_cls in strategies.AGGREGATION_MODES:
            btn = QRadioButton(mode_cls.name)
            self.row3.layout().addWidget(btn)
            self.mode_group.addButton(btn)
            if mode_cls.name == "Personal Best": btn.setChecked(True)
        self.agg_setting_container = QHBoxLayout()
        self.row3.layout().addLayout(self.agg_setting_container)
        self.row3.layout().addStretch()
        layout.addWidget(self.row3)

        # Row 4
        self.row4 = self.create_toolbar_row("Highlight:")
        self.hl_group = QButtonGroup(self)
        self.hl_group.buttonClicked.connect(self.on_highlight_changed)
        for hl_cls in strategies.HIGHLIGHT_MODES:
            btn = QRadioButton(hl_cls.name)
            self.row4.layout().addWidget(btn)
            self.hl_group.addButton(btn)
            if hl_cls.name == "Row Heatmap": btn.setChecked(True)
        self.hl_setting_container = QHBoxLayout()
        self.row4.layout().addLayout(self.hl_setting_container)
        self.row4.layout().addStretch()
        
        btn_help = QPushButton("(?)")
        btn_help.setCursor(Qt.CursorShape.WhatsThisCursor)
        btn_help.setStyleSheet("""
            QPushButton { background: transparent; border: none; color: #787b86; font-weight: bold; margin-right: 10px; text-align: left; }
            QPushButton:hover { color: #d1d4dc; }
        """)
        help_text = ("Controls:\n- Left Click cell: Load detailed graph.\n- Right Click header/cell: Hide.\n- Middle Click tab: Close tab.")
        btn_help.setToolTip(help_text) 
        btn_help.clicked.connect(lambda: QToolTip.showText(QCursor.pos(), help_text, btn_help))
        self.row4.layout().addWidget(btn_help)
        
        btn_manage = QPushButton("Manage Hidden")
        btn_manage.clicked.connect(self.open_manage_hidden)
        self.row4.layout().addWidget(btn_manage)
        layout.addWidget(self.row4)

        # Table
        self.grid = QTableWidget()
        self.grid.verticalHeader().setVisible(False)
        self.grid.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.grid.cellClicked.connect(self.on_cell_clicked)
        self.grid.setMouseTracking(True)
        self.grid.cellEntered.connect(self.on_cell_entered)
        self.grid.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(self.on_table_context_menu)
        self.grid.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.horizontalHeader().customContextMenuRequested.connect(self.on_header_context_menu)
        layout.addWidget(self.grid)
        self.update_strategy_widgets()

    def create_toolbar_row(self, label_text):
        frame = QFrame()
        frame.setObjectName("Panel")
        frame.setStyleSheet("border-bottom: 1px solid #363a45;")
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(10, 2, 10, 2)
        lay.addWidget(QLabel(label_text))
        return frame

    def leaveEvent(self, event): self.tooltip.hide(); super().leaveEvent(event)
    def focusOutEvent(self, event): self.tooltip.hide(); super().focusOutEvent(event)
    def on_data_updated(self, df): self.all_runs_df = df

    # --- ENTRY POINT 1: FAMILY VIEW ---
    def on_scenario_selected(self, scenario_name):
        if self.all_runs_df is None: return
        self.base_name = scenario_name
        self.is_playlist_mode = False
        self.is_loading_state = True
        
        self.row1.setVisible(True)
        self.row2.setVisible(False)
        
        family_df = parsers.get_scenario_family_info(self.all_runs_df, scenario_name)
        if family_df is None or family_df.empty:
            family_df = self.all_runs_df[self.all_runs_df['Scenario'] == scenario_name].copy()
            family_df['Modifiers'] = [{}] * len(family_df)
        self.current_family_df = family_df

        self._setup_axes_for_family(family_df)
        self.load_view_settings()
        self.is_loading_state = False
        self.refresh_grid_view()

    def _setup_axes_for_family(self, family_df):
        axes = set()
        for mods in family_df['Modifiers']:
            if isinstance(mods, dict): axes.update(mods.keys())
        available_axes = sorted(list(axes))
        if not available_axes: available_axes = ["Default"]
        
        for btn in self.axis_group.buttons():
            self.axis_group.removeButton(btn)
            btn.deleteLater()
        
        for axis in available_axes:
            btn = QRadioButton(axis)
            self.axis_container.addWidget(btn)
            self.axis_group.addButton(btn)
        
        if self.axis_group.buttons():
            self.axis_group.buttons()[0].setChecked(True)
            self.current_axis = self.axis_group.buttons()[0].text()
            self.rebuild_format_options()

    # --- ENTRY POINT 2: PLAYLIST VIEW ---
    def load_playlist(self, name, scenarios):
        if self.all_runs_df is None: return
        self.base_name = name
        self.playlist_scenarios = scenarios
        self.is_playlist_mode = True
        self.is_loading_state = True
        
        self.row1.setVisible(False)
        self.row2.setVisible(False)
        
        self.load_view_settings()
        self.is_loading_state = False
        self.refresh_grid_view()

    # ... (event handlers) ...
    def on_axis_changed(self, btn):
        if not btn: return
        old_disabled = []
        for pat, chk in self.format_checkboxes.items():
            if not chk.isChecked(): old_disabled.append(pat)
        self.axis_filter_cache[self.current_axis] = old_disabled
        self.current_axis = btn.text()
        self.rebuild_format_options()
        if not self.is_loading_state: self.save_view_settings()
        self.refresh_grid_view()

    def rebuild_format_options(self):
        patterns = set()
        if not self.is_playlist_mode and self.current_family_df is not None:
            for mods in self.current_family_df['Modifiers']:
                if isinstance(mods, dict) and self.current_axis in mods:
                    patterns.add(mods[self.current_axis][1])
        
        while self.format_container.count():
            item = self.format_container.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.format_checkboxes = {}
        
        if len(patterns) > 1:
            self.row2.setVisible(True)
            disabled_list = self.axis_filter_cache.get(self.current_axis, [])
            for pat in patterns:
                label = f"{self.current_axis} #" if pat == 'word_value' else (f"# {self.current_axis}" if pat == 'value_word' else "Standalone")
                chk = QCheckBox(label)
                if pat in disabled_list: chk.setChecked(False)
                else: chk.setChecked(True)
                chk.stateChanged.connect(self.on_control_changed)
                self.format_container.addWidget(chk)
                self.format_checkboxes[pat] = chk
        else:
            self.row2.setVisible(False)

    def on_mode_changed(self, btn):
        self.active_agg = self.agg_strategies[btn.text()]
        self.update_strategy_widgets()
        self.on_control_changed()

    def on_highlight_changed(self, btn):
        self.active_hl = self.hl_strategies[btn.text()]
        self.update_strategy_widgets()
        self.on_control_changed()

    def on_control_changed(self):
        if not self.is_loading_state: self.save_view_settings()
        self.refresh_grid_view()

    def update_strategy_widgets(self):
        for layout in [self.agg_setting_container, self.hl_setting_container]:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()
        
        self.agg_setting_widget = self.active_agg.get_setting_widget()
        if self.agg_setting_widget:
            if hasattr(self.agg_setting_widget, 'valueChanged'):
                self.agg_setting_widget.valueChanged.connect(self.on_control_changed)
            self.agg_setting_container.addWidget(self.agg_setting_widget)

        self.hl_setting_widget = self.active_hl.get_setting_widget()
        if self.hl_setting_widget:
            widget_to_bind = self.hl_setting_widget
            if hasattr(widget_to_bind, 'spin'): widget_to_bind = widget_to_bind.spin
            if hasattr(widget_to_bind, 'valueChanged'):
                widget_to_bind.valueChanged.connect(self.on_control_changed)
            self.hl_setting_container.addWidget(self.hl_setting_widget)

    def load_view_settings(self):
        settings = self.config_manager.get("grid_view", scenario=self.base_name, default={})
        self.hidden_scenarios = set(settings.get("hidden_scenarios", []))
        self.hidden_cms = set(settings.get("hidden_cms", []))
        self.axis_filter_cache = settings.get("axis_filters", {})

        if not settings: return

        if not self.is_playlist_mode and "axis" in settings:
            for btn in self.axis_group.buttons():
                if btn.text() == settings["axis"]: 
                    btn.setChecked(True)
                    self.current_axis = btn.text()
                    self.rebuild_format_options() 
                    break
        
        saved_patterns = settings.get("disabled_patterns", [])
        for pat, chk in self.format_checkboxes.items():
            if pat in saved_patterns: chk.setChecked(False)

        if "sens_step" in settings: self.sens_combo.setCurrentText(settings["sens_step"])

        if "mode" in settings:
            for btn in self.mode_group.buttons():
                if btn.text() == settings["mode"]: 
                    btn.setChecked(True); self.active_agg = self.agg_strategies[settings["mode"]]; break
        
        if "highlight" in settings:
            for btn in self.hl_group.buttons():
                if btn.text() == settings["highlight"]: 
                    btn.setChecked(True); self.active_hl = self.hl_strategies[settings["highlight"]]; break
        
        self.update_strategy_widgets()
        
        if "agg_val" in settings and self.agg_setting_widget:
            self.active_agg.set_setting_value(self.agg_setting_widget, settings["agg_val"])
        if "hl_val" in settings and self.hl_setting_widget:
            self.active_hl.set_setting_value(self.hl_setting_widget, settings["hl_val"])

    def save_view_settings(self):
        if not self.base_name: return
        
        current_disabled = []
        for pat, chk in self.format_checkboxes.items():
            if not chk.isChecked(): current_disabled.append(pat)
        self.axis_filter_cache[self.current_axis] = current_disabled

        settings = {
            "axis": self.current_axis,
            "mode": self.active_agg.name,
            "highlight": self.active_hl.name,
            "sens_step": self.sens_combo.currentText(),
            "hidden_scenarios": list(self.hidden_scenarios),
            "hidden_cms": list(self.hidden_cms),
            "axis_filters": self.axis_filter_cache
        }
        if self.agg_setting_widget:
            settings["agg_val"] = self.active_agg.get_setting_value(self.agg_setting_widget)
        if self.hl_setting_widget:
            settings["hl_val"] = self.active_hl.get_setting_value(self.hl_setting_widget)
            
        self.config_manager.set_scenario(self.base_name, "grid_view", settings)

    def refresh_grid_view(self):
        df_to_process = pd.DataFrame()
        
        if self.is_playlist_mode:
            mask = self.all_runs_df['Scenario'].isin(self.playlist_scenarios)
            df_to_process = self.all_runs_df[mask].copy()
            if self.hidden_scenarios:
                df_to_process = df_to_process[~df_to_process['Scenario'].isin(self.hidden_scenarios)]
            df_to_process['Modifiers'] = [{}] * len(df_to_process)
        else:
            if self.current_family_df is None: return
            records = self.current_family_df.to_dict('records')
            active_formats = {pat: chk.isChecked() for pat, chk in self.format_checkboxes.items()}
            filtered_rows = []
            
            for row in records:
                scen = row['Scenario']
                if scen in self.hidden_scenarios: continue
                if scen == self.base_name:
                    filtered_rows.append(row)
                    continue
                
                mods = row['Modifiers']
                if isinstance(mods, dict) and self.current_axis in mods:
                    mod_keys = list(mods.keys())
                    remaining = [k for k in mod_keys if k != self.current_axis]
                    if len(remaining) == 0:
                        val, pat = mods[self.current_axis]
                        if pat in active_formats:
                            if active_formats[pat]: filtered_rows.append(row)
                        else: filtered_rows.append(row)
            
            if filtered_rows: df_to_process = pd.DataFrame(filtered_rows)

        if df_to_process.empty: self.grid.clear(); return

        if self.current_axis == "Sens" or self.is_playlist_mode: 
            df_to_process['ActiveAxis'] = df_to_process['Sens']
        else:
            df_to_process['ActiveAxis'] = df_to_process['Modifiers'].apply(
                lambda m: m[self.current_axis][0] if self.current_axis in m else np.nan)

        setting_val = None
        if self.agg_setting_widget:
            setting_val = self.active_agg.get_setting_value(self.agg_setting_widget)
        
        summary = self.active_agg.calculate(df_to_process, setting_val)
        pivot = summary.pivot_table(index='Scenario', columns='Sens', values='Score')

        sens_filter = self.sens_combo.currentText()
        step = 0
        if sens_filter != "All":
            try: step = float(sens_filter.replace("cm", ""))
            except: pass
            
        cols = []
        for c in pivot.columns:
            if str(c) in self.hidden_cms or f"{c}cm" in self.hidden_cms: continue
            if step > 0:
                if self._is_step_match(c, step): cols.append(c)
            else: cols.append(c)
                
        pivot = pivot[cols]
        pivot = self.sort_pivot_rows(pivot)

        self.recent_data_map = {}
        if self.active_hl.name == "Recent Success":
            days = 14
            if self.hl_setting_widget: days = self.active_hl.get_setting_value(self.hl_setting_widget)
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
            src = df_to_process if self.is_playlist_mode else self.current_family_df
            recent_df = src[src['Timestamp'] >= cutoff]
            if not recent_df.empty:
                self.recent_data_map = recent_df.groupby(['Scenario', 'Sens'])['Score'].max().to_dict()

        self.populate_table(pivot)

    def _is_step_match(self, col, step):
        try:
            val = float(col)
            return abs(val % step) < 0.05 or abs((val % step)-step) < 0.05
        except: return False

    def sort_pivot_rows(self, pivot_df):
        if self.is_playlist_mode:
            order_map = {name: i for i, name in enumerate(self.playlist_scenarios)}
            def sort_key(name): return order_map.get(name, 9999) 
            rows = list(pivot_df.index)
            rows.sort(key=sort_key)
            return pivot_df.reindex(rows)
        else:
            def key(name):
                if name == self.base_name: return 100.0
                mod = name.replace(self.base_name, "").strip()
                nums = re.findall(r"(\d+\.?\d*)", mod)
                return float(nums[-1]) if nums else 999.0
            rows = list(pivot_df.index)
            rows.sort(key=key)
            return pivot_df.reindex(rows)

    def populate_table(self, df):
        self.grid.clear()
        
        # 1. SETUP COLUMNS
        data_cols = sorted(df.columns, key=lambda x: float(x) if str(x).replace('.','').isdigit() else str(x))
        
        headers = ["Scenario / Sensitivity"] + [str(c) for c in data_cols] + ["AVG", "Best", "CM"]
        if not self.is_playlist_mode:
            headers.append("%")
            
        self.grid.setRowCount(len(df) + 1)
        self.grid.setColumnCount(len(headers))
        self.grid.setHorizontalHeaderLabels(headers)
        
        header = self.grid.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        if len(headers) > 1:
            for i in range(1, len(headers)): 
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        # --- NEW: Formatting Helper ---
        def fmt_score(val):
            # If 4 digits or more (>= 1000), drop decimal.
            # Otherwise (0-999), show 1 decimal place.
            if abs(val) >= 1000:
                return f"{val:.0f}"
            return f"{val:.1f}"
        # ------------------------------

        # 2. PRE-CALCULATE CONTEXT (Global)
        all_data_values = df.values.flatten()
        all_data_values = all_data_values[~np.isnan(all_data_values)]
        
        global_ctx = {
            'g_min': all_data_values.min() if len(all_data_values) > 0 else 0,
            'g_max': all_data_values.max() if len(all_data_values) > 0 else 1
        }
        
        base_pb_score = 1.0
        if not self.is_playlist_mode and self.base_name in df.index:
            base_pb_score = df.loc[self.base_name].max()

        # 3. PRE-CALCULATE ROWS & ACCUMULATE TOP ROW DATA
        processed_rows = []
        # We store LISTS of values for the top row
        top_row_acc = {c: [] for c in data_cols}
        top_row_acc['AVG'] = []
        top_row_acc['Best'] = []
        # CM and % don't need color accumulation usually, but let's keep structure
        top_row_acc['CM'] = [] 
        top_row_acc['%'] = []

        for sc, row in df.iterrows():
            vals = row.dropna().values
            if len(vals) == 0:
                processed_rows.append({'name': sc, 'empty': True})
                continue

            row_min = vals.min()
            row_max = vals.max()
            row_avg = vals.mean()
            
            row_cm = np.nan
            try:
                best_sens_col = row.idxmax()
                row_cm = float(best_sens_col) 
            except: pass

            row_pct = 0
            if base_pb_score > 0:
                row_pct = (row_max / base_pb_score) * 100

            p_row = {
                'name': sc,
                'empty': False,
                'vals': row,
                'stats': {'AVG': row_avg, 'Best': row_max, 'CM': row_cm, '%': row_pct},
                'ctx': {
                    'r_min': row_min, 'r_max': row_max,
                    'g_min': global_ctx['g_min'], 'g_max': global_ctx['g_max']
                }
            }
            processed_rows.append(p_row)

            # Accumulate
            for c in data_cols:
                v = row.get(c, np.nan)
                if pd.notna(v): top_row_acc[c].append(v)
            
            top_row_acc['AVG'].append(row_avg)
            top_row_acc['Best'].append(row_max)
            if not np.isnan(row_cm): top_row_acc['CM'].append(row_cm)
            top_row_acc['%'].append(row_pct)

        # 4. CALCULATE TOP ROW CONTEXT (The Fix)
        # We need to know the Min/Max of the AVERAGES to color the top row properly relative to itself.
        top_row_means = []
        
        # Calculate means for Data Columns
        for c in data_cols:
            if top_row_acc[c]: top_row_means.append(np.mean(top_row_acc[c]))
            
        # Calculate means for Aggregates (AVG, Best)
        # Note: Best in top row = Mean of Bests. 
        if top_row_acc['AVG']: top_row_means.append(np.mean(top_row_acc['AVG']))
        if top_row_acc['Best']: top_row_means.append(np.mean(top_row_acc['Best']))
        
        # Create the specific context for the Top Row
        top_ctx = global_ctx.copy()
        if top_row_means:
            top_ctx['r_min'] = min(top_row_means)
            top_ctx['r_max'] = max(top_row_means)
        else:
            top_ctx['r_min'] = 0
            top_ctx['r_max'] = 1

        # 5. RENDER TOP ROW
        self.grid.setItem(0, 0, QTableWidgetItem("-- Column Averages --"))
        
        def render_top_cell(col_idx, values, is_highlighted=True):
            if not values:
                self.grid.setItem(0, col_idx, QTableWidgetItem("-"))
                return
            
            mean_val = np.mean(values)
            
            txt = fmt_score(mean_val)
            
            if headers[col_idx] == "CM": txt = f"{mean_val:.1f}cm" # CM always keeps precision
            if headers[col_idx] == "%": txt = f"{mean_val:.0f}%"   # % usually fine as integer
            
            it = QTableWidgetItem(txt)
            it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            if is_highlighted:
                # ... (Highlight logic same) ...
                col = self.active_hl.get_color(mean_val, top_ctx, None)
                if col: it.setBackground(col)
                else: it.setBackground(QColor(40,44,52))
            
            self.grid.setItem(0, col_idx, it)


        # Render Data Cols
        for i, c in enumerate(data_cols):
            render_top_cell(i + 1, top_row_acc[c], is_highlighted=True)
            
        # Render Aggregates
        base_idx = len(data_cols) + 1
        render_top_cell(base_idx, top_row_acc['AVG'], is_highlighted=True)
        render_top_cell(base_idx + 1, top_row_acc['Best'], is_highlighted=True)
        render_top_cell(base_idx + 2, top_row_acc['CM'], is_highlighted=False)
        if not self.is_playlist_mode:
            render_top_cell(base_idx + 3, top_row_acc['%'], is_highlighted=False)

        # 6. RENDER DATA ROWS (Standard)
        hl_setting = None
        if self.hl_setting_widget:
            hl_setting = self.active_hl.get_setting_value(self.hl_setting_widget)

        for i, p_row in enumerate(processed_rows):
            row_idx = i + 1
            self.grid.setItem(row_idx, 0, QTableWidgetItem(str(p_row['name'])))
            
            if p_row['empty']:
                for c_i in range(1, self.grid.columnCount()):
                    self.grid.setItem(row_idx, c_i, QTableWidgetItem("-"))
                continue

            for c_i, c in enumerate(data_cols):
                val = p_row['vals'].get(c, np.nan)
                if pd.notna(val):
                    it = QTableWidgetItem(fmt_score(val))
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    
                    ctx = p_row['ctx'].copy()
                    if row_idx > 1:
                        prev_item = self.grid.item(row_idx-1, c_i+1)
                        if prev_item and prev_item.text() != "-" and prev_item.text():
                            try: ctx['prev_val'] = float(prev_item.text())
                            except: ctx['prev_val'] = None
                    
                    if hasattr(self, 'recent_data_map'):
                        ctx['recent_max'] = self.recent_data_map.get((p_row['name'], c))

                    col = self.active_hl.get_color(val, ctx, hl_setting)
                    if col: it.setBackground(col)
                    self.grid.setItem(row_idx, c_i+1, it)
                else:
                    self.grid.setItem(row_idx, c_i+1, QTableWidgetItem("-"))

            # Row Aggregates
            it_avg = QTableWidgetItem(fmt_score(p_row['stats']['AVG']))
            it_avg.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            col_avg = self.active_hl.get_color(p_row['stats']['AVG'], p_row['ctx'], hl_setting)
            if col_avg: it_avg.setBackground(col_avg)
            self.grid.setItem(row_idx, base_idx, it_avg)

            it_best = QTableWidgetItem(fmt_score(p_row['stats']['Best']))
            it_best.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            col_best = self.active_hl.get_color(p_row['stats']['Best'], p_row['ctx'], hl_setting)
            if col_best: it_best.setBackground(col_best)
            self.grid.setItem(row_idx, base_idx + 1, it_best)

            cm_val = p_row['stats']['CM']
            cm_str = f"{cm_val}cm" if not np.isnan(cm_val) else "-"
            it_cm = QTableWidgetItem(cm_str)
            it_cm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid.setItem(row_idx, base_idx + 2, it_cm)

            if not self.is_playlist_mode:
                pct_val = p_row['stats']['%']
                it_pct = QTableWidgetItem(f"{pct_val:.0f}%")
                it_pct.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.grid.setItem(row_idx, base_idx + 3, it_pct)

    def on_table_context_menu(self, pos):
        item = self.grid.itemAt(pos)
        if not item: return
        if item.column() != 0: return 
        menu = QMenu(self)
        hide_action = QAction(f"Hide Scenario: {item.text()}", self)
        hide_action.triggered.connect(lambda: self.hide_scenario(item.text()))
        menu.addAction(hide_action)
        menu.exec(self.grid.viewport().mapToGlobal(pos))

    def on_header_context_menu(self, pos):
        idx = self.grid.horizontalHeader().logicalIndexAt(pos)
        if idx <= 0: return 
        header_text = self.grid.horizontalHeaderItem(idx).text()
        if header_text in ["AVG", "Best", "%", "cm"]: return
        menu = QMenu(self)
        hide_action = QAction(f"Hide {header_text}", self)
        hide_action.triggered.connect(lambda: self.hide_cm(header_text))
        menu.addAction(hide_action)
        menu.exec(self.grid.horizontalHeader().mapToGlobal(pos))

    def hide_scenario(self, name):
        self.hidden_scenarios.add(name)
        self.save_view_settings()
        self.refresh_grid_view()

    def hide_cm(self, cm_text):
        self.hidden_cms.add(cm_text)
        self.save_view_settings()
        self.refresh_grid_view()

    def open_manage_hidden(self):
        dlg = ManageHiddenDialog(list(self.hidden_scenarios), list(self.hidden_cms), self)
        if dlg.exec():
            self.hidden_scenarios = set(dlg.hidden_scens)
            self.hidden_cms = set(dlg.hidden_cms)
            self.save_view_settings()
            self.refresh_grid_view()

    def on_cell_clicked(self, r, c):
        # NEW: Ignore the top row (index 0) explicitly
        if r == 0: return

        item_scen = self.grid.item(r, 0)
        if not item_scen: return
        
        scenario_name = item_scen.text()

        sens_val = None
        
        if c > 0:
            header_text = self.grid.horizontalHeaderItem(c).text()
            if header_text not in ["AVG", "Best", "%"]:
                try:
                    clean_text = header_text.replace("cm", "").strip()
                    sens_val = float(clean_text)
                except: sens_val = None 
        
        self.state_manager.variant_selected.emit({
            'scenario': scenario_name,
            'sens': sens_val
        })

    def on_cell_entered(self, row, col):
        if row <= 0 or col < 0: self.tooltip.hide(); return
        item_scen = self.grid.item(row, 0)
        if not item_scen: self.tooltip.hide(); return
        scenario_name = item_scen.text()
        if scenario_name == "-- Average --": self.tooltip.hide(); return
        
        sens_val = None
        sens_str = self.grid.horizontalHeaderItem(col).text().replace("cm", "")
        if col > 0:
            try: sens_val = float(sens_str)
            except: pass
            
        src_df = self.all_runs_df if self.is_playlist_mode else self.current_family_df
        if src_df is None: return
        
        df = src_df[src_df['Scenario'] == scenario_name]
        if sens_val is not None:
            df = df[df['Sens'] == sens_val]
            sub_title = f"Sensitivity: {sens_val}cm"
        else:
            if col == 0: sub_title = "Sensitivity: All"
            else: self.tooltip.hide(); return
            
        if df.empty: self.tooltip.hide(); return
        
        from core.analytics import stats
        stats_data = stats.calculate_detailed_stats(df)
        scores = df.sort_values('Timestamp')['Score'].tolist()
        
        self.tooltip.update_data(scenario_name, sub_title, stats_data, scores)
        
        cursor_pos = QCursor.pos()
        self.tooltip.move(cursor_pos.x() + 20, cursor_pos.y() + 20)
        self.tooltip.show()
        self.tooltip.raise_()