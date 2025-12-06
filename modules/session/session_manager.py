from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QStackedWidget, QPushButton, 
                             QHBoxLayout, QLabel, QFrame, QCheckBox)
from PyQt6.QtCore import Qt
from core.config_manager import ConfigManager
from modules.session.session_list import SessionListWidget
from modules.session.session_report import SessionReportWidget

class SessionManager(QWidget):
    def __init__(self, state_manager):
        super().__init__()
        self.state_manager = state_manager
        self.config_manager = ConfigManager()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        # HEADER
        self.header = QFrame()
        self.header.setStyleSheet("background: #1e222d; border-bottom: 1px solid #363a45;")
        self.header.setFixedHeight(40)
        h_layout = QHBoxLayout(self.header)
        h_layout.setContentsMargins(5,0,5,0)
        
        # LEFT: Back Button
        self.btn_back = QPushButton("← History")
        self.btn_back.setStyleSheet("border: none; font-weight: bold; color: #2962FF;")
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.clicked.connect(self.go_to_list)
        self.btn_back.setVisible(False) 
        self.btn_back.setFixedWidth(80)
        
        # CENTER: Title
        self.lbl_title = QLabel("Session History")
        self.lbl_title.setStyleSheet("font-weight: bold; color: #d1d4dc; font-size: 14px;")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # RIGHT: Toggles
        # 1. Stack PBs
        self.chk_stack = QCheckBox("Stack PBs")
        stack_val = self.config_manager.get("session_stack_pbs", default=False)
        self.chk_stack.setChecked(stack_val)
        self.chk_stack.stateChanged.connect(self.on_toggles_changed) # Unified handler
        
        # 2. Count New (NEW)
        self.chk_count_new = QCheckBox("Count New")
        new_val = self.config_manager.get("session_count_new", default=False)
        self.chk_count_new.setChecked(new_val)
        self.chk_count_new.stateChanged.connect(self.on_toggles_changed)

        h_layout.addWidget(self.btn_back)
        h_layout.addStretch()
        h_layout.addWidget(self.lbl_title)
        h_layout.addStretch()
        h_layout.addWidget(self.chk_stack)
        h_layout.addSpacing(10)
        h_layout.addWidget(self.chk_count_new)
        
        layout.addWidget(self.header)

        # STACK
        self.stack = QStackedWidget()
        self.page_list = SessionListWidget(state_manager)
        self.page_report = SessionReportWidget(state_manager)
        
        self.stack.addWidget(self.page_list)
        self.stack.addWidget(self.page_report)
        
        self.state_manager.session_selected.connect(self.go_to_report)
        
        layout.addWidget(self.stack)
        
        # Trigger initial state
        self.on_toggles_changed()

    def on_toggles_changed(self):
        stack_val = self.chk_stack.isChecked()
        new_val = self.chk_count_new.isChecked()
        
        self.config_manager.set_global("session_stack_pbs", stack_val)
        self.config_manager.set_global("session_count_new", new_val)
        
        # Update Sub-Widgets
        self.page_report.set_view_options(stack_val, new_val)
        self.page_list.update_display(stack_val, new_val) # NEW method in list

    def go_to_report(self, session_id):
        self.stack.setCurrentWidget(self.page_report)
        self.btn_back.setVisible(True)
        self.lbl_title.setText(f"Session #{int(session_id)}")

    def go_to_list(self):
        self.stack.setCurrentWidget(self.page_list)
        self.btn_back.setVisible(False)
        self.lbl_title.setText("Session History")