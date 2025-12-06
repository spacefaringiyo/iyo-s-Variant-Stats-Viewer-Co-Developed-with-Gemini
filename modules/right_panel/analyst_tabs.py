from PyQt6.QtWidgets import QTabWidget, QWidget, QVBoxLayout, QLabel
from modules.right_panel.ongoing import OngoingWidget
from modules.session.session_manager import SessionManager
from modules.career.career_widget import CareerWidget
from modules.calendar.calendar_widget import CalendarWidget

class AnalystTabs(QTabWidget):
    # Added config_manager to init
    def __init__(self, state_manager, config_manager): 
        super().__init__()
        self.state_manager = state_manager
        self.config = config_manager # Store config
        self.is_first_load = True
        
        # 1. Calendar
        self.calendar_tab = CalendarWidget(state_manager)
        self.addTab(self.calendar_tab, "Calendar")
        
        # 2. Ongoing
        self.ongoing_tab = OngoingWidget(state_manager)
        self.addTab(self.ongoing_tab, "Ongoing")
        
        # 3. Session Report
        self.session_tab = SessionManager(state_manager)
        self.addTab(self.session_tab, "Session Report")
        
        # 4. Career
        self.career_tab = CareerWidget(state_manager)
        self.addTab(self.career_tab, "Career Profile")
        
        self.setStyleSheet("""
            QTabBar::tab { background: #1e222d; color: #787b86; padding: 8px 12px; border-bottom: 1px solid #363a45; }
            QTabBar::tab:selected { background: #131722; color: #d1d4dc; border-bottom: 2px solid #2962FF; }
            QTabWidget::pane { border: none; background: #131722; }
        """)
        
        self.state_manager.session_selected.connect(self.on_session_jump)
        self.currentChanged.connect(self.save_active_tab)

        self.state_manager.request_date_jump.connect(self.on_date_jump)
        
        self.restore_active_tab()

    def on_session_jump(self, sess_id):
        if self.is_first_load:
            self.is_first_load = False
            return
        self.setCurrentIndex(2)

    def on_date_jump(self, date_obj):
        # Switch to Calendar Tab (Index 0)
        self.setCurrentIndex(0)

    def save_active_tab(self, index):
        # Save "Last" state automatically
        self.config.set_global("last_active_tab", index)

    def restore_active_tab(self):
        # Check settings
        mode = self.config.get("startup_tab_mode", default="Last")
        
        index = 0
        if mode == "Last":
            index = self.config.get("last_active_tab", default=0)
        elif mode == "Calendar": index = 0
        elif mode == "Ongoing": index = 1
        elif mode == "Session Report": index = 2
        elif mode == "Career Profile": index = 3
        
        self.setCurrentIndex(index)