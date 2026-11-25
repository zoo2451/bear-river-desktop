"""Bear River Gage Explorer - Tkinter desktop app.

Run with:  python app.py
See spec.md for requirements.
"""

import math
import os
import queue
import threading
import tkinter as tk
from datetime import datetime, timezone
from tkinter import filedialog, messagebox, ttk
from zoneinfo import ZoneInfo

import webbrowser

import matplotlib.dates as mdates
import pandas as pd
import requests
import tkintermapview
from PIL import Image, ImageDraw, ImageTk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

APP_TITLE = "Bear River Gage Explorer"
BASIN_CENTER = (41.8, -111.6)  # lat, lon
MOUNTAIN = ZoneInfo("America/Denver")
TIMEOUT_S = 30
PERIOD_CHOICES = (30, 90, 365, 730)  # hydrograph period options (days)

# ---------------------------------------------------------------- data sources
OGC = "https://api.waterdata.usgs.gov/ogcapi/v0/collections"
WBD_URL = "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/2/query"
BASIN_BBOX = "-112.9,40.6,-110.4,43.1"  # lon/lat box that encloses HUC 1601
STATE_NAMES = {"16": "Idaho", "49": "Utah", "56": "Wyoming"}


def fetch_features(url, params):
    """GET an OGC API collection, following 'next' links until every page is read."""
    features = []
    params = dict(params)
    while url:
        r = requests.get(url, params=params, timeout=TIMEOUT_S)
        r.raise_for_status()
        data = r.json()
        features.extend(data.get("features", []))
        url = next((ln["href"] for ln in data.get("links", []) if ln.get("rel") == "next"), None)
        params = None  # the next link already holds the query string
    return features


def fetch_boundary():
    """HUC 1601 boundary as a list of rings, each a list of (lat, lon)."""
    params = {"where": "huc4='1601'", "outFields": "huc4,name", "f": "geojson",
              "outSR": "4326", "maxAllowableOffset": "0.003"}
    r = requests.get(WBD_URL, params=params, timeout=TIMEOUT_S)
    r.raise_for_status()
    geom = r.json()["features"][0]["geometry"]
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    return [[(lat, lon) for lon, lat in poly[0]] for poly in polys]  # outer rings only


def fetch_sites():
    """Every USGS stream site in HUC 1601, as a dict keyed by monitoring location id."""
    feats = fetch_features(f"{OGC}/monitoring-locations/items", {
        "f": "json", "limit": 1000, "site_type_code": "ST",
        "filter": "hydrologic_unit_code LIKE '1601%'", "filter-lang": "cql-text"})
    sites = {}
    for f in feats:
        p, g = f["properties"], f.get("geometry")
        if not g:
            continue
        lon, lat = g["coordinates"][:2]
        sites[f["id"]] = {
            "id": f["id"],
            "site": p.get("monitoring_location_number") or f["id"].split("-", 1)[-1],
            "name": p.get("monitoring_location_name") or "",
            "state": STATE_NAMES.get(p.get("state_code"), p.get("state_name") or ""),
            "county": p.get("county_name") or "",
            "drainage_area": p.get("drainage_area"),
            "lat": lat, "lon": lon,
            "latest_value": None, "latest_time": None,
        }
    return sites


def fetch_latest(sites):
    """Attach the latest discharge (00060) reading to each site in place."""
    feats = fetch_features(f"{OGC}/latest-continuous/items", {
        "f": "json", "limit": 1000, "parameter_code": "00060",
        "bbox": BASIN_BBOX, "skipGeometry": "true"})
    for f in feats:
        p = f["properties"]
        s = sites.get(p.get("monitoring_location_id"))
        if s is None or not p.get("time"):
            continue
        t = parse_time(p["time"])
        if s["latest_time"] is None or t > s["latest_time"]:  # keep the newest series
            s["latest_time"] = t
            s["latest_value"] = to_float(p.get("value"))


