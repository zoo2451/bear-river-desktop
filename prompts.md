# Prompt Log

## 2026-11-24

- **Asked:** Plan the Option A port of the Bear River Gage Explorer web app to a Tkinter desktop app.
- **Changed:** Nothing; proposed the file layout, spec sections, three added features (embedded plot with toolbar, CSV/Excel export, save/open session), three validation cases, and the commit sequence.
- **Result:** Succeeded. Bear River Gage Explorer confirmed as the app to port.

- **Asked:** Set up the project and write the first draft of the spec.
- **Changed:** Created `AGENTS.md` with the prompt-log line, a rough first-draft `spec.md` (seven sections plus Platform and Features added), and this `prompts.md`.
- **Result:** Succeeded.

- **Asked:** "Go ahead and make this for me": build the full desktop app in stages, committing each step.
- **Changed (spec revision):** Tested the live USGS Water Data API (monitoring-locations, latest-continuous, daily) and the WBD boundary service, then rewrote `spec.md`: overview; inputs table with units, ranges, defaults, and controls; data-source requests; active-gage rule, mean flow, runoff volume (1.98347 acre-ft per cfs-day), and time-zone rules; outputs; layout; error handling; platform; three added features; three validation cases with specific gages; and 7 build stages. Found 313 stream sites in HUC 1601, about 21 of them active within 7 days, and confirmed that drainage area increases down the main stem (172 → 7029 mi²).
- **Result:** Succeeded. Spec ready to build from.

- **Asked:** Build stage 1 (layout mockup) from the Build stages section of spec.md.
- **Changed:** Created `app.py`: a Tkinter window with a menu bar, a controls bar (active-window spinbox, historical checkbox), a tkintermapview map centered on the basin, a gage list, a selected-gage info panel, an embedded matplotlib hydrograph with placeholder data, a statistics line, and a status bar. First test: the status bar and statistics line were pushed off the window because they were packed after expanding widgets. Fixed by packing them first.
- **Result:** Succeeded after the packing fix. Checked with a screenshot: every area is visible and labeled.

- **Asked:** Build stage 2 (live data on the map) from spec.md.
- **Changed:** Added the data layer to `app.py`: a paged OGC API fetch, the HUC 1601 boundary from WBD, stream sites (`site_type_code=ST`, `hydrologic_unit_code LIKE '1601%'`), latest discharge from `latest-continuous`, and the `is_active` rule. Downloads run in a worker thread with a queue polled by `after()`. Draws the boundary and small dot markers (blue active, gray historical, with a legend); the historical checkbox and active-window spinbox redraw without re-downloading; the gage list sorts by column with active gages on top; File > Reload Live Data; error dialog on download failure.
- **Result:** Succeeded. 21 active gages within 7 days, 292 historical, 313 total. The window stayed responsive during the download. Fixed the sort so active gages stay on top when historical ones are shown.

- **Asked:** Build stage 3 (gage details and hydrograph, first working version) from spec.md.
- **Changed:** Added `fetch_daily` (daily collection, statistic 00003, `time=P365D`) returning a pandas DataFrame, and `flow_stats` (mean, n, peak, minimum, runoff volume = 1.98347 × ΣQ). Clicking a marker or list row highlights it orange, fills the info panel (name, site, state, drainage area, latest flow, reading time in Mountain Time with its age and active/historical status), enables "Open USGS page", and downloads and draws the hydrograph with a mean line, peak marker, and statistics line. Daily data is cached per gage. Added messages for no data, download failure, and ice-affected readings.
- **Result:** Succeeded. Corinne (10126000) shows 1,080 cfs latest, a 364-day hydrograph, and a mean of 796.3 cfs. The historical gage 10099000 shows "No daily data" without crashing; ice-affected 10023000 shows "No value (ice/equipment)". Moved the legend so it no longer covers the peak; old readings show their age in years.
