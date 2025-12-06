# Plugins for Graph Lines

class IndicatorBase:
    name = "Base"
    color = "#FFFFFF"
    width = 2
    style = "Solid" # Solid, Dotted, Dashed

    def extract_data(self, processed_session_data):
        """
        Takes the list of dicts output by engine.analyze_session
        Returns a list of {time, value} for TradingView
        """
        return []

# --- IMPLEMENTATIONS ---

class IndScore(IndicatorBase):
    name = "Score"
    color = "#4aa3df" # Light Blue
    width = 2
    def extract_data(self, data):
        return [{'time': d['time'], 'value': d['pct']} for d in data]

class IndTrend(IndicatorBase):
    name = "Session Trend"
    color = "#FF9800" # Orange
    width = 2
    def extract_data(self, data):
        return [{'time': d['time'], 'value': d['trend_pct']} for d in data]

class IndFlow(IndicatorBase):
    name = "Global Flow"
    color = "#9C27B0" # Purple
    width = 2
    def extract_data(self, data):
        return [{'time': d['time'], 'value': d['flow_pct']} for d in data]

class IndPulse(IndicatorBase):
    name = "The Pulse"
    color = "#00E5FF" # Cyan
    width = 1
    def extract_data(self, data):
        return [{'time': d['time'], 'value': d['pulse_pct']} for d in data]

# Registry
AVAILABLE_INDICATORS = [IndTrend, IndFlow, IndPulse]