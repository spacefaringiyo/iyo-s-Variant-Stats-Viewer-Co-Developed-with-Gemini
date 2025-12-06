from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QPushButton, 
                             QStackedWidget, QLabel, QFrame)
from PyQt6.QtCore import Qt
from modules.navigation.sidebar import NavigationWidget
from modules.navigation.playlist_sidebar import PlaylistNavigationWidget

class BrowserTabs(QWidget):
    def __init__(self, state_manager, config_manager):
        super().__init__()
        self.state_manager = state_manager
        
        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        
        self.menu_container = QFrame()
        self.menu_container.setStyleSheet("""
            QFrame { background: #1e222d; border-bottom: 1px solid #363a45; }
            QPushButton {
                background: transparent;
                border: none;
                color: #787b86;
                font-weight: bold;
                padding: 10px;
                text-align: center;
                border-radius: 4px;
            }
            QPushButton:hover { background: #2a2e39; color: #d1d4dc; }
            QPushButton:checked { 
                background: #131722; 
                color: #2962FF; 
                border-bottom: 2px solid #2962FF;
                border-radius: 0px;
            }
        """)
        self.menu_layout = QGridLayout(self.menu_container)
        self.menu_layout.setContentsMargins(5,5,5,5)
        self.menu_layout.setSpacing(5)
        
        self.btn_scenarios = self.create_nav_btn("Scenarios", 0)
        self.btn_playlists = self.create_nav_btn("Playlists", 1)
        self.btn_benchmarks = self.create_nav_btn("Benchmarks", 2)
        
        self.btn_stats = QPushButton("Stats")
        self.btn_stats.setEnabled(False) 
        self.btn_stats.setStyleSheet("color: #363a45;")
        
        self.menu_layout.addWidget(self.btn_scenarios, 0, 0)
        self.menu_layout.addWidget(self.btn_playlists, 0, 1)
        self.menu_layout.addWidget(self.btn_benchmarks, 1, 0)
        self.menu_layout.addWidget(self.btn_stats, 1, 1)
        
        layout.addWidget(self.menu_container)

        # 2. Content Stack
        self.stack = QStackedWidget()
        
        # Page 0: Scenarios
        self.page_scenarios = NavigationWidget(state_manager, config_manager)
        self.stack.addWidget(self.page_scenarios)
        
        # Page 1: Playlists (UPDATED)
        self.page_playlists = PlaylistNavigationWidget(state_manager, config_manager)
        self.stack.addWidget(self.page_playlists)
        
        # Page 2: Benchmarks
        self.page_benchmarks = QWidget()
        bm_layout = QVBoxLayout(self.page_benchmarks)
        bm_layout.addWidget(QLabel("Benchmarks Module\n(Coming Soon)"))
        self.stack.addWidget(self.page_benchmarks)
        
        layout.addWidget(self.stack)
        
        self.btn_scenarios.setChecked(True)
        self.stack.setCurrentIndex(0)

    def create_nav_btn(self, text, index):
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self.switch_tab(index))
        return btn

    def switch_tab(self, index):
        self.stack.setCurrentIndex(index)
        self.btn_scenarios.setChecked(index == 0)
        self.btn_playlists.setChecked(index == 1)
        self.btn_benchmarks.setChecked(index == 2)