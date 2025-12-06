from PyQt6.QtCore import QObject, pyqtSignal

class StateManager(QObject):
    """
    Central Hub for application state.
    """
    data_updated = pyqtSignal(object) 
    scenario_selected = pyqtSignal(str) 
    variant_selected = pyqtSignal(dict) 
    
    playlist_selected = pyqtSignal(object) 
    
    settings_changed = pyqtSignal() 
    session_selected = pyqtSignal(int)
    
    chart_title_changed = pyqtSignal(str) 
    request_date_jump = pyqtSignal(object)

    def __init__(self):
        super().__init__()