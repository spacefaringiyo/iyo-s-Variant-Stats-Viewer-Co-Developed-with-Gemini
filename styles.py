# styles.py

BG_DARK = "#131722"
BG_PANEL = "#1e222d"
BG_HOVER = "#2a2e39"
ACCENT = "#2962FF"
TEXT_MAIN = "#d1d4dc"
TEXT_DIM = "#787b86"
BORDER = "#363a45"
BG_BROWSER_PANEL = "#2c2c2c"

QSS = f"""
QMainWindow {{
    background-color: {BG_DARK};
}}

/* --- DOCK WIDGETS --- */
QDockWidget {{
    titlebar-close-icon: url(close.png);
    titlebar-normal-icon: url(float.png);
    color: {TEXT_MAIN};
    font-weight: bold;
}}
QDockWidget::title {{
    background: {BG_PANEL};
    padding-left: 10px;
    padding-top: 4px;
    padding-bottom: 4px;
    border-bottom: 1px solid {BORDER};
}}
QDockWidget::close-button, QDockWidget::float-button {{
    background: transparent;
    border: none;
}}
QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
    background: {BG_HOVER};
}}

/* --- COMMON INPUTS --- */
QWidget {{
    color: {TEXT_MAIN};
}}
QFrame#Panel {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 4px;
}}
QLineEdit {{
    background-color: {BG_DARK};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px;
    color: {TEXT_MAIN};
}}
QPushButton {{
    background-color: {BG_HOVER};
    border: 1px solid {BORDER};
    color: {TEXT_MAIN};
    padding: 6px 12px;
    border-radius: 4px;
}}
QPushButton:hover {{
    background-color: {ACCENT};
    border: 1px solid {ACCENT};
    color: white;
}}

/* --- DROPDOWNS (Combos) --- */
QComboBox {{
    background-color: {BG_DARK};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 5px;
    color: {TEXT_MAIN};
}}
QComboBox:hover {{
    border: 1px solid {TEXT_DIM};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
/* The popup list inside the combo box */
QComboBox QAbstractItemView {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    selection-color: white;
    color: {TEXT_MAIN};
    outline: none;
}}

/* --- LISTS & TREES (Sidebar, Session List) --- */
QTreeWidget, QListWidget {{
    background-color: {BG_BROWSER_PANEL};
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: {TEXT_MAIN};
    outline: none; 
}}
QTreeWidget::item, QListWidget::item {{
    padding: 4px;
}}
QTreeWidget::item:hover, QListWidget::item:hover {{
    background-color: {BG_HOVER};
}}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background-color: {BG_HOVER}; 
    color: {ACCENT};
    border-left: 2px solid {ACCENT};
}}

/* --- TABLES --- */
QTableWidget {{
    background-color: {BG_DARK};
    gridline-color: {BORDER};
    border: none;
    outline: none;
}}
QHeaderView::section {{
    background-color: {BG_PANEL};
    color: {TEXT_DIM};
    border: none;
    border-bottom: 1px solid {BORDER};
    border-right: 1px solid {BORDER};
    padding: 4px;
}}

/* --- SCROLL BARS (Optional Polish) --- */
QScrollBar:vertical {{
    border: none;
    background: {BG_DARK};
    width: 10px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: {BG_HOVER};
    min-height: 20px;
    border-radius: 5px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""