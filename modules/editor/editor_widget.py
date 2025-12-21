from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal

class EditorWidget(QWidget):
    # Signal to tell Main Window to go back
    close_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        # 1. Header Toolbar
        header = QFrame()
        header.setStyleSheet("background: #1e222d; border-bottom: 1px solid #363a45;")
        header.setFixedHeight(50)
        h_layout = QHBoxLayout(header)
        
        # Back Button
        btn_back = QPushButton("← Back to Dashboard")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.setStyleSheet("""
            QPushButton { background: #2a2e39; border: none; color: #d1d4dc; font-weight: bold; padding: 6px 12px; border-radius: 4px; }
            QPushButton:hover { background: #363a45; color: white; }
        """)
        btn_back.clicked.connect(self.close_requested.emit)
        
        h_layout.addWidget(btn_back)
        h_layout.addStretch()
        h_layout.addWidget(QLabel("SCENARIO EDITOR MODE"))
        h_layout.addStretch()
        
        layout.addWidget(header)
        
        # 2. Placeholder Content
        content = QLabel("Editor UI will go here.\n(Center + Right Panel Space)")
        content.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content.setStyleSheet("font-size: 20px; color: #787b86; font-weight: bold;")
        layout.addWidget(content, stretch=1)