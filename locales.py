# locales.py

# Dictionary of all text used in the app
TRANSLATIONS = {
    "en": {
        # Main UI
        "window_title": "Variant Stats Viewer by iyo & Gemini (v1.22)",
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
        
        "hl_none": "None",
        "hl_drop": "Performance Drop",
        "hl_row_heat": "Row Heatmap",
        "hl_global_heat": "Global Heatmap",
        "hl_target": "Target Score",
        
        # Grid Headers / Tooltips
        "rating": "Rating: {val}",
        "avg_row": "-- Averages --",
        "col_avg": "AVG",
        "col_best": "Best",
        "col_cm": "cm",
        "tooltip_sens": "Sensitivity: {val}",
        "tooltip_pb": "PB: {val} (on {date})",
        "tooltip_runs": "Runs: {val}",
        "tooltip_avg": "Avg: {val}",
        "tooltip_med": "Median: {val} | 75th: {val2}",
        "tooltip_launchpad": "Launchpad Avg: {val}",
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
        "graph_daily": "Daily Average",
        "graph_weekly": "Weekly Average",
        "graph_monthly": "Monthly Average",
        "graph_session": "Session Average",
        
        "graph_hide_low": "Hide scores below:",
        "graph_connect": "Connect Sessions",
        "graph_4color": "4-Color Cycle",
        
        # Misc
        "restart_msg": "Please restart the application to apply language changes.",
        "restart_title": "Restart Required",
        "lang_label": "Language:", # Label for the dropdown itself
    },
    
    "jp": {
        "window_title": "Variant Stats Viewer by iyo & Gemini (バージョン v1.22)",
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
        
        "hl_none": "なし",
        "hl_drop": "スコア低下",
        "hl_row_heat": "行ヒートマップ",
        "hl_global_heat": "全体ヒートマップ",
        "hl_target": "目標スコア",
        
        "rating": "レーティング: {val}",
        "avg_row": "-- 平均 --",
        "col_avg": "平均",
        "col_best": "ベスト",
        "col_cm": "cm",
        "tooltip_sens": "感度: {val}",
        "tooltip_pb": "PB: {val} ({date})",
        "tooltip_runs": "回数: {val}",
        "tooltip_avg": "平均: {val}",
        "tooltip_med": "中央値: {val} | 75%: {val2}",
        "tooltip_launchpad": "PB直前平均: {val}",
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
        "rep_graph_title": "セッション・パフォーマンス推移",
        
        "sec_played": "プレイしたシナリオ ({count})",
        "sec_pbs": "自己ベスト更新 ({count})",
        "sec_avgs": "平均スコア比較 ({count})",
        
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
        
        "graph_hide_low": "以下のスコアを非表示:",
        "graph_connect": "セッションを繋ぐ",
        "graph_4color": "4色サイクル",
        
        "restart_msg": "言語変更を適用するには再起動してください。",
        "restart_title": "再起動が必要です",
        "lang_label": "言語:",
    },

    "pt": {
        "window_title": "Visualizador de Estatísticas KovaaK por iyo & Gemini (v1.22)",
        "search_label": "Buscar Cenário Base:",
        "ready_label": "Pronto. Selecione a pasta e clique em 'Carregar'.",
        "loading_label": "Carregando estatísticas...",
        "loaded_label": "{count} execuções carregadas. Pronto para buscar.",
        "load_err_label": "Falha ao carregar ou sem dados.",
        "load_btn": "Carregar",
        "refresh_btn": "Atualizar (F5)",
        "session_report_btn": "Relatório da Sessão",
        "session_hist_btn": "Histórico de Sessões",
        "select_folder_btn": "Selecionar Pasta",
        
        "recently_played": "Jogado Recentemente",
        "favorites": "Favoritos",
        "recents": "Recentes",
        "compare_by": "Comparar por:",
        "filter_format": "Formato de Filtro:",
        
        "session_gap": "Intervalo (min):",
        "req_refresh": "(Requer Atualização)",
        "theme": "Tema:",
        "show_decimals": "Decimais",
        "manage_hidden": "Gerenciar Ocultos",
        "font_size": "Tamanho Fonte:",
        "cell_h": "Altura Célula:",
        
        "sens_filter": "Filtro Sens:",
        "grid_mode": "Modo Grade:",
        "highlight": "Destaque:",
        "pb_num": "Top #:",
        "target": "Meta:",
        
        "opt_all": "Todos",
        "opt_5cm": "Passo 5cm",
        "opt_10cm": "Passo 10cm",
        "opt_custom_step": "Passo Personalizado",
        "opt_specific": "Lista Específica",
        
        "mode_pb": "Recorde Pessoal",
        "mode_avg": "Média",
        "mode_count": "Contagem",
        
        "hl_none": "Nenhum",
        "hl_drop": "Queda de Desempenho",
        "hl_row_heat": "Mapa de Calor (Linha)",
        "hl_global_heat": "Mapa de Calor (Global)",
        "hl_target": "Meta de Pontuação",
        
        "rating": "Avaliação: {val}",
        "avg_row": "-- Médias --",
        "col_avg": "MÉDIA",
        "col_best": "Melhor",
        "col_cm": "cm",
        "tooltip_sens": "Sensibilidade: {val}",
        "tooltip_pb": "RP: {val} (em {date})",
        "tooltip_runs": "Execuções: {val}",
        "tooltip_avg": "Média: {val}",
        "tooltip_med": "Mediana: {val} | 75%: {val2}",
        "tooltip_launchpad": "Média Pré-RP: {val}",
        "tooltip_recent": "Média Recente: {val}",
        
        "rep_title": "Relatório da Sessão - {date}",
        "rep_duration": "Duração Total",
        "rep_active": "Tempo Ativo",
        "rep_density": "Densidade",
        "rep_plays": "Total Jogos",
        "rep_pbs": "Total RPs",
        "rep_browse": "Histórico...",
        "rep_refresh": "Atualizar (F5)",
        "rep_summarize": "Resumir por Cenário",
        "rep_sort": "Ordenar:",
        "rep_graph_title": "Fluxo de Desempenho",
        
        "sec_played": "Cenários Jogados ({count})",
        "sec_pbs": "Novos Recordes ({count})",
        "sec_avgs": "Comparação de Médias ({count})",
        
        "sort_perf": "Desempenho",
        "sort_count": "Contagem",
        "sort_order": "Ordem Jogado",
        "sort_alpha": "Alfabético",
        
        "lbl_session": "Sessão: {val} ({count} jogos)",
        "lbl_alltime": "Geral: {val} ({count} jogos)",
        "lbl_new_pb": "Novo RP: {new} (vs. {old})",
        
        "graph_view_mode": "Modo de Visualização:",
        "graph_raw": "Dados Brutos",
        "graph_daily": "Média Diária",
        "graph_weekly": "Média Semanal",
        "graph_monthly": "Média Mensal",
        "graph_session": "Média da Sessão",
        
        "graph_hide_low": "Ocultar abaixo de:",
        "graph_connect": "Conectar Sessões",
        "graph_4color": "Ciclo 4 Cores",
        
        "restart_msg": "Por favor, reinicie o aplicativo para aplicar o idioma.",
        "restart_title": "Reinicialização Necessária",
        "lang_label": "Idioma:",
    },

    "cn": {
        "window_title": "Variant Stats Viewer by iyo & Gemini (v1.22)",
        "search_label": "搜索基础场景:",
        "ready_label": "就绪。请选择文件夹并点击“加载统计”。",
        "loading_label": "正在加载统计数据...",
        "loaded_label": "已加载 {count} 条数据。准备搜索。",
        "load_err_label": "加载失败或无数据。",
        "load_btn": "加载统计",
        "refresh_btn": "刷新 (F5)",
        "session_report_btn": "上次会话报告",
        "session_hist_btn": "会话历史",
        "select_folder_btn": "选择文件夹",
        
        "recently_played": "最近游玩",
        "favorites": "收藏",
        "recents": "历史记录",
        "compare_by": "比较方式:",
        "filter_format": "过滤格式:",
        
        "session_gap": "会话间隔(分):",
        "req_refresh": "(需刷新)",
        "theme": "主题:",
        "show_decimals": "显示小数",
        "manage_hidden": "管理隐藏项",
        "font_size": "字体大小:",
        "cell_h": "单元格高:",
        
        "sens_filter": "灵敏度过滤:",
        "grid_mode": "网格模式:",
        "highlight": "高亮显示:",
        "pb_num": "排名:",
        "target": "目标:",
        
        "opt_all": "全部",
        "opt_5cm": "5cm 步进",
        "opt_10cm": "10cm 步进",
        "opt_custom_step": "自定义步进",
        "opt_specific": "特定列表",
        
        "mode_pb": "个人最佳 (PB)",
        "mode_avg": "平均分",
        "mode_count": "游玩次数",
        
        "hl_none": "无",
        "hl_drop": "性能下降",
        "hl_row_heat": "行热力图",
        "hl_global_heat": "全局热力图",
        "hl_target": "目标分数",
        
        "rating": "评分: {val}",
        "avg_row": "-- 平均 --",
        "col_avg": "平均",
        "col_best": "最佳",
        "col_cm": "cm",
        "tooltip_sens": "灵敏度: {val}",
        "tooltip_pb": "PB: {val} ({date})",
        "tooltip_runs": "次数: {val}",
        "tooltip_avg": "平均: {val}",
        "tooltip_med": "中位数: {val} | 75%: {val2}",
        "tooltip_launchpad": "PB前平均: {val}",
        "tooltip_recent": "近期平均: {val}",
        
        "rep_title": "会话报告 - {date}",
        "rep_duration": "总时长",
        "rep_active": "活跃时间",
        "rep_density": "游玩密度",
        "rep_plays": "总次数",
        "rep_pbs": "PB总数",
        "rep_browse": "浏览历史...",
        "rep_refresh": "刷新 (F5)",
        "rep_summarize": "按场景汇总",
        "rep_sort": "排序:",
        "rep_graph_title": "会话性能趋势",
        
        "sec_played": "游玩场景 ({count})",
        "sec_pbs": "新纪录 ({count})",
        "sec_avgs": "平均分对比 ({count})",
        
        "sort_perf": "表现",
        "sort_count": "次数",
        "sort_order": "游玩顺序",
        "sort_alpha": "字母顺序",
        
        "lbl_session": "本次: {val} ({count}次)",
        "lbl_alltime": "历史: {val} ({count}次)",
        "lbl_new_pb": "新PB: {new} (原: {old})",
        
        "graph_view_mode": "视图模式:",
        "graph_raw": "原始数据",
        "graph_daily": "日平均",
        "graph_weekly": "周平均",
        "graph_monthly": "月平均",
        "graph_session": "会话平均",
        
        "graph_hide_low": "隐藏低于:",
        "graph_connect": "连接会话",
        "graph_4color": "4色循环",
        
        "restart_msg": "请重启应用以应用语言更改。",
        "restart_title": "需要重启",
        "lang_label": "语言:",
    }
}

def get_text(lang_code, key, **kwargs):
    """
    Retrieves text for the given language code and key.
    Falls back to 'en' if language or key is missing.
    Accepts kwargs for string formatting (e.g., {val}).
    """
    lang_dict = TRANSLATIONS.get(lang_code, TRANSLATIONS["en"])
    text = lang_dict.get(key, TRANSLATIONS["en"].get(key, f"MISSING: {key}"))
    
    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError:
            return text
    return text