from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLineEdit, QTreeWidget, 
                             QTreeWidgetItem, QLabel, QPushButton, QHBoxLayout, QMenu)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from core.analytics import playlists

class PlaylistNavigationWidget(QWidget):
    def __init__(self, state_manager, config_manager):
        super().__init__()
        self.state_manager = state_manager
        self.config_manager = config_manager
        self.setup_ui()
        self.refresh_list()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Search
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Filter Playlists...")
        self.search_bar.textChanged.connect(self.on_search_text_changed)
        layout.addWidget(self.search_bar)

        # Refresh
        btn_refresh = QPushButton("Refresh Lists")
        btn_refresh.clicked.connect(self.refresh_list)
        layout.addWidget(btn_refresh)

        # Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(20)
        self.tree.itemClicked.connect(self.on_item_clicked)
        
        # Enable Right-Click Context Menu
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        
        layout.addWidget(self.tree)

        # Roots
        self.playing_root = QTreeWidgetItem(self.tree, ["Playing Now"])
        self.playing_root.setExpanded(True)
        font = self.playing_root.font(0); font.setBold(True)
        self.playing_root.setFont(0, font)
        self.playing_root.setForeground(0, Qt.GlobalColor.green)

        # NEW: Favorites Root
        self.fav_root = QTreeWidgetItem(self.tree, ["Favorites"])
        self.fav_root.setExpanded(True)

        self.all_root = QTreeWidgetItem(self.tree, ["All Playlists"])
        self.all_root.setExpanded(True)

    def refresh_list(self):
        self.playing_root.takeChildren()
        self.fav_root.takeChildren()
        self.all_root.takeChildren()
        
        path = self.config_manager.get("playlist_path")
        if not path:
            path = playlists.auto_detect_playlists_path()
            if path: self.config_manager.set_global("playlist_path", path)
        
        if not path:
            QTreeWidgetItem(self.all_root, ["No Playlist Folder Set"]).setDisabled(True)
            return

        # 1. Playing Now
        active_name, active_scens = playlists.get_active_playlist(path)
        if active_name:
            item = QTreeWidgetItem(self.playing_root, [active_name])
            item.setData(0, Qt.ItemDataRole.UserRole, {'name': active_name, 'scenarios': active_scens})
            item.setForeground(0, Qt.GlobalColor.cyan)
        else:
            QTreeWidgetItem(self.playing_root, ["(None Detected)"]).setDisabled(True)

        # 2. Scan All
        pl_files = playlists.scan_playlists(path)
        
        # 3. Populate All & Favorites
        favs = self.config_manager.get_playlist_favorites()
        
        # Map path to name for favorites lookup if needed, 
        # but here we iterate the scanned files.
        for pl in pl_files:
            name = pl['name']
            file_path = pl['path']
            
            # Add to All
            item_all = QTreeWidgetItem(self.all_root, [name])
            item_all.setData(0, Qt.ItemDataRole.UserRole, file_path)
            
            # Add to Favorites if match
            if name in favs:
                item_fav = QTreeWidgetItem(self.fav_root, [name])
                item_fav.setData(0, Qt.ItemDataRole.UserRole, file_path)

    # --- NEW: Context Menu ---
    def show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item: return
        
        # Only allow items with data (skip headers/empty placeholders)
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data: return 
        
        name = item.text(0)
        is_fav = self.config_manager.is_playlist_favorite(name)
        
        menu = QMenu(self)
        action_text = "Remove from Favorites" if is_fav else "Add to Favorites"
        action = QAction(action_text, self)
        action.triggered.connect(lambda: self.toggle_favorite(name))
        menu.addAction(action)
        
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def toggle_favorite(self, name):
        if self.config_manager.is_playlist_favorite(name):
            self.config_manager.remove_playlist_favorite(name)
        else:
            self.config_manager.add_playlist_favorite(name)
        self.refresh_list() # Re-render tree

    # --- UPDATED: Search to include Favorites ---
    def on_search_text_changed(self, text):
        search_text = text.lower()
        
        def filter_root(root):
            visible_count = 0
            for i in range(root.childCount()):
                item = root.child(i)
                match = search_text in item.text(0).lower()
                item.setHidden(not match)
                if match: visible_count += 1
            
            # Optional: Hide header if empty search results
            if search_text: root.setHidden(visible_count == 0)
            else: root.setHidden(False)

        filter_root(self.playing_root)
        filter_root(self.fav_root)
        filter_root(self.all_root)
        
        if search_text:
            self.playing_root.setExpanded(True)
            self.fav_root.setExpanded(True)
            self.all_root.setExpanded(True)

    def on_item_clicked(self, item, column):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data: return 

        payload = {}
        if isinstance(data, dict):
            # Playing Now (Pre-parsed)
            payload = data
        elif isinstance(data, str):
            # File Path (Lazy Parse)
            scens = playlists.parse_playlist(data)
            payload = {'name': item.text(0), 'scenarios': scens}
            
        if payload:
            self.state_manager.playlist_selected.emit(payload)