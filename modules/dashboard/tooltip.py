from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QPoint, QSize
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath

class SparklineWidget(QWidget):
    def __init__(self, scores, avg, p75):
        super().__init__()
        self.setMinimumHeight(80)
        self.setMinimumWidth(280)
        self.scores = scores
        self.avg = avg
        self.p75 = p75
        self.setStyleSheet("background: transparent;")

    def sizeHint(self): return QSize(280, 80)

    def paintEvent(self, event):
        if not self.scores or len(self.scores) < 2: return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        padding = 10
        min_val, max_val = min(self.scores), max(self.scores)
        rng = max_val - min_val if max_val > min_val else 1.0
        
        def get_y(val): return h - padding - (((val - min_val) / rng) * (h - 2*padding))
        def get_x(idx): return padding + (idx / (len(self.scores) - 1)) * (w - 2*padding)

        # Draw Avg (Grey Dashed)
        y_avg = get_y(self.avg)
        pen_avg = QPen(QColor("#787b86"), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen_avg)
        painter.drawLine(int(padding), int(y_avg), int(w-padding), int(y_avg))

        # Draw p75 (Green Dashed) - ALWAYS DRAW
        y_p75 = get_y(self.p75)
        pen_p75 = QPen(QColor("#4CAF50"), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen_p75)
        painter.drawLine(int(padding), int(y_p75), int(w-padding), int(y_p75))

        # Draw Line
        path = QPainterPath()
        path.moveTo(get_x(0), get_y(self.scores[0]))
        for i, val in enumerate(self.scores): path.lineTo(get_x(i), get_y(val))
        painter.setPen(QPen(QColor("#4aa3df"), 2))
        painter.drawPath(path)

        # Draw Max Dot
        max_idx = self.scores.index(max_val)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#FFD700"))
        painter.drawEllipse(QPoint(int(get_x(max_idx)), int(get_y(max_val))), 4, 4)

class CustomTooltip(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        # REMOVED: WA_TranslucentBackground (This caused the see-through ghosting)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        
        # Solid Styling
        self.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border: 1px solid #485c7b;
                border-radius: 4px;
            }
            QLabel { background: transparent; color: #d1d4dc; border: none; }
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 12, 12, 12)
        self.layout.setSpacing(4)

        self.lbl_title = QLabel()
        self.lbl_title.setStyleSheet("font-weight: bold; color: #4aa3df; font-size: 13px;")
        self.layout.addWidget(self.lbl_title)
        
        self.lbl_sub = QLabel()
        self.lbl_sub.setStyleSheet("font-weight: bold; color: #FF9800; font-size: 12px;")
        self.layout.addWidget(self.lbl_sub)
        
        self.layout.addWidget(self.create_line())
        
        self.lbl_pb = QLabel()
        self.layout.addWidget(self.lbl_pb)
        self.lbl_stats = QLabel()
        self.layout.addWidget(self.lbl_stats)
        self.lbl_med = QLabel()
        self.layout.addWidget(self.lbl_med)
        
        self.layout.addWidget(self.create_line())
        
        self.lbl_launchpad = QLabel()
        self.layout.addWidget(self.lbl_launchpad)
        self.lbl_recent = QLabel()
        self.layout.addWidget(self.lbl_recent)
        
        self.spark_container = QVBoxLayout()
        self.layout.addLayout(self.spark_container)

    def create_line(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        line.setStyleSheet("color: #363a45;")
        return line

    def update_data(self, title, sub_title, stats, runs):
        self.lbl_title.setText(title)
        self.lbl_sub.setText(sub_title)
        
        pb_date = stats['pb_date'].strftime('%Y-%m-%d')
        sens_str = f" ({stats.get('pb_sens')}cm)" if stats.get('pb_sens') else ""
        self.lbl_pb.setText(f"PB: {stats['max']:.1f}{sens_str} (on {pb_date})")
        
        self.lbl_stats.setText(f"Runs: {stats['count']} | Avg: {stats['avg']:.1f} (±{stats['std']:.1f})")
        self.lbl_med.setText(f"Median: {stats['p50']:.1f} | 75th: {stats['p75']:.1f}")
        
        self.lbl_launchpad.setText(f"Avg before prev PB: {stats['launchpad_avg']:.1f}")
        self.lbl_recent.setText(f"Recent Avg: {stats.get('recent_avg', 0):.1f}")
        
        while self.spark_container.count():
            child = self.spark_container.takeAt(0)
            if child.widget(): child.widget().deleteLater()
            
        if len(runs) > 200: runs = runs[::(len(runs)//200)]
        spark = SparklineWidget(runs, stats['avg'], stats['p75'])
        self.spark_container.addWidget(spark)
        self.adjustSize()