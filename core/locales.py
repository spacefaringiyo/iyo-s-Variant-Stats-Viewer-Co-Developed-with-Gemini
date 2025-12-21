# locales.py

# --- CENTRAL VERSION CONTROL ---
APP_VERSION = "v2.1.0"
# -------------------------------

# Dictionary of all text used in the app
TRANSLATIONS = {
    "en": {
        # Main UI
        "window_title": "Variant Stats Viewer by iyo & Gemini ({ver})", # Use {ver} placeholder
        "search_label": "Search for Base Scenario:",
        "ready_label": "Ready. Select stats folder and click 'Load Stats'.",
        "loading_label": "Loading stats, please wait...",
        "loaded_label": "Loaded {count} total runs. Ready to search.",
        "load_err_label": "Load failed or no data found.",
        "load_btn": "Load Stats",
        "refresh_btn": "Refresh Stats (F5)",
        "session_report_btn": "Last Session Report",
        "session_hist_btn": "Session History",
        "select_folder_btn": "Select Stats Folder",
        "hint_hide": "(Right-click Scenario/CM to hide)",
        
        # Lists
        "recently_played": "Recently Played",
        "favorites": "Favorites",
        "recents": "Recents",
        "compare_by": "Compare by:",
        "filter_format": "Filter Format:",
        
        # Settings Row
        "session_gap": "Session Gap (min):",
        "req_refresh": "(Requires Refresh)",
        "theme": "Theme:",
        "show_decimals": "Show Decimals",
        "manage_hidden": "Manage Hidden",
        "font_size": "Font Size:",
        "cell_h": "Cell H:",
        
        # Analysis Modes
        "sens_filter": "Sens Filter:",
        "grid_mode": "Grid Mode:",
        "highlight": "Highlight:",
        "pb_num": "PB #:",
        "target": "Target:",
        
        # Dropdown Options & Radio Buttons
        "opt_all": "All",
        "opt_5cm": "5cm Inc.",
        "opt_10cm": "10cm Inc.",
        "opt_custom_step": "Custom Step",
        "opt_specific": "Specific List",
        
        "mode_pb": "Personal Best",
        "mode_avg": "Average Score",
        "mode_count": "Play Count",
        "mode_percentile": "Nth Percentile",
        
        "hl_none": "None",
        "hl_drop": "Performance Drop",
        "hl_row_heat": "Row Heatmap",
        "hl_global_heat": "Global Heatmap",
        "hl_target": "Target Score",
        "hl_recent_success": "Recent Success (Days)",
        
        # Grid Headers / Tooltips
        "rating": "Global Average: {val}",
        "avg_row": "-- Averages --",
        "col_avg": "AVG",
        "col_best": "Best",
        "col_cm": "cm",
        "tooltip_sens": "Sensitivity: {val}",
        "tooltip_pb": "PB: {val} (on {date})",
        "tooltip_runs": "Runs: {val}",
        "tooltip_avg": "Avg: {val}",
        "tooltip_med": "Median: {val} | 75th: {val2}",
        "tooltip_launchpad": "Avg before prev PB: {val}",
        "tooltip_recent": "Recent Avg:    {val}",
        
        # Session Report
        "rep_title": "Session Report - {date}",
        "rep_duration": "Total Duration",
        "rep_active": "Active Playtime",
        "rep_density": "Play Density",
        "rep_plays": "Total Plays",
        "rep_pbs": "Total PBs",
        "rep_browse": "Browse History...",
        "rep_refresh": "Refresh (F5)",
        "rep_summarize": "Summarize by Scenario",
        "rep_sort": "Sort by:",
        "rep_graph_title": "Session Performance Flow",
        
        "sec_played": "Scenarios Played ({count})",
        "sec_pbs": "Personal Bests ({count})",
        "sec_avgs": "Average Score Comparison ({count})",
        "sec_ranks": "Rank Achieved",
        
        "sort_perf": "Performance",
        "sort_count": "Play Count",
        "sort_order": "Order Played",
        "sort_alpha": "Alphabetical",
        
        "lbl_session": "Session: {val} ({count} runs)",
        "lbl_alltime": "All-Time: {val} ({count} runs)",
        "lbl_new_pb": "New PB: {new} (vs. {old})",
        
        # Graph Window
        "graph_view_mode": "View Mode:",
        "graph_raw": "Raw Data",
        "graph_daily": "Daily Avg",
        "graph_weekly": "Weekly Avg",
        "graph_monthly": "Monthly Avg",
        "graph_session": "Session Avg",
        "graph_grouped": "Grouped Avg", # NEW
        "graph_hide_count": "Hide Count <=",
        
        "graph_hide_low": "Hide scores below:",
        "graph_connect": "Connect Sessions",
        "graph_4color": "4-Color Cycle",
        "graph_color_sens": "Color by Sens", # NEW
        "graph_group_size": "Group Size (N=)", # NEW
        
        # Misc
        "restart_msg": "Please restart the application to apply language changes.",
        "restart_title": "Restart Required",
        "lang_label": "Language:",
    },
    
    "jp": {
        "window_title": "Variant Stats Viewer by iyo & Gemini ({ver})",
        "search_label": "シナリオ検索:",
        "ready_label": "準備完了。フォルダを選択して読み込んでください。",
        "loading_label": "読み込み中...",
        "loaded_label": "計{count}件のスコアを読み込みました。",
        "load_err_label": "読み込み失敗、またはデータがありません。",
        "load_btn": "スコア読み込み",
        "refresh_btn": "更新 (F5)",
        "session_report_btn": "前回のセッションレポート",
        "session_hist_btn": "セッション履歴",
        "select_folder_btn": "フォルダ選択",
        "hint_hide": "(シナリオ/cmを右クリックで非表示)",
        
        "recently_played": "最近プレイしたシナリオ",
        "favorites": "お気に入り",
        "recents": "履歴",
        "compare_by": "比較軸:",
        "filter_format": "フィルタ形式:",
        
        "session_gap": "セッション間隔(分):",
        "req_refresh": "(要再読込)",
        "theme": "テーマ:",
        "show_decimals": "小数表示",
        "manage_hidden": "非表示管理",
        "font_size": "文字サイズ:",
        "cell_h": "セル高さ:",
        
        "sens_filter": "感度フィルタ:",
        "grid_mode": "表示モード:",
        "highlight": "ハイライト:",
        "pb_num": "順位:",
        "target": "目標:",
        
        "opt_all": "全て",
        "opt_5cm": "5cm刻み",
        "opt_10cm": "10cm刻み",
        "opt_custom_step": "カスタム刻み",
        "opt_specific": "指定リスト",
        
        "mode_pb": "自己ベスト",
        "mode_avg": "平均スコア",
        "mode_count": "プレイ回数",
        "mode_percentile": "上位 N%",
        
        "hl_none": "なし",
        "hl_drop": "スコア低下",
        "hl_row_heat": "行ヒートマップ",
        "hl_global_heat": "全体ヒートマップ",
        "hl_target": "目標スコア",
        "hl_recent_success": "最近の達成 (日数)",
        
        "rating": "全体平均: {val}",
        "avg_row": "-- 平均 --",
        "col_avg": "平均",
        "col_best": "ベスト",
        "col_cm": "cm",
        "tooltip_sens": "感度: {val}",
        "tooltip_pb": "PB: {val} ({date})",
        "tooltip_runs": "回数: {val}",
        "tooltip_avg": "平均: {val}",
        "tooltip_med": "中央値: {val} | 75%: {val2}",
        "tooltip_launchpad": "PB更新直前の平均: {val}",
        "tooltip_recent": "直近平均:    {val}",
        
        "rep_title": "セッションレポート - {date}",
        "rep_duration": "総時間",
        "rep_active": "プレイ時間",
        "rep_density": "プレイ密度",
        "rep_plays": "プレイ回数",
        "rep_pbs": "更新数",
        "rep_browse": "履歴を見る...",
        "rep_refresh": "更新 (F5)",
        "rep_summarize": "シナリオ別に集計",
        "rep_sort": "並び替え:",
        "rep_graph_title": "セッションパフォーマンス推移",
        
        "sec_played": "プレイしたシナリオ ({count})",
        "sec_pbs": "自己ベスト更新 ({count})",
        "sec_avgs": "平均スコア比較 ({count})",
        "sec_ranks": "ランク獲得数",
        
        "sort_perf": "パフォーマンス",
        "sort_count": "回数",
        "sort_order": "プレイ順",
        "sort_alpha": "名前順",
        
        "lbl_session": "今回: {val} ({count}回)",
        "lbl_alltime": "通算: {val} ({count}回)",
        "lbl_new_pb": "新記録: {new} (旧: {old})",
        
        "graph_view_mode": "表示モード:",
        "graph_raw": "生データ",
        "graph_daily": "日別平均",
        "graph_weekly": "週別平均",
        "graph_monthly": "月別平均",
        "graph_session": "セッション平均",
        "graph_grouped": "グループ平均", # NEW
        
        "graph_hide_low": "以下のスコアを非表示:",
        "graph_connect": "セッションを繋ぐ",
        "graph_4color": "4色サイクル",
        "graph_color_sens": "感度別カラー", # NEW
        "graph_group_size": "グループサイズ (N=)", # NEW
        
        "restart_msg": "言語変更を適用するには再起動してください。",
        "restart_title": "再起動が必要です",
        "lang_label": "言語:",
    },
    #just these two languages for now
}

def get_text(lang_code, key, **kwargs):
    """
    Retrieves text for the given language code and key.
    Falls back to 'en' if language or key is missing.
    Accepts kwargs for string formatting (e.g., {val}).
    Injects {ver} automatically if not provided.
    """
    # Auto-inject version if not provided
    kwargs.setdefault('ver', APP_VERSION)

    lang_dict = TRANSLATIONS.get(lang_code, TRANSLATIONS["en"])
    text = lang_dict.get(key, TRANSLATIONS["en"].get(key, f"MISSING: {key}"))
    
    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError:
            return text
    return text