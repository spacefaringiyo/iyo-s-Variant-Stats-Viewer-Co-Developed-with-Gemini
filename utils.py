import tkinter
import customtkinter

class Tooltip:
    def __init__(self, widget, text_func, plot_data_func=None, bg="#1e1e1e", fg="#dce4ee", delay=300):
        self.widget = widget
        self.text_func = text_func
        self.plot_data_func = plot_data_func # New: Function to get data for graph
        self.bg = bg
        self.fg = fg
        self.delay = delay
        self.tooltip_window = None
        self.id = None
        self.widget.bind("<Enter>", self.schedule_tip)
        self.widget.bind("<Leave>", self.hide_tip)
        self.widget.bind("<ButtonPress>", self.hide_tip)

    def schedule_tip(self, event=None):
        self.id = self.widget.after(self.delay, self.show_tip)

    def show_tip(self, event=None):
        if self.tooltip_window: return
        
        text = self.text_func()
        if not text: return
        
        # Get Plot Data if available
        plot_points = self.plot_data_func() if self.plot_data_func else None

        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        self.tooltip_window = tkinter.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        # Main Frame
        frame = tkinter.Frame(self.tooltip_window, background=self.bg, relief='solid', borderwidth=1)
        frame.pack()

        # Text Label
        label = tkinter.Label(frame, text=text, justify='left',
                              background=self.bg, foreground=self.fg,
                              font=("Consolas", 10), padx=8, pady=5) # Consolas for alignment
        label.pack(fill="x")

        # --- SPARKLINE DRAWING LOGIC ---
        if plot_points and len(plot_points) > 1:
            self.draw_sparkline(frame, plot_points)
        # -------------------------------

    def draw_sparkline(self, parent, data):
        # Configuration
        width = 220
        height = 60
        padding = 4
        
        canvas = tkinter.Canvas(parent, width=width, height=height, bg=self.bg, highlightthickness=0)
        canvas.pack(padx=5, pady=(0, 5))

        # 1. Normalize Data
        scores = [d['Score'] for d in data]
        min_val = min(scores)
        max_val = max(scores)
        val_range = max_val - min_val if max_val != min_val else 1
        
        num_points = len(scores)
        step_x = (width - 2*padding) / (num_points - 1) if num_points > 1 else 0
        
        def get_y(val):
            norm = 1.0 - ((val - min_val) / val_range)
            return padding + (norm * (height - 2*padding))

        # 2. Calculate Stats
        avg_score = sum(scores) / len(scores)
        
        # Simple percentile calculation without numpy
        sorted_scores = sorted(scores)
        k = (len(sorted_scores) - 1) * 0.75
        f = int(k)
        c = int(k) + 1
        if c < len(sorted_scores):
            p75_score = sorted_scores[f] * (c - k) + sorted_scores[c] * (k - f)
        else:
            p75_score = sorted_scores[f]

        # 3. Draw Reference Lines (Behind the graph)
        # Average (Grey Dash)
        avg_y = get_y(avg_score)
        canvas.create_line(padding, avg_y, width-padding, avg_y, fill="#555555", dash=(2, 2))
        
        # 75th Percentile (Green Dash) - Only if it's visibly different from max/avg
        p75_y = get_y(p75_score)
        if abs(p75_y - avg_y) > 2: # Don't draw if it overlaps heavily with Avg
            canvas.create_line(padding, p75_y, width-padding, p75_y, fill="#4caf50", dash=(2, 2))

        # 4. Calculate Coordinates for Trend
        coords = []
        for i, score in enumerate(scores):
            px = padding + (i * step_x)
            py = get_y(score)
            coords.append((px, py))

        # 5. Draw Trend Line
        line_coords = [c for coord in coords for c in coord]
        canvas.create_line(line_coords, fill="#4aa3df", width=2, smooth=True)

        # 6. Draw Start/End/Peak Dots
        start = coords[0]
        end = coords[-1]
        canvas.create_oval(start[0]-2, start[1]-2, start[0]+2, start[1]+2, fill="#888888", outline="")
        
        max_idx = scores.index(max_val)
        max_pt = coords[max_idx]
        canvas.create_oval(max_pt[0]-2, max_pt[1]-2, max_pt[0]+2, max_pt[1]+2, fill="#ffd700", outline="") # Gold
        
        canvas.create_oval(end[0]-2, end[1]-2, end[0]+2, end[1]+2, fill="#ffffff", outline="")

    def hide_tip(self, event=None):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None