from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QListWidget, QListWidgetItem, 
                             QLabel)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMutex
import pandas as pd
from core.config_manager import ConfigManager
from core.analytics import stats

class AnalysisWorker(QThread):
    # Signals: SessionID, ScenPBCount, SensPBCount
    result_ready = pyqtSignal(int, int, int)
    finished = pyqtSignal()
    
    def __init__(self, full_df, session_ids, stack_pbs, count_new):
        super().__init__()
        # We perform a shallow copy. Pandas is usually copy-on-write, so this is safe for reading.
        self.full_df = full_df
        self.session_ids = session_ids
        self.stack_pbs = stack_pbs
        self.count_new = count_new
        self.is_aborted = False

    def abort(self):
        self.is_aborted = True

    def run(self):
        # We loop through sessions.
        # To optimize, we can sort them, but the order doesn't strictly matter 
        # as long as we emit the ID.
        
        for sess_id in self.session_ids:
            if self.is_aborted: return
            
            # Extract specific session
            session_df = self.full_df[self.full_df['SessionID'] == sess_id]
            if session_df.empty: continue
            
            # Run the FAST PATH analysis
            # We don't need to slice 'prior_history' manually here; 
            # analyze_session does it. But passing the whole DF repeatedly is slightly inefficient.
            # However, for Lazy Loading, accuracy > micro-optimization of DF passing.
            
            # Note: analyze_session filters history_df based on timestamp.
            # Passing self.full_df as 'history_df' is correct.
            
            try:
                counts = stats.analyze_session(
                    session_df, 
                    self.full_df, 
                    stack_pbs=self.stack_pbs, 
                    count_new=self.count_new, 
                    summary_only=True
                )
                
                if counts and not self.is_aborted:
                    self.result_ready.emit(sess_id, counts['scen_pb_count'], counts['sens_pb_count'])
            except Exception as e:
                # Silently fail on one session rather than crash thread
                print(f"Error analyzing session {sess_id}: {e}")
                
        self.finished.emit()

class SessionListWidget(QWidget):
    def __init__(self, state_manager):
        super().__init__()
        self.state_manager = state_manager
        self.config_manager = ConfigManager()
        self.current_selected_id = None
        self.df = None 
        
        # --- CACHING & THREADING ---
        self.worker = None
        # Cache Key: (sess_id, stack_bool, count_new_bool) -> (scen_count, sens_count)
        self.pb_cache = {} 
        
        self.setup_ui()
        
        self.state_manager.data_updated.connect(self.on_data_updated)
        self.state_manager.session_selected.connect(self.on_external_selection)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        lbl = QLabel("History")
        lbl.setStyleSheet("font-weight: bold; padding: 10px; color: #787b86;")
        layout.addWidget(lbl)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("border: none; background: #131722;")
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.list_widget)

    def on_external_selection(self, sess_id):
        self.current_selected_id = sess_id
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == sess_id:
                self.list_widget.setCurrentItem(item)
                return
        self.list_widget.clearSelection()

    def on_data_updated(self, df):
        if df is None or 'SessionID' not in df.columns: return
        self.df = df
        
        # Clear cache on new data load (file reload)
        self.pb_cache = {} 
        
        stack = self.config_manager.get("session_stack_pbs", default=False)
        count_new = self.config_manager.get("session_count_new", default=False)
        
        self.update_display(stack, count_new)

    def update_display(self, stack_pbs, count_new):
        if self.df is None: return
        
        # 1. Stop any existing worker
        if self.worker and self.worker.isRunning():
            self.worker.abort()
            self.worker.wait() # Wait for it to safely stop
        
        self.list_widget.clear()
        
        # 2. Basic Aggregation (Fast) - Just Date, Duration, Count
        grouped = self.df.groupby('SessionID')
        sess_stats = grouped.agg(
            StartTime=('Timestamp', 'min'),
            Count=('Score', 'size'),
            Duration=('Duration', 'sum'),
            MostPlayed=('Scenario', lambda x: x.mode().iloc[0] if not x.empty else "N/A")
        ).sort_index(ascending=False)
        
        # 3. Populate List (Initially without PBs)
        sessions_needing_calc = []
        
        item_to_select = None
        
        for sess_id, row in sess_stats.iterrows():
            sid = int(sess_id)
            date_str = row['StartTime'].strftime('%Y-%m-%d %H:%M')
            duration_min = int(row['Duration'] // 60)
            
            # Check Cache
            cache_key = (sid, stack_pbs, count_new)
            pb_text = "..."
            
            if cache_key in self.pb_cache:
                scen_pb, sens_pb = self.pb_cache[cache_key]
                pb_text = self._format_pb_text(scen_pb, sens_pb)
            else:
                sessions_needing_calc.append(sid)
            
            # Store metadata we need to update label later
            label_base = (f"#{sid} - {date_str}\n"
                          f"{row['MostPlayed']}\n"
                          f"{row['Count']} Runs ({duration_min}m)")
            
            label_full = f"{label_base} | {pb_text}"
            
            item = QListWidgetItem(label_full)
            item.setData(Qt.ItemDataRole.UserRole, sid)
            # Store base text so we can append PB later
            item.setData(Qt.ItemDataRole.UserRole + 1, label_base) 
            
            self.list_widget.addItem(item)
            
            if self.current_selected_id == sid:
                item_to_select = item

        if item_to_select: self.list_widget.setCurrentItem(item_to_select)
        elif self.list_widget.count() > 0:
             # Auto-select first but don't emit to avoid loops
             self.list_widget.setCurrentRow(0)
             self.current_selected_id = self.list_widget.item(0).data(Qt.ItemDataRole.UserRole)

        # 4. Start Background Worker if needed
        if sessions_needing_calc:
            self.worker = AnalysisWorker(self.df, sessions_needing_calc, stack_pbs, count_new)
            self.worker.result_ready.connect(self.on_worker_result)
            self.worker.start()

    def on_worker_result(self, sess_id, scen_pb, sens_pb):
        # 1. Update Cache
        # We need to know current toggles to store the key correctly.
        # We can fetch from config or store them in class.
        # Ideally, we trust the worker was spawned with current config.
        # But if user toggled quickly, this result might be stale.
        # Check if worker is still valid (not aborted).
        if self.worker and self.worker.is_aborted: return

        stack = self.worker.stack_pbs
        new = self.worker.count_new
        self.pb_cache[(sess_id, stack, new)] = (scen_pb, sens_pb)
        
        # 2. Update UI Row
        # Find item by iterating (linear search is fast enough for <5000 items)
        # Optimization: We could store {sess_id: item} map in update_display
        # But QListWidget isn't too slow.
        
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == sess_id:
                base_text = item.data(Qt.ItemDataRole.UserRole + 1)
                pb_text = self._format_pb_text(scen_pb, sens_pb)
                item.setText(f"{base_text} | {pb_text}")
                break

    def _format_pb_text(self, scen_pb, sens_pb):
        txt = ""
        if scen_pb > 0: txt += f"{scen_pb} 🏆  "
        if sens_pb > 0: txt += f"{sens_pb} 🎯"
        if not txt: txt = "0 PBs"
        return txt

    def on_item_clicked(self, item):
        sess_id = item.data(Qt.ItemDataRole.UserRole)
        self.current_selected_id = sess_id
        self.state_manager.session_selected.emit(sess_id)