def fetch_daily(site_id, days):
    """Daily mean discharge (00060, statistic 00003) for the last `days` days.

    Returns a DataFrame with columns date (datetime64) and flow_cfs (float, NaN if missing).
    """
    feats = fetch_features(f"{OGC}/daily/items", {
        "f": "json", "limit": 1000, "monitoring_location_id": site_id,
        "parameter_code": "00060", "statistic_id": "00003",
        "time": f"P{int(days)}D", "skipGeometry": "true"})
    rows = {}
    for f in feats:
        p = f["properties"]
        if p.get("time"):
            # one value per day; if several time series exist keep the first non-missing
            q = to_float(p.get("value"))
            if rows.get(p["time"]) is None:
                rows[p["time"]] = q
    df = pd.DataFrame({"date": pd.to_datetime(list(rows.keys())),
                       "flow_cfs": pd.to_numeric(list(rows.values()), errors="coerce")})
    return df.sort_values("date").reset_index(drop=True)


CFS_DAY_TO_ACRE_FT = 86400 / 43560  # 1.98347 acre-ft per cfs-day


def flow_stats(df):
    """Spec equations: mean flow, n, peak, minimum, and runoff volume (acre-ft)."""
    q = df["flow_cfs"].dropna()
    if q.empty:
        return None
    d = df.loc[q.index, "date"]
    return {
        "n": int(q.size),
        "mean": float(q.sum() / q.size),
        "peak": float(q.max()), "peak_date": d[q.idxmax()],
        "min": float(q.min()), "min_date": d[q.idxmin()],
        "volume_af": float(q.sum() * CFS_DAY_TO_ACRE_FT),
        "start": df["date"].iloc[0], "end": df["date"].iloc[-1],
    }


# ------------------------------------------------------- export (feature 2)
def daily_export_tables(site, df, days):
    """Daily flow table and a one-row-per-statistic summary for one gage."""
    daily = pd.DataFrame({"date": df["date"].dt.date, "flow_cfs": df["flow_cfs"]})
    st = flow_stats(df)
    rows = [("Site number", site["site"], ""), ("Name", site["name"], ""),
            ("Drainage area", site["drainage_area"], "mi²"), ("Period requested", days, "days")]
    if st:
        rows += [("Start date", f"{st['start']:%Y-%m-%d}", ""), ("End date", f"{st['end']:%Y-%m-%d}", ""),
                 ("Days with values (n)", st["n"], "days"), ("Mean flow", round(st["mean"], 3), "cfs"),
                 ("Peak flow", st["peak"], "cfs"), ("Peak date", f"{st['peak_date']:%Y-%m-%d}", ""),
                 ("Minimum flow", st["min"], "cfs"), ("Minimum date", f"{st['min_date']:%Y-%m-%d}", ""),
                 ("Runoff volume", round(st["volume_af"], 1), "acre-ft")]
    rows.append(("Source", "USGS Water Data API, daily mean discharge (00060, 00003)", ""))
    return daily, pd.DataFrame(rows, columns=["statistic", "value", "unit"])


def gage_table(sites):
    """Table of every stream site with its latest reading and status."""
    rows = []
    for s in sites.values():
        t = s.get("latest_time")
        rows.append({
            "site_number": s["site"], "name": s["name"], "county": s.get("county", ""), "state": s["state"],
            "latitude": s["lat"], "longitude": s["lon"],
            "drainage_area_mi2": s["drainage_area"],
            "latest_flow_cfs": s["latest_value"],
            "latest_reading_MT": t.astimezone(MOUNTAIN).strftime("%Y-%m-%d %H:%M") if t else None,
            "status": "active" if s.get("active") else "historical",
            "usgs_page": usgs_page(s["site"]),
        })
    df = pd.DataFrame(rows)
    return df.sort_values(["status", "name"]).reset_index(drop=True) if not df.empty else df


