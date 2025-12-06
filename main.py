import sys
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QDockWidget, QLabel, QSplitter, 
                             QMenu, QPushButton, QHBoxLayout, QVBoxLayout, QWidget, 
                             QFileDialog, QDialog, QFormLayout, QSpinBox, QMessageBox,
                             QComboBox, QCheckBox, QGroupBox, QGridLayout, QDoubleSpinBox,
                             QSizePolicy, QProgressBar)
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QByteArray, QFileSystemWatcher, QTimer
from pathlib import Path

import styles
from core.state_manager import StateManager
from core.config_manager import ConfigManager
from core.analytics import processors
from core.analytics.processors import CACHE_HISTORY_PATH

# Modules
from modules.navigation.browser_tabs import BrowserTabs
from modules.dashboard.grid_container import GridContainer
from modules.charts.chart_widget import ChartWidget
from modules.right_panel.analyst_tabs import AnalystTabs

from core.locales import APP_VERSION, get_text

# --- SETTINGS DIALOG ---
class SettingsDialog(QDialog):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.parent_window = parent
        self.setWindowTitle("Preferences")
        self.resize(400, 480)
        self.setStyleSheet(styles.QSS)
        
        layout = QVBoxLayout(self)
        
        # 1. GENERAL SETTINGS
        grp_gen = QGroupBox("General")
        form_gen = QFormLayout(grp_gen)
        
        self.sb_gap = QSpinBox()
        self.sb_gap.setRange(1, 1440)
        self.sb_gap.setValue(self.config_manager.get("session_gap", default=30))
        self.sb_gap.setSuffix(" min")
        form_gen.addRow("Session Gap:", self.sb_gap)

         # --- Playlist Path Selector ---
        self.btn_playlist_path = QPushButton("Select Folder...")
        self.lbl_playlist_path = QLabel(self.config_manager.get("playlist_path", default="Not Set"))
        self.lbl_playlist_path.setStyleSheet("color: #787b86; font-style: italic;")
        
        self.btn_playlist_path.clicked.connect(self.select_playlist_folder)
        
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.lbl_playlist_path)
        path_layout.addWidget(self.btn_playlist_path)
        form_gen.addRow("Playlist Path:", path_layout)
        
        self.cb_startup = QComboBox()
        self.cb_startup.addItems(["Last", "Calendar", "Ongoing", "Session Report", "Career Profile"])
        current = self.config_manager.get("startup_tab_mode", default="Last")
        self.cb_startup.setCurrentText(current)
        form_gen.addRow("Startup Tab:", self.cb_startup)

         # Calendar Compare Mode
        self.cb_cal_mode = QComboBox()
        self.cb_cal_mode.addItems(["Average", "Best"])
        curr_cal = self.config_manager.get("calendar_compare_mode", default="Average")
        self.cb_cal_mode.setCurrentText(curr_cal)
        self.cb_cal_mode.setToolTip("Determines if 'vs Avg' comparisons in Calendar use today's Average or Best score.")
        form_gen.addRow("Calendar vs Mode:", self.cb_cal_mode)
        
        self.chk_dev = QCheckBox("Enable Dev Mode (Show Refresh Time)")
        self.chk_dev.setChecked(self.config_manager.get("dev_mode", default=False))
        form_gen.addRow("Dev Mode:", self.chk_dev)
        
        layout.addWidget(grp_gen)
        
        # 2. DATA FILTERS
        grp_filter = QGroupBox("Data Filters (% vs Average)")
        grid_filter = QGridLayout(grp_filter)
        
        def make_range_row(row_idx, label_text, key_min, key_max):
            lbl = QLabel(label_text)
            sb_min = QDoubleSpinBox(); sb_min.setRange(-9999, 9999); sb_min.setSuffix("%")
            sb_max = QDoubleSpinBox(); sb_max.setRange(-9999, 9999); sb_max.setSuffix("%")
            sb_min.setValue(self.config_manager.get(key_min, default=-1000.0))
            sb_max.setValue(self.config_manager.get(key_max, default=1000.0))
            grid_filter.addWidget(lbl, row_idx, 0)
            grid_filter.addWidget(QLabel("Min:"), row_idx, 1); grid_filter.addWidget(sb_min, row_idx, 2)
            grid_filter.addWidget(QLabel("Max:"), row_idx, 3); grid_filter.addWidget(sb_max, row_idx, 4)
            return sb_min, sb_max

        self.sb_ong_min, self.sb_ong_max = make_range_row(0, "Ongoing Tab:", "ongoing_min_pct", "ongoing_max_pct")
        self.sb_sess_min, self.sb_sess_max = make_range_row(1, "Session Rep:", "session_min_pct", "session_max_pct")
        layout.addWidget(grp_filter)

        # 3. MAINTENANCE
        grp_maint = QGroupBox("Maintenance")
        vbox_maint = QVBoxLayout(grp_maint)
        btn_rebuild = QPushButton("Rebuild Database (Fix Errors)")
        btn_rebuild.setStyleSheet("background: #8B0000; color: white; font-weight: bold;")
        btn_rebuild.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_rebuild.clicked.connect(self.on_rebuild_clicked)
        vbox_maint.addWidget(btn_rebuild)
        lbl_maint = QLabel("Use this if stats seem wrong. It will delete the cache and rescan your folder.")
        lbl_maint.setStyleSheet("color: #787b86; font-size: 11px;")
        lbl_maint.setWordWrap(True)
        vbox_maint.addWidget(lbl_maint)
        layout.addWidget(grp_maint)
        
        layout.addStretch()
        
        btn_box = QHBoxLayout()
        btn_save = QPushButton("Save & Reload"); btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel"); btn_cancel.clicked.connect(self.reject)
        btn_box.addStretch(); btn_box.addWidget(btn_cancel); btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

    def on_rebuild_clicked(self):
        if self.parent_window: self.parent_window.full_rebuild()
        self.reject()

    def select_playlist_folder(self):
        current = self.config_manager.get("playlist_path", "")
        start_dir = current if current and Path(current).exists() else str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Select Playlist Folder", start_dir)
        if folder:
            self.lbl_playlist_path.setText(folder)

    def get_values(self):
        # We need to grab the path from the label if it changed, 
        # or rely on config if user didn't touch it. 
        # Better approach: store a temporary variable in the class.
        # But simpler for now: The label text IS the new path if user selected one.
        
        pl_path = self.lbl_playlist_path.text()
        if pl_path == "Not Set": pl_path = ""

        return {
            "session_gap": self.sb_gap.value(),
            "playlist_path": pl_path,
            "startup_tab_mode": self.cb_startup.currentText(),
            "calendar_compare_mode": self.cb_cal_mode.currentText(),
            "ongoing_min_pct": self.sb_ong_min.value(),
            "ongoing_max_pct": self.sb_ong_max.value(),
            "session_min_pct": self.sb_sess_min.value(),
            "session_max_pct": self.sb_sess_max.value(),
            "dev_mode": self.chk_dev.isChecked()
        }
    

