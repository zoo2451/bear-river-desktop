"""Bear River Gage Explorer - Tkinter desktop app.

Run with:  python app.py
See spec.md for requirements.
"""

import tkinter as tk
from tkinter import ttk

import tkintermapview
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

APP_TITLE = "Bear River Gage Explorer"
BASIN_CENTER = (41.8, -111.6)  # lat, lon


class GageExplorerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1300x800")
        self.minsize(1000, 650)
        self._build_menu()
        self._build_controls()
        self._build_status_bar()  # pack before the expanding layout so it is never squeezed out
        self._build_layout()
        self._show_placeholder()

    # ------------------------------------------------------------------ UI
    def _build_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Open Session...", state="disabled")
        file_menu.add_command(label="Save Session...", state="disabled")
        file_menu.add_separator()
        file_menu.add_command(label="Export Daily Flow...", state="disabled")
        file_menu.add_command(label="Export Gage Table...", state="disabled")
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="About", state="disabled")
        menubar.add_cascade(label="Help", menu=help_menu)
        self.config(menu=menubar)

    def _build_controls(self):
        bar = ttk.Frame(self, padding=(10, 6))
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text=APP_TITLE, font=("Segoe UI", 13, "bold")).pack(side="left")
        ttk.Label(bar, text="  USGS stream gages, HUC 1601 (UT / ID / WY)",
                  foreground="#555").pack(side="left")
        self.show_hist = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Show historical gages",
                        variable=self.show_hist).pack(side="right", padx=6)
        self.active_days = tk.IntVar(value=7)
        ttk.Spinbox(bar, from_=1, to=30, width=4,
                    textvariable=self.active_days).pack(side="right")
        ttk.Label(bar, text="Active window (days):").pack(side="right", padx=(12, 4))

    def _build_layout(self):
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(side="top", fill="both", expand=True)

        # Left: map
        map_frame = ttk.Frame(paned)
        self.map = tkintermapview.TkinterMapView(map_frame, corner_radius=0)
        self.map.pack(fill="both", expand=True)
        self.map.set_position(*BASIN_CENTER)
        self.map.set_zoom(8)
        paned.add(map_frame, weight=55)

        # Right: list, info, plot
        right = ttk.Frame(paned, padding=8)
        paned.add(right, weight=45)

        list_box = ttk.LabelFrame(right, text="Gages", padding=4)
        list_box.pack(fill="x")
        cols = ("site", "name", "flow")
        self.tree = ttk.Treeview(list_box, columns=cols, show="headings", height=6)
        self.tree.heading("site", text="Site number")
        self.tree.heading("name", text="Name")
        self.tree.heading("flow", text="Latest flow (cfs)")
        self.tree.column("site", width=90, anchor="w")
        self.tree.column("name", width=290, anchor="w")
        self.tree.column("flow", width=110, anchor="e")
        sb = ttk.Scrollbar(list_box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="x", expand=True)
        sb.pack(side="right", fill="y")

        info = ttk.LabelFrame(right, text="Selected gage", padding=6)
        info.pack(fill="x", pady=(8, 0))
        self.info_vars = {}
        fields = [("name", "Name"), ("site", "Site number"), ("state", "State"),
                  ("area", "Drainage area"), ("flow", "Latest flow"),
                  ("time", "Latest reading")]
        for r, (key, label) in enumerate(fields):
            ttk.Label(info, text=label + ":", foreground="#555").grid(
                row=r, column=0, sticky="w", padx=(0, 8))
            var = tk.StringVar(value="-")
            ttk.Label(info, textvariable=var).grid(row=r, column=1, sticky="w")
            self.info_vars[key] = var
        self.usgs_btn = ttk.Button(info, text="Open USGS page", state="disabled")
        self.usgs_btn.grid(row=0, column=2, rowspan=2, sticky="ne", padx=(16, 0))
        info.columnconfigure(1, weight=1)

        plot_box = ttk.LabelFrame(right, text="Hydrograph", padding=4)
        plot_box.pack(fill="both", expand=True, pady=(8, 0))
        self.stats_var = tk.StringVar(value="")
        ttk.Label(plot_box, textvariable=self.stats_var, foreground="#333",
                  wraplength=560, justify="left").pack(side="bottom", fill="x", pady=(4, 0))
        self.fig = Figure(figsize=(5, 3), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_box)
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

    def _build_status_bar(self):
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status_var, relief="sunken",
                  anchor="w", padding=(8, 2)).pack(side="bottom", fill="x")

    # ------------------------------------------------------------ mockup
    def _show_placeholder(self):
        """Stage 1 mockup: placeholder values only, no downloads."""
        self.tree.insert("", "end", values=("10126000", "BEAR RIVER NEAR CORINNE, UT", "1,080"))
        self.tree.insert("", "end", values=("10092700", "BEAR RIVER AT IDAHO-UTAH STATE LINE", "401"))
        self.tree.insert("", "end", values=("10011500", "BEAR RIVER NEAR UTAH-WYOMING STATE LINE", "107"))
        for key, val in {"name": "BEAR RIVER NEAR CORINNE, UT (placeholder)",
                         "site": "10126000", "state": "Utah", "area": "7,029 mi²",
                         "flow": "1,080 cfs", "time": "2026-11-24 19:30 MST"}.items():
            self.info_vars[key].set(val)
        import math
        days = list(range(365))
        q = [800 + 2500 * math.exp(-((d - 200) / 30) ** 2) for d in days]
        self.ax.plot(days, q, color="#2f73bd", lw=1.2)
        self.ax.set_xlabel("Day (placeholder)")
        self.ax.set_ylabel("Daily mean discharge (cfs)")
        self.ax.set_title("Placeholder hydrograph", fontsize=10)
        self.ax.grid(alpha=0.3)
        self.fig.tight_layout()
        self.canvas.draw()
        self.stats_var.set("Mean flow: - cfs  |  Peak: - cfs  |  Runoff volume: - acre-ft  (placeholder)")
        self.status_var.set("Mockup - no data downloaded yet")


if __name__ == "__main__":
    GageExplorerApp().mainloop()
