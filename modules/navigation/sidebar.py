from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLineEdit, QTreeWidget, 
                             QTreeWidgetItem, QLabel, QFrame, QMenu)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

class NavigationWidget(QWidget):
    def __init__(self, state_manager, config_manager=None):
        super().__init__()
        self.state_manager = state_manager
        self.config_manager = config_manager # Stores it
        self.scenario_list = []
        self.setup_ui()
        
        self.state_manager.data_updated.connect(self.on_data_updated)
        
        if self.config_manager:
            self.refresh_favorites()

    # Added config_manager to init signature
    #removed to to above change
    #def set_config_manager(self, cfg):
    #   self.config_manager = cfg
    #    self.refresh_favorites()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Filter Scenarios...")
        self.search_bar.textChanged.connect(self.on_search_text_changed)
        self.search_bar.returnPressed.connect(self.on_enter_pressed)
        layout.addWidget(self.search_bar)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(20)
        self.tree.itemClicked.connect(self.on_item_clicked)
        
        # Context Menu
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        
        layout.addWidget(self.tree)

        self.favorites_root = QTreeWidgetItem(self.tree, ["Favorites"])
        self.favorites_root.setExpanded(True)
        
        self.recents_root = QTreeWidgetItem(self.tree, ["Recently Played"])
        self.recents_root.setExpanded(True)

        self.all_root = QTreeWidgetItem(self.tree, ["All Scenarios"])
        self.all_root.setExpanded(True)

    def on_data_updated(self, df):
        if df is None: return
        
        # 1. Get new list
        new_scenarios = sorted(df['Scenario'].unique())
        
        # 2. Smart Diff: Only rebuild "All Scenarios" if the list actually changed
        # We store self.scenario_list in the class (it was already there), so we compare against it.
        if new_scenarios != self.scenario_list:
            self.scenario_list = new_scenarios
            
            self.all_root.takeChildren()
            # Batch operations are faster, but QTreeWidget requires item-by-item adds usually.
            # However, not doing this at all is infinite% faster.
            for scen in self.scenario_list:
                QTreeWidgetItem(self.all_root, [scen])
        
        # 3. Always update Recents (Fast and changes every run)
        self.recents_root.takeChildren()
        recent_df = df.sort_values('Timestamp', ascending=False)
        recents = recent_df['Scenario'].drop_duplicates().head(25).tolist()
        for scen in recents:
            QTreeWidgetItem(self.recents_root, [scen])
            
        if hasattr(self, 'config_manager'):
            self.refresh_favorites()

    def refresh_favorites(self):
        if not hasattr(self, 'config_manager'): return
        favs = self.config_manager.get_favorites()
        self.favorites_root.takeChildren()
        for f in favs:
            QTreeWidgetItem(self.favorites_root, [f])

    def show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item: return
        
        # Only allow favoriting scenarios (leaf nodes)
        if item.childCount() > 0: return 
        
        scenario_name = item.text(0)
        is_fav = self.config_manager.is_favorite(scenario_name)
        
        menu = QMenu(self)
        action_text = "Remove from Favorites" if is_fav else "Add to Favorites"
        action = QAction(action_text, self)
        action.triggered.connect(lambda: self.toggle_favorite(scenario_name))
        menu.addAction(action)
        
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def toggle_favorite(self, name):
        if self.config_manager.is_favorite(name):
            self.config_manager.remove_favorite(name)
        else:
            self.config_manager.add_favorite(name)
        self.refresh_favorites()

    def on_search_text_changed(self, text):
        search_text = text.lower()
        
        # Helper to filter children of a top-level item
        def filter_category(root_item):
            visible_children = 0
            for i in range(root_item.childCount()):
                item = root_item.child(i)
                # Check if item matches
                is_match = search_text in item.text(0).lower()
                item.setHidden(not is_match)
                if is_match:
                    visible_children += 1
            
            # Optional: Hide the category header if no children match, 
            # but keep it visible if search is empty (to show structure)
            if search_text:
                root_item.setHidden(visible_children == 0)
            else:
                root_item.setHidden(False)
                # When clearing search, unhide all children
                for i in range(root_item.childCount()):
                    root_item.child(i).setHidden(False)

        # Apply to all 3 roots
        filter_category(self.favorites_root)
        filter_category(self.recents_root)
        filter_category(self.all_root)
        
        # If searching, expand everything to show results. 
        # If clearing, maybe collapse? Let's keep it simple: Expand on search.
        if search_text:
            self.favorites_root.setExpanded(True)
            self.recents_root.setExpanded(True)
            self.all_root.setExpanded(True)

    def on_enter_pressed(self):
        child_count = self.all_root.childCount()
        for i in range(child_count):
            item = self.all_root.child(i)
            if not item.isHidden():
                self.state_manager.scenario_selected.emit(item.text(0))
                self.tree.setCurrentItem(item)
                return

    def on_item_clicked(self, item, column):
        if item.childCount() > 0: return 
        self.state_manager.scenario_selected.emit(item.text(0))