class DataLoader(QThread):
    finished = pyqtSignal(object)
    def __init__(self, path, session_gap): 
        super().__init__()
        self.path = path
        self.session_gap = session_gap
    def run(self):
        df = processors.find_and_process_stats(self.path, session_gap_minutes=self.session_gap)
        self.finished.emit(df)

class KovaaksV2App(QMainWindow):
    def __init__(self):
        super().__init__()

        title = get_text("en", "window_title", ver=APP_VERSION)
        self.setWindowTitle(title)
        self.resize(1800, 1000)
        self.setStyleSheet(styles.QSS)
        
        self.state_manager = StateManager()
        self.config_manager = ConfigManager()
        self.current_stats_path = None
        self.is_initial_load = True
        self.load_start_time = 0
        
        self.file_watcher = QFileSystemWatcher(self)
        self.file_watcher.directoryChanged.connect(self.on_dir_changed)
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(2000) 
        self.debounce_timer.timeout.connect(self.refresh_stats)
        
        self.state_manager.chart_title_changed.connect(self.update_header_title)

        self.setDockOptions(QMainWindow.DockOption.AllowNestedDocks | 
                            QMainWindow.DockOption.AnimatedDocks | 
                            QMainWindow.DockOption.AllowTabbedDocks)

        self.setup_layout() 
        self.setup_menu()   
        self.load_app_state() 
        
        self.shortcut_refresh = QShortcut(QKeySequence("F5"), self)
        self.shortcut_refresh.activated.connect(self.refresh_stats)
        
        self.auto_load()

    def setup_layout(self):
        self.central_container = QWidget()
        self.central_layout = QVBoxLayout(self.central_container)
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.central_layout.setSpacing(0)
        self.setCentralWidget(self.central_container)

        # 1. HEADER
        self.header_widget = QWidget()
        self.header_widget.setFixedHeight(50)
        self.header_widget.setStyleSheet("background-color: #131722; border-bottom: 1px solid #363a45;")
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(20, 0, 20, 0)
        
        self.header_label = QLabel("ANALYTICS")
        self.header_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #d1d4dc; margin-right: 20px;")
        header_layout.addWidget(self.header_label)
        header_layout.addStretch()
        
        self.chk_auto = QCheckBox("Auto-Refresh")
        self.chk_auto.setStyleSheet("color: #d1d4dc; font-weight: bold; margin-right: 15px;")
        auto_state = self.config_manager.get("auto_refresh", default=True)
        self.chk_auto.setChecked(auto_state)
        self.chk_auto.stateChanged.connect(self.on_auto_toggled)
        header_layout.addWidget(self.chk_auto)
        
        btn_load = QPushButton("Load Folder")
        btn_load.clicked.connect(self.select_folder)
        btn_load.setStyleSheet("QPushButton { background-color: #2a2e39; border: 1px solid #363a45; color: #d1d4dc; padding: 6px 12px; } QPushButton:hover { background-color: #363a45; }")
        header_layout.addWidget(btn_load)
        
        self.btn_refresh = QPushButton("Refresh (F5)")
        self.btn_refresh.clicked.connect(self.refresh_stats)
        self.btn_refresh.setStyleSheet("QPushButton { background-color: #2962FF; border: none; color: white; padding: 6px 12px; font-weight: bold;} QPushButton:hover { background-color: #1e53e5; } QPushButton:disabled { background-color: #363a45; color: #787b86; }")
        header_layout.addWidget(self.btn_refresh)
        
        self.central_layout.addWidget(self.header_widget)

        # 2. LOADING BAR (New)
        self.loader_bar = QProgressBar()
        self.loader_bar.setFixedHeight(2) # Ultra thin
        self.loader_bar.setTextVisible(False)
        
        # Background matches Window (#131722) so it's invisible when empty.
        # Chunk is the Accent Blue (#2962FF) for consistency.
        self.loader_bar.setStyleSheet("""
            QProgressBar { border: none; background-color: #131722; }
            QProgressBar::chunk { background-color: #2962FF; } 
        """)
        
        # Initialize as "Idle" (0% progress, visible but empty)
        self.loader_bar.setRange(0, 100)
        self.loader_bar.setValue(0)
        
        self.central_layout.addWidget(self.loader_bar)

        # 3. SPLITTER (Same as before)
        self.center_splitter = QSplitter(Qt.Orientation.Vertical)
        self.center_splitter.setObjectName("CenterSplitter")
        
        self.chart_widget = ChartWidget(self.state_manager)
        self.chart_widget.setMinimumHeight(0) 
        self.chart_widget.setMinimumWidth(0)
        self.chart_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        
        self.grid_container = GridContainer(self.state_manager, self.config_manager)
        self.grid_container.setMinimumHeight(0) 
        self.grid_container.setMinimumWidth(0)
        self.grid_container.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        
        self.center_splitter.addWidget(self.chart_widget)
        self.center_splitter.addWidget(self.grid_container)
        
        self.central_layout.addWidget(self.center_splitter)

        # DOCKS
        self.dock_nav = QDockWidget("Browser", self)
        self.dock_nav.setObjectName("DockNav")
        self.dock_nav.setMinimumWidth(0) # Allow browser to be narrow
        self.dock_nav.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        self.dock_nav.setWidget(BrowserTabs(self.state_manager, self.config_manager))
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_nav)

        self.dock_analyst = QDockWidget("Analyst", self)
        self.dock_analyst.setObjectName("DockAnalyst")
        self.dock_analyst.setMinimumWidth(0) # Allow analyst to be narrow
        self.dock_analyst.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)

        self.dock_analyst.setWidget(AnalystTabs(self.state_manager, self.config_manager))
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_analyst)

    def setup_menu(self):
        menu_bar = self.menuBar()
        settings_menu = menu_bar.addMenu("Settings")
        act_pref = QAction("Preferences...", self)
        act_pref.triggered.connect(self.open_preferences)
        settings_menu.addAction(act_pref)

        view_menu = menu_bar.addMenu("View")
        def add_dock_toggle(dock):
            action = dock.toggleViewAction()
            view_menu.addAction(action)
        add_dock_toggle(self.dock_nav)
        add_dock_toggle(self.dock_analyst)

    def update_header_title(self, text):
        self.header_label.setText(text)

    def open_preferences(self):
        dlg = SettingsDialog(self.config_manager, self)
        if dlg.exec():
            vals = dlg.get_values()
            self.config_manager.set_global("session_gap", vals["session_gap"])
            self.config_manager.set_global("playlist_path", vals["playlist_path"])
            self.config_manager.set_global("startup_tab_mode", vals["startup_tab_mode"])
            self.config_manager.set_global("calendar_compare_mode", vals["calendar_compare_mode"])
            self.config_manager.set_global("ongoing_min_pct", vals["ongoing_min_pct"])
            self.config_manager.set_global("ongoing_max_pct", vals["ongoing_max_pct"])
            self.config_manager.set_global("session_min_pct", vals["session_min_pct"])
            self.config_manager.set_global("session_max_pct", vals["session_max_pct"])
            self.config_manager.set_global("dev_mode", vals["dev_mode"])
            self.refresh_stats()

    def update_watcher(self, path):
        if self.file_watcher.directories():
            self.file_watcher.removePaths(self.file_watcher.directories())
        if path and self.chk_auto.isChecked():
            self.file_watcher.addPath(path)

    def on_auto_toggled(self, state):
        self.config_manager.set_global("auto_refresh", self.chk_auto.isChecked())
        if self.chk_auto.isChecked():
            self.update_watcher(self.current_stats_path)
        else:
            if self.file_watcher.directories():
                self.file_watcher.removePaths(self.file_watcher.directories())

    def on_dir_changed(self, path):
        self.debounce_timer.start()

    def auto_load(self):
        saved_path = self.config_manager.get("stats_path")
        if saved_path and Path(saved_path).exists():
            self.start_loading(saved_path)
            return

        # Expanded Path List (Windows + Linux + Steam Deck)
        home = Path.home()
        paths_to_check = [
            # Windows - Standard
            Path("C:/Program Files (x86)/Steam/steamapps/common/FPSAimTrainer/FPSAimTrainer/stats"),
            # Windows - Common Secondary Drive
            Path("D:/SteamLibrary/steamapps/common/FPSAimTrainer/FPSAimTrainer/stats"),
            
            # Linux - Native Steam (Debian/Arch/Fedora etc)
            home / ".steam/steam/steamapps/common/FPSAimTrainer/FPSAimTrainer/stats",
            home / ".local/share/Steam/steamapps/common/FPSAimTrainer/FPSAimTrainer/stats",
            
            # Linux - Flatpak (Steam Deck / Mint / PopOS)
            home / ".var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/FPSAimTrainer/FPSAimTrainer/stats",
            home / ".var/app/com.valvesoftware.Steam/.steam/steam/steamapps/common/FPSAimTrainer/FPSAimTrainer/stats",

            # Linux - Snap (Ubuntu)
            home / "snap/steam/common/.local/share/Steam/steamapps/common/FPSAimTrainer/FPSAimTrainer/stats",

            # Linux - Custom Mounts (Common for secondary drives)
            Path("/mnt/Games/SteamLibrary/steamapps/common/FPSAimTrainer/FPSAimTrainer/stats"),
        ]

        for p in paths_to_check:
            if p.exists():
                self.start_loading(str(p))
                break

    def select_folder(self):
        current = self.config_manager.get("stats_path")
        start_dir = current if current and Path(current).exists() else str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Select Stats Folder", start_dir)
        if folder:
            self.config_manager.set_global("stats_path", folder)
            self.start_loading(folder)

    def full_rebuild(self):
        from core.analytics.processors import APP_DATA_DIR
        try:
            for f in APP_DATA_DIR.glob("*"):
                if f.is_file(): f.unlink()
            print("Cache cleared.")
        except Exception as e:
            print(f"Error clearing cache: {e}")
        self.refresh_stats()

    def refresh_stats(self):
        if self.current_stats_path:
            self.start_loading(self.current_stats_path)

    def start_loading(self, path):
        self.current_stats_path = path
        self.update_watcher(path) 
        
        self.btn_refresh.setEnabled(False)
        self.load_start_time = time.time()
        
        # --- UI FEEDBACK ---
        self.loader_bar.setRange(0, 0) 
        
        if not CACHE_HISTORY_PATH.exists():
             self.btn_refresh.setText("Initializing...")
             self.header_label.setText("ANALYTICS - Building Cache (First Run)")
        else:
             self.btn_refresh.setText("Loading...")
        # -------------------
        
        gap = self.config_manager.get("session_gap", default=30)
        self.worker = DataLoader(path, gap) 
        self.worker.finished.connect(self.on_data_loaded)
        self.worker.start()

    def on_data_loaded(self, df):
        # 1. EMIT DATA
        self.state_manager.data_updated.emit(df)
        
        # 2. STOP ANIMATION (Reset to empty bar)
        self.loader_bar.setRange(0, 100)
        self.loader_bar.setValue(0)
        
        # 3. AUTO-LOAD LOGIC
        if self.is_initial_load:
            saved_tabs = self.config_manager.get("open_tabs", default=[])
            if saved_tabs:
                self.grid_container.restore_state()
            else:
                if df is not None and not df.empty:
                    try:
                        recent_row = df.sort_values('Timestamp').iloc[-1]
                        recent_scen = recent_row['Scenario']
                        self.state_manager.scenario_selected.emit(recent_scen)
                    except: pass
            
            self.is_initial_load = False 
            
        # 4. STOP TIMER
        duration = time.time() - self.load_start_time
        
        if self.config_manager.get("dev_mode", default=False):
            self.btn_refresh.setText(f"Refresh (F5) [{duration:.2f}s]")
        else:
            self.btn_refresh.setText("Refresh (F5)")

        if "Building Cache" in self.header_label.text():
             self.header_label.setText("ANALYTICS")
             
        self.btn_refresh.setEnabled(True)

    def closeEvent(self, event):
        settings = {
            "geometry": self.saveGeometry().toHex().data().decode(),
            "windowState": self.saveState().toHex().data().decode(),
            "splitterState": self.center_splitter.saveState().toHex().data().decode()
        }
        self.config_manager.set_global("app_layout", settings)
        self.grid_container.save_state()
        super().closeEvent(event)

    def load_app_state(self):
        settings = self.config_manager.get("app_layout", default={})
        if "geometry" in settings:
            self.restoreGeometry(QByteArray.fromHex(settings["geometry"].encode()))
        if "windowState" in settings:
            self.restoreState(QByteArray.fromHex(settings["windowState"].encode()))
        if "splitterState" in settings:
            self.center_splitter.restoreState(QByteArray.fromHex(settings["splitterState"].encode()))
        else:
            # First Time Defaults
            # Make Browser Wider (350px)
            self.resizeDocks([self.dock_nav], [350], Qt.Orientation.Horizontal)
            self.resizeDocks([self.dock_analyst], [400], Qt.Orientation.Horizontal)
            
            # Force Layout: Chart (Top, 300px), Grid (Bottom, 700px)
            self.center_splitter.setSizes([400, 600])

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KovaaksV2App()
    window.show()
    sys.exit(app.exec())