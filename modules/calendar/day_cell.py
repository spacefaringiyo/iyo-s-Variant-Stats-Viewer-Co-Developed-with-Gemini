from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

class DayCell(QFrame):
    clicked = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.date = None
        self.is_selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(2,2,2,2)
        self.layout.setSpacing(0)
        
        # Row 1: Date | Time
        r1 = QHBoxLayout()
        self.lbl_date = QLabel()
        self.lbl_date.setStyleSheet("font-weight: bold; color: #787b86;")
        self.lbl_time = QLabel()
        self.lbl_time.setStyleSheet("font-size: 10px; color: #4aa3df;")
        r1.addWidget(self.lbl_date); r1.addStretch(); r1.addWidget(self.lbl_time)
        self.layout.addLayout(r1)
        
        # Row 2: Runs
        self.lbl_runs = QLabel()
        self.lbl_runs.setStyleSheet("font-size: 10px; color: #d1d4dc;")
        self.lbl_runs.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.lbl_runs)
        
        # Row 3: PBs (Scen | Sens)
        r3 = QHBoxLayout()
        self.lbl_pb_scen = QLabel()
        self.lbl_pb_scen.setStyleSheet("font-size: 10px; color: #FFD700;")
        self.lbl_pb_sens = QLabel()
        self.lbl_pb_sens.setStyleSheet("font-size: 10px; color: #FFD700;")
        r3.addWidget(self.lbl_pb_scen); r3.addStretch(); r3.addWidget(self.lbl_pb_sens)
        self.layout.addLayout(r3)
        
        self.layout.addStretch()

    def set_data(self, date, stats, is_current_month, max_activity, is_selected):
        self.date = date
        self.is_selected = is_selected
        
        day_str = str(date.day)
        if date.day == 1: day_str = date.strftime("%b %d")
        self.lbl_date.setText(day_str)
        
        # Reset
        self.lbl_time.setText(""); self.lbl_runs.setText("")
        self.lbl_pb_scen.setText(""); self.lbl_pb_sens.setText("")
        
        if not is_current_month:
            self.setStyleSheet(f"background: #131722; border: 1px solid #2B2B43;"); self.lbl_date.setStyleSheet("color: #444;")
            self.setEnabled(False)
            return
        
        self.setEnabled(True)
        self.lbl_date.setStyleSheet("font-weight: bold; color: #787b86;")

        bg_color = "#1e222d"
        
        if stats:
            dur_min = int(stats['duration'] // 60)
            self.lbl_time.setText(f"{dur_min}m")
            self.lbl_runs.setText(f"{stats['runs']} runs")
            
            scen_pb = stats.get('pbs_scen', 0)
            sens_pb = stats.get('pbs_sens', 0)
            
            # Format: "3 🏆" | "5 🎯"
            if scen_pb > 0: self.lbl_pb_scen.setText(f"{scen_pb} 🏆")
            if sens_pb > 0: self.lbl_pb_sens.setText(f"{sens_pb} 🎯")
            
            if max_activity > 0:
                intensity = min(1.0, stats['duration'] / max_activity)
                alpha = int(intensity * 120) + 20
                bg_color = f"rgba(46, 125, 50, {alpha})"
        
        border = "#2962FF" if is_selected else "#363a45"
        width = "2px" if is_selected else "1px"
        self.setStyleSheet(f"QFrame {{ background-color: {bg_color}; border: {width} solid {border}; border-radius: 4px; }} QLabel {{ background: transparent; border: none; }}")

    def mousePressEvent(self, event):
        if self.isEnabled(): self.clicked.emit(self.date)
        super().mousePressEvent(event)