from PyQt6.QtWidgets import (QTabWidget, QTabBar, QMenu, QWidget, QVBoxLayout, 
                             QPushButton, QToolButton)
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QAction, QCursor
from modules.dashboard.grid_widget import GridWidget

class GridContainer(QTabWidget):
    def __init__(self, state_manager, config_manager):
        super().__init__()
        self.state_manager = state_manager
        self.config_manager = config_manager
        self.all_runs_df = None
        self.tabs_to_restore = [] 
        self.suppress_signal = False

        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        
        self.tabCloseRequested.connect(self.close_tab_request)
        self.currentChanged.connect(self.on_tab_changed, Qt.ConnectionType.QueuedConnection)
        
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        self.btn_clear = QToolButton()
        self.btn_clear.setText("Clear Unpinned")
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.clicked.connect(self.close_all_unpinned)
        self.btn_clear.setStyleSheet("border: none; color: #787b86; font-weight: bold; padding: 2px 8px;")
        self.setCornerWidget(self.btn_clear, Qt.Corner.TopRightCorner)

        self.state_manager.data_updated.connect(self.on_data_updated)
        self.state_manager.scenario_selected.connect(self.open_scenario_tab)
        self.state_manager.variant_selected.connect(self.on_variant_selected)
        
        # --- CONNECT NEW SIGNAL ---
        self.state_manager.playlist_selected.connect(self.open_playlist_tab)
        # --------------------------

        self.setStyleSheet("""
            QTabBar::tab { background: #1e222d; color: #787b86; padding: 8px 15px; border-right: 1px solid #363a45; border-top: 2px solid transparent; min-width: 120px; }
            QTabBar::tab:selected { background: #131722; color: #d1d4dc; border-top: 2px solid #2962FF; }
            QTabBar::tab:hover { background: #2a2e39; }
            QTabWidget::pane { border: none; background: #131722; }
        """)

    def on_variant_selected(self, payload):
        scenario_name = payload.get('scenario')
        if not scenario_name: return
        
        current_idx = self.currentIndex()
        if current_idx != -1:
            current_widget = self.widget(current_idx)
            # If current tab handles this scenario (whether Family or Playlist containing it),
            # we might want to stay. For now, strict check on Base Name.
            if hasattr(current_widget, 'base_name'):
                base = current_widget.base_name
                # If Family Mode: check startswith
                if not current_widget.is_playlist_mode and scenario_name.startswith(base):
                    return
                # If Playlist Mode: check if in scenarios list
                if current_widget.is_playlist_mode and scenario_name in current_widget.playlist_scenarios:
                    return

        self.suppress_signal = True 
        self.open_scenario_tab(scenario_name)
        self.suppress_signal = False

    def on_data_updated(self, df):
        self.all_runs_df = df
        for i in range(self.count()):
            widget = self.widget(i)
            if isinstance(widget, GridWidget): widget.on_data_updated(df)

    def on_tab_changed(self, index):
        if index == -1: return
        if getattr(self, 'suppress_signal', False): return

        widget = self.widget(index)
        if isinstance(widget, GridWidget):
            # If Playlist, we might emit something else, or nothing.
            # Currently Sidebar listens for "scenario_selected" to highlight.
            # Playlists don't need reverse highlighting in sidebar yet.
            if not widget.is_playlist_mode:
                tab_text = self.tabText(index).replace("★ ", "")
                self.state_manager.scenario_selected.emit(tab_text)

    # --- NEW: OPEN PLAYLIST TAB ---
    def open_playlist_tab(self, payload):
        name = payload['name']
        scenarios = payload['scenarios']
        
        # Check duplicates
        for i in range(self.count()):
            clean_name = self.tabText(i).replace("★ ", "")
            if clean_name == name:
                self.setCurrentIndex(i)
                return
        
        # Create
        new_grid = GridWidget(self.state_manager, self.config_manager)
        if self.all_runs_df is not None:
            new_grid.on_data_updated(self.all_runs_df)
            
        new_grid.load_playlist(name, scenarios)
        
        self.blockSignals(True)
        index = self.addTab(new_grid, name)
        self.setCurrentIndex(index)
        self.blockSignals(False)
    # ------------------------------

    def open_scenario_tab(self, scenario_name):
        for i in range(self.count()):
            clean_name = self.tabText(i).replace("★ ", "")
            if clean_name == scenario_name:
                if self.currentIndex() != i: self.setCurrentIndex(i)
                return
        
        self._create_and_add_tab({"name": scenario_name, "pinned": False, "active": True})

    def close_tab_request(self, index):
        if self.is_pinned(index): return 
        widget = self.widget(index); self.removeTab(index); widget.deleteLater()

    def close_all_unpinned(self):
        for i in range(self.count() - 1, -1, -1):
            if not self.is_pinned(i): self.close_tab_request(i)

    def is_pinned(self, index): return self.tabBar().tabData(index) is True

    def toggle_pin(self, index):
        new_state = not self.is_pinned(index)
        self.tabBar().setTabData(index, new_state)
        text = self.tabText(index)
        if new_state: self.setTabText(index, "★ " + text); self.tabBar().setTabButton(index, QTabBar.ButtonPosition.RightSide, None)
        else: self.setTabText(index, text.replace("★ ", ""))

    def show_context_menu(self, pos):
        tab_bar = self.tabBar();
        if not tab_bar.geometry().contains(pos): return
        local_pos = tab_bar.mapFrom(self, pos); index = tab_bar.tabAt(local_pos)
        if index == -1: return
        menu = QMenu(self)
        pinned = self.is_pinned(index)
        menu.addAction("Unpin Tab" if pinned else "Pin Tab").triggered.connect(lambda: self.toggle_pin(index))
        menu.addSeparator()
        action_close = menu.addAction("Close"); action_close.setEnabled(not pinned); action_close.triggered.connect(lambda: self.close_tab_request(index))
        menu.addAction("Close Other Tabs").triggered.connect(lambda: self.close_others(index))
        menu.addAction("Close All Unpinned").triggered.connect(self.close_all_unpinned)
        menu.exec(QCursor.pos())

    def close_others(self, keep_index):
        for i in range(self.count() - 1, -1, -1):
            if i != keep_index and not self.is_pinned(i): self.close_tab_request(i)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            tab_bar = self.tabBar(); local_pos = tab_bar.mapFrom(self, event.pos()); index = tab_bar.tabAt(local_pos)
            if index != -1: self.close_tab_request(index); return
        super().mousePressEvent(event)

    def save_state(self):
        tabs = []
        for i in range(self.count()):
            widget = self.widget(i)
            # Store Type so we can restore correctly
            is_pl = getattr(widget, 'is_playlist_mode', False)
            pl_scens = getattr(widget, 'playlist_scenarios', [])
            
            tabs.append({
                "name": self.tabText(i).replace("★ ", ""), 
                "pinned": self.is_pinned(i), 
                "active": (i == self.currentIndex()),
                "is_playlist": is_pl,
                "scenarios": pl_scens
            })
        self.config_manager.set_global("open_tabs", tabs)

    def restore_state(self):
        tabs = self.config_manager.get("open_tabs", default=[])
        if not tabs: return
        self.tabs_to_restore = tabs
        QTimer.singleShot(0, self._restore_next_tab)

    def _restore_next_tab(self):
        if not self.tabs_to_restore: return 
        tab_data = self.tabs_to_restore.pop(0) 
        
        current_names = {self.tabText(i).replace("★ ", "") for i in range(self.count())}
        if tab_data['name'] in current_names:
            QTimer.singleShot(0, self._restore_next_tab)
            return

        # Restore based on Type
        if tab_data.get('is_playlist', False):
            # Manually trigger playlist logic
            new_grid = GridWidget(self.state_manager, self.config_manager)
            if self.all_runs_df is not None: new_grid.on_data_updated(self.all_runs_df)
            new_grid.load_playlist(tab_data['name'], tab_data.get('scenarios', []))
            
            self.blockSignals(True)
            index = self.addTab(new_grid, tab_data['name'])
            if tab_data.get('pinned', False): self.toggle_pin(index)
            if tab_data.get('active', False): self.setCurrentIndex(index)
            self.blockSignals(False)
        else:
            # Standard Scenario Tab
            self._create_and_add_tab(tab_data)
        
        QTimer.singleShot(50, self._restore_next_tab) 

    def _create_and_add_tab(self, tab_data):
        new_grid = GridWidget(self.state_manager, self.config_manager)
        if self.all_runs_df is not None:
            new_grid.on_data_updated(self.all_runs_df)
            
        new_grid.on_scenario_selected(tab_data['name'])
        
        self.blockSignals(True)
        index = self.addTab(new_grid, tab_data['name'])
        if tab_data.get('pinned', False): self.toggle_pin(index)
        if tab_data.get('active', False): self.setCurrentIndex(index)
        self.blockSignals(False)
        
        if tab_data.get('active', False):
             self.on_tab_changed(index)