def write_tables(path, tables):
    """Write {sheet name: DataFrame}. .xlsx gets one sheet each; .csv gets the first table
    in `path` and any others in `<path stem>_<sheet>.csv`. Returns the files written."""
    root, ext = os.path.splitext(path)
    if ext.lower() == ".xlsx":
        with pd.ExcelWriter(path, engine="openpyxl") as xw:
            for name, df in tables.items():
                df.to_excel(xw, sheet_name=name[:31], index=False)
        return [path]
    written = []
    for i, (name, df) in enumerate(tables.items()):
        p = path if i == 0 else f"{root}_{name.lower().replace(' ', '_')}.csv"
        df.to_csv(p, index=False, encoding="utf-8-sig")  # BOM so Excel shows mi² correctly
        written.append(p)
    return written


def parse_time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def to_float(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def is_active(site, now, window_days):
    """Spec rule: active if the latest discharge reading is within the active window."""
    t = site.get("latest_time")
    return t is not None and (now - t).total_seconds() <= window_days * 86400


# --------------------------------------------------------------- formatting
def fmt_flow(q):
    if q is None:
        return "No value"
    return f"{q:,.0f}" if q >= 100 else f"{q:,.3g}"


def fmt_age(seconds):
    hours = seconds / 3600
    if hours < 48:
        return f"{hours:.1f} hours ago"
    days = hours / 24
    return f"{days:.0f} days ago" if days < 730 else f"{days / 365.25:.0f} years ago"


def usgs_page(site_number):
    return f"https://waterdata.usgs.gov/monitoring-location/USGS-{site_number}/"


def dot_icon(fill, outline, size=14):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((1, 1, size - 2, size - 2), fill=fill, outline=outline, width=2)
    return ImageTk.PhotoImage(img)


# ======================================================================= app
class GageExplorerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1300x800")
        self.minsize(1000, 650)
        self.sites = {}          # id -> site dict
        self.boundary = []       # list of rings of (lat, lon)
        self.markers = []
        self.polygons = []
        self.jobs = queue.Queue()  # results from worker threads
        self.icons = {
            "active": dot_icon("#2f73bd", "#12345e"),
            "hist": dot_icon("#b8bec8", "#6b7280", 11),
            "selected": dot_icon("#f08a24", "#7a3d00", 18),
        }
        self.marker_by_id = {}
        self.selected = None
        self.period_days = 365
        self.daily_cache = {}    # (site id, days) -> DataFrame
        self._build_menu()
        self._build_controls()
        self._build_status_bar()  # pack before the expanding layout so it is never squeezed out
        self._build_layout()
        self._clear_info()
        self.after(100, self._poll_jobs)
        self.after(200, self.load_live_data)

    # ------------------------------------------------------------------ UI
    def _build_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Open Session...", state="disabled")
        file_menu.add_command(label="Save Session...", state="disabled")
        file_menu.add_separator()
        file_menu.add_command(label="Export Daily Flow...", command=self.export_daily)
        file_menu.add_command(label="Export Gage Table...", command=self.export_gage_table)
        file_menu.add_separator()
        file_menu.add_command(label="Reload Live Data", command=self.load_live_data)
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
        ttk.Checkbutton(bar, text="Show historical gages", variable=self.show_hist,
                        command=self.refresh_gages).pack(side="right", padx=6)
        self.active_days = tk.StringVar(value="7")
        spin = ttk.Spinbox(bar, from_=1, to=30, width=4, textvariable=self.active_days,
                           command=self.refresh_gages)
        spin.bind("<Return>", lambda e: self.refresh_gages())
        spin.bind("<FocusOut>", lambda e: self.refresh_gages())
        spin.pack(side="right")
        ttk.Label(bar, text="Active window (days):").pack(side="right", padx=(12, 4))
        legend = ttk.Frame(bar)
        legend.pack(side="right", padx=12)
        tk.Label(legend, image=self.icons["active"]).pack(side="left")
        ttk.Label(legend, text="Active  ").pack(side="left")
        tk.Label(legend, image=self.icons["hist"]).pack(side="left")
        ttk.Label(legend, text="Historical").pack(side="left")

    def _build_layout(self):
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(side="top", fill="both", expand=True)

        map_frame = ttk.Frame(paned)
        self.map = tkintermapview.TkinterMapView(map_frame, corner_radius=0)
        self.map.pack(fill="both", expand=True)
        self.map.set_position(*BASIN_CENTER)
        self.map.set_zoom(8)
        paned.add(map_frame, weight=55)

        right = ttk.Frame(paned, padding=8)
        paned.add(right, weight=45)

        list_box = ttk.LabelFrame(right, text="Gages", padding=4)
        list_box.pack(fill="x")
        self.tree_cols = {"site": ("Site number", 90, "w"), "name": ("Name", 290, "w"),
                          "flow": ("Latest flow (cfs)", 110, "e")}
        self.tree = ttk.Treeview(list_box, columns=list(self.tree_cols), show="headings",
                                 height=6, selectmode="browse")
        for c, (label, w, anchor) in self.tree_cols.items():
            self.tree.heading(c, text=label, command=lambda c=c: self.sort_tree(c))
            self.tree.column(c, width=w, anchor=anchor)
        self.sort_state = ("name", False)
        sb = ttk.Scrollbar(list_box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="x", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        info = ttk.LabelFrame(right, text="Selected gage", padding=6)
        info.pack(fill="x", pady=(8, 0))
        self.info_vars = {}
        fields = [("name", "Name"), ("site", "Site number"), ("state", "County, state"),
                  ("area", "Drainage area"), ("flow", "Latest flow"),
                  ("time", "Latest reading")]
        for r, (key, label) in enumerate(fields):
            ttk.Label(info, text=label + ":", foreground="#555").grid(
                row=r, column=0, sticky="w", padx=(0, 8))
            var = tk.StringVar(value="-")
            ttk.Label(info, textvariable=var).grid(row=r, column=1, sticky="w")
            self.info_vars[key] = var
        self.usgs_btn = ttk.Button(info, text="Open USGS page", state="disabled",
                                   command=self.open_usgs_page)
        self.usgs_btn.grid(row=0, column=2, rowspan=2, sticky="ne", padx=(16, 0))
        info.columnconfigure(1, weight=1)

        plot_box = ttk.LabelFrame(right, text="Hydrograph", padding=4)
        plot_box.pack(fill="both", expand=True, pady=(8, 0))
        self.stats_var = tk.StringVar(value="")
        ttk.Label(plot_box, textvariable=self.stats_var, foreground="#333",
                  wraplength=560, justify="left").pack(side="bottom", fill="x", pady=(4, 0))
        # Feature 1: plot controls + matplotlib navigation toolbar
        ctrl = ttk.Frame(plot_box)
        ctrl.pack(side="top", fill="x", pady=(0, 4))
        ttk.Label(ctrl, text="Period:").pack(side="left")
        self.period_var = tk.StringVar(value="365 days")
        period = ttk.Combobox(ctrl, textvariable=self.period_var, width=10, state="readonly",
                              values=[f"{d} days" for d in PERIOD_CHOICES])
        period.pack(side="left", padx=(4, 14))
        period.bind("<<ComboboxSelected>>", self.on_period_change)
        self.log_scale = tk.BooleanVar(value=False)
        ttk.Checkbutton(ctrl, text="Log-scale flow axis", variable=self.log_scale,
                        command=self.redraw_selected).pack(side="left")
        self.fig = Figure(figsize=(5, 3), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_box)
        self.toolbar = NavigationToolbar2Tk(self.canvas, plot_box, pack_toolbar=False)
        self.toolbar.pack(side="bottom", fill="x")
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

    def _build_status_bar(self):
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status_var, relief="sunken",
                  anchor="w", padding=(8, 2)).pack(side="bottom", fill="x")

    def _clear_info(self):
        for v in self.info_vars.values():
            v.set("-")
        self.info_vars["name"].set("Click a gage to see its data.")
        self.ax.clear()
        self.ax.text(0.5, 0.5, "Click a gage to see its hydrograph", ha="center",
                     va="center", transform=self.ax.transAxes, color="#777")
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.canvas.draw_idle()
        self.stats_var.set("")

    # ------------------------------------------------------- background work
    def run_in_background(self, func, on_done, on_error):
        """Run func() in a worker thread; deliver its result on the Tk main loop."""
        def worker():
            try:
                self.jobs.put((on_done, func()))
            except Exception as exc:  # noqa: BLE001 - report every failure to the user
                self.jobs.put((on_error, exc))
        threading.Thread(target=worker, daemon=True).start()

    def _poll_jobs(self):
        try:
            while True:
                callback, value = self.jobs.get_nowait()
                callback(value)
        except queue.Empty:
            pass
        self.after(100, self._poll_jobs)

    # ------------------------------------------------------------ live data
    def load_live_data(self):
        self.status_var.set("Downloading basin boundary, stream sites, and latest readings...")

        def work():
            boundary = fetch_boundary()
            sites = fetch_sites()
            fetch_latest(sites)
            return boundary, sites

        self.run_in_background(work, self._on_live_data, self._on_live_error)

    def _on_live_data(self, result):
        self.boundary, self.sites = result
        self.loaded_at = datetime.now(timezone.utc)
        self.draw_boundary()
        self.refresh_gages()

    def _on_live_error(self, exc):
        self.status_var.set(f"Download failed: {exc}")
        messagebox.showerror(APP_TITLE, "Could not download data from USGS.\n\n"
                             f"{exc}\n\nCheck your internet connection and use "
                             "File > Reload Live Data.")

    def window_days(self):
        try:
            return min(30, max(1, int(float(self.active_days.get()))))
        except ValueError:
            return 7

    def draw_boundary(self):
        for p in self.polygons:
            p.delete()
        self.polygons = [self.map.set_polygon(ring, outline_color="#1d3557", fill_color=None,
                                              border_width=2, name="HUC 1601")
                         for ring in self.boundary]
        lats = [lat for ring in self.boundary for lat, _ in ring]
        lons = [lon for ring in self.boundary for _, lon in ring]
        if lats:
            self.map.fit_bounding_box((max(lats), min(lons)), (min(lats), max(lons)))

    def refresh_gages(self):
        """Classify active/historical, redraw markers, and refill the gage list."""
        if not self.sites:
            return
        w = self.window_days()
        self.active_days.set(str(w))
        now = datetime.now(timezone.utc)
        for s in self.sites.values():
            s["active"] = is_active(s, now, w)
        shown = [s for s in self.sites.values() if s["active"] or self.show_hist.get()]
        for m in self.markers:
            m.delete()
        self.markers = []
        self.marker_by_id = {}
        # historical first so active markers are drawn on top; selected last
        for s in sorted(shown, key=lambda s: (s["id"] == self.selected, s["active"])):
            m = self.map.set_marker(s["lat"], s["lon"], icon=self.icon_for(s), data=s["id"],
                                    command=self.on_marker_click)
            self.markers.append(m)
            self.marker_by_id[s["id"]] = m
        self.tree.delete(*self.tree.get_children())
        for s in shown:
            flow = fmt_flow(s["latest_value"]) if s["active"] else "historical"
            self.tree.insert("", "end", iid=s["id"], values=(s["site"], s["name"], flow))
        self.sort_tree(self.sort_state[0], keep=True)
        if self.selected in self.marker_by_id:
            self.tree.selection_set(self.selected)
            self.tree.see(self.selected)
        n_act = sum(s["active"] for s in self.sites.values())
        self.status_var.set(f"{n_act} active gages (reported within {w} days), "
                            f"{len(self.sites) - n_act} historical, {len(self.sites)} stream sites "
                            f"in HUC 1601. Showing {len(shown)}.")

    def sort_tree(self, col, keep=False):
        prev_col, rev = self.sort_state
        rev = rev if keep else (not rev if col == prev_col else False)
        self.sort_state = (col, rev)

        def key(iid):
            s = self.sites[iid]
            if col == "flow":
                return s["latest_value"] if s["active"] and s["latest_value"] is not None else -1.0
            return s["site"] if col == "site" else s["name"]
        items = sorted(self.tree.get_children(), key=key, reverse=rev)
        items.sort(key=lambda iid: not self.sites[iid]["active"])  # stable: active gages stay on top
        for i, iid in enumerate(items):
            self.tree.move(iid, "", i)

    # ------------------------------------------------------------ selection
    def icon_for(self, s):
        if s["id"] == self.selected:
            return self.icons["selected"]
        return self.icons["active" if s.get("active") else "hist"]

    def on_marker_click(self, marker):
        self.select_site(marker.data)

    def on_tree_select(self, _event=None):
        sel = self.tree.selection()
        if sel and sel[0] != self.selected:
            self.select_site(sel[0])

    def select_site(self, site_id):
        old, self.selected = self.selected, site_id
        for sid in (old, site_id):
            if sid in self.marker_by_id:
                self.marker_by_id[sid].change_icon(self.icon_for(self.sites[sid]))
        if site_id in self.marker_by_id:  # keep the highlighted marker on top
            self.map.canvas.tag_raise(self.marker_by_id[site_id].canvas_icon)
        if self.tree.exists(site_id) and self.tree.selection() != (site_id,):
            self.tree.selection_set(site_id)
            self.tree.see(site_id)
        self.show_info(self.sites[site_id])
        self.load_hydrograph(site_id)

    def show_info(self, s):
        v = self.info_vars
        v["name"].set(s["name"])
        v["site"].set(s["site"])
        v["state"].set(", ".join(x for x in (s.get("county"), s["state"]) if x) or "-")
        da = s["drainage_area"]
        v["area"].set(f"{da:,.1f} mi²" if da is not None else "not reported")
        t = s["latest_time"]
        if t is None:
            v["flow"].set("No discharge reading on record")
            v["time"].set("-")
        else:
            q = s["latest_value"]
            v["flow"].set(f"{fmt_flow(q)} cfs" if q is not None
                          else "No value (ice/equipment)")
            age = (datetime.now(timezone.utc) - t).total_seconds()
            status = "active" if s.get("active") else "historical"
            v["time"].set(f"{t.astimezone(MOUNTAIN):%Y-%m-%d %H:%M %Z}  ({fmt_age(age)}, {status})")
        self.usgs_btn.configure(state="normal")

    def open_usgs_page(self):
        if self.selected:
            webbrowser.open(usgs_page(self.sites[self.selected]["site"]))

    # ----------------------------------------------------------- hydrograph
    def load_hydrograph(self, site_id):
        key = (site_id, self.period_days)
        if key in self.daily_cache:
            self.draw_hydrograph(site_id)
            return
        self.ax.clear()
        self.ax.text(0.5, 0.5, "Downloading daily flow...", ha="center", va="center",
                     transform=self.ax.transAxes, color="#777")
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.canvas.draw_idle()
        self.stats_var.set("")
        self.status_var.set(f"Downloading {self.period_days} days of daily flow for "
                            f"{self.sites[site_id]['site']}...")

        def done(df):
            self.daily_cache[key] = df
            self.status_var.set(f"Loaded {len(df)} daily values for {self.sites[site_id]['site']}.")
            if self.selected == site_id:
                self.draw_hydrograph(site_id)

        def failed(exc):
            self.status_var.set(f"Daily flow download failed: {exc}")
            if self.selected == site_id:
                self.plot_message("Could not download daily flow.\nCheck your connection.")

        self.run_in_background(lambda: fetch_daily(site_id, self.period_days), done, failed)

    # ------------------------------------------------------- export (feature 2)
    EXPORT_TYPES = [("Excel workbook", "*.xlsx"), ("CSV file", "*.csv")]

    def export_daily(self):
        df = self.daily_cache.get((self.selected, self.period_days)) if self.selected else None
        if df is None or df.empty:
            messagebox.showinfo(APP_TITLE, "Select a gage with daily data first.")
            return
        s = self.sites[self.selected]
        path = filedialog.asksaveasfilename(
            title="Export daily flow", defaultextension=".xlsx", filetypes=self.EXPORT_TYPES,
            initialfile=f"{s['site']}_daily_flow_{self.period_days}d.xlsx")
        if path:
            daily, summary = daily_export_tables(s, df, self.period_days)
            self._write(path, {"Daily flow": daily, "Summary": summary})

    def export_gage_table(self):
        if not self.sites:
            messagebox.showinfo(APP_TITLE, "No gage data loaded yet.")
            return
        path = filedialog.asksaveasfilename(
            title="Export gage table", defaultextension=".xlsx", filetypes=self.EXPORT_TYPES,
            initialfile="bear_river_gages.xlsx")
        if path:
            self._write(path, {"Gages": gage_table(self.sites)})

    def _write(self, path, tables):
        try:
            files = write_tables(path, tables)
        except (OSError, ValueError) as exc:  # e.g. file open in Excel
            messagebox.showerror(APP_TITLE, f"Could not write the file:\n{exc}")
            return
        self.status_var.set("Exported " + ", ".join(os.path.basename(f) for f in files))

    def on_period_change(self, _event=None):
        self.period_days = int(self.period_var.get().split()[0])
        if self.selected:
            self.load_hydrograph(self.selected)

    def redraw_selected(self):
        if self.selected and (self.selected, self.period_days) in self.daily_cache:
            self.draw_hydrograph(self.selected)

    def plot_message(self, text):
        self.ax.clear()
        self.ax.text(0.5, 0.5, text, ha="center", va="center",
                     transform=self.ax.transAxes, color="#777")
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.canvas.draw_idle()
        self.stats_var.set("Mean flow: -  |  Peak: -  |  Minimum: -  |  Runoff volume: -")

    def draw_hydrograph(self, site_id):
        s = self.sites[site_id]
        df = self.daily_cache.get((site_id, self.period_days))
        stats = flow_stats(df) if df is not None else None
        if stats is None:
            self.plot_message(f"No daily data for the last {self.period_days} days.")
            return
        ax = self.ax
        ax.clear()
        ax.plot(df["date"], df["flow_cfs"], color="#2f73bd", lw=1.3, label="Daily mean flow")
        ax.axhline(stats["mean"], color="#1d3557", ls="--", lw=1,
                   label=f"Mean = {stats['mean']:,.1f} cfs")
        ax.plot(stats["peak_date"], stats["peak"], "o", color="#f08a24",
                label=f"Peak = {stats['peak']:,.0f} cfs")
        ax.set_ylabel("Daily mean discharge (cfs)")
        ax.set_xlabel("Date")
        ax.set_title(f"{s['site']}  {s['name']}", fontsize=9)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
        ax.grid(alpha=0.3)
        if self.log_scale.get():
            ax.set_yscale("log", nonpositive="mask")  # zero-flow days cannot be shown on a log axis
        ax.legend(fontsize=8, loc="best", framealpha=0.85)
        ax.margins(y=0.12)
        self.fig.tight_layout()
        self.canvas.draw_idle()
        self.toolbar.update()  # reset the toolbar's Home view to this plot
        self.stats_var.set(
            f"{stats['start']:%Y-%m-%d} to {stats['end']:%Y-%m-%d}:  "
            f"Mean flow {stats['mean']:,.1f} cfs (n = {stats['n']} days)  |  "
            f"Peak {stats['peak']:,.0f} cfs on {stats['peak_date']:%Y-%m-%d}  |  "
            f"Minimum {stats['min']:,.1f} cfs on {stats['min_date']:%Y-%m-%d}  |  "
            f"Runoff volume {stats['volume_af']:,.0f} acre-ft")


if __name__ == "__main__":
    GageExplorerApp().mainloop()
