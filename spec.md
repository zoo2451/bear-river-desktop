# Bear River Gage Explorer (Desktop)

## Overview
A Tkinter desktop app with a map of the Bear River basin (HUC 1601) on the left and a gage panel on the right. When it starts, it downloads the basin boundary, every USGS stream site in the basin, and each site's latest discharge reading. Active gages appear as markers. Clicking one fills the panel with the gage's information and a one-year daily hydrograph. Desktop features add an interactive plot toolbar, CSV/Excel export, and save/open of session files for offline use. All downloads run in a background thread so the window never freezes.

## Purpose
The app shows where USGS stream gages are in the Bear River basin, which drains parts of Utah, Idaho, and Wyoming into the Great Salt Lake, and what each one is recording now and over the past year. It is for hydrology students, water managers, and engineers who want a quick look at basin conditions without visiting each USGS page. It is a desktop port of my Bear River Gage Explorer web app, with features that use what Python does well: file input/output, pandas, and interactive matplotlib plots.

## Inputs
| Input | Unit | Range / rule | Default | Control |
|---|---|---|---|---|
| Selected gage | - | Any marker shown on the map | None selected | Click a map marker, or pick from the gage list |
| Show historical gages | - | On/off | Off | Checkbox |
| Active window | days | 1-30 | 7 | Spinbox |
| Hydrograph period | days | 30-730 | 365 | Dropdown (30, 90, 365, 730) |
| Log-scale flow axis | - | On/off | Off | Checkbox |
| Session file | .json | File written by this app | - | File > Open / Save Session |
| Export file | .csv / .xlsx | Any writable path | - | File > Export |

## Calculations

### Data sources
Every download uses the USGS Water Data API (`https://api.waterdata.usgs.gov/ogcapi/v0`), except the boundary, which comes from the USGS Watershed Boundary Dataset. The retiring waterservices.usgs.gov service is not used.

| Data | Request |
|---|---|
| Basin boundary | `hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/2/query?where=huc4='1601'&f=geojson&outSR=4326` |
| Stream sites | `collections/monitoring-locations/items?site_type_code=ST&filter=hydrologic_unit_code LIKE '1601%'` |
| Latest discharge | `collections/latest-continuous/items?parameter_code=00060&bbox=-112.9,40.6,-110.4,43.1`, kept only for sites in the list above |
| Daily flow | `collections/daily/items?monitoring_location_id=<id>&parameter_code=00060&statistic_id=00003&time=P<N>D` |

Responses are paged. The app follows `next` links until every page is read.

### Rules and equations
- **Active gage:** the latest discharge (parameter 00060) reading time *t*<sub>last</sub> satisfies now − *t*<sub>last</sub> ≤ *W* days, where *W* is the active window. All other stream sites are historical.
- **Mean flow:** *Q̄* = (1/*n*) Σ *Q*<sub>i</sub>, where *Q*<sub>i</sub> is the daily mean discharge (cfs) on day *i* and *n* is the number of days with a value. Days with missing values are skipped, and *n* is reported.
- **Runoff volume:** *V* = Σ *Q*<sub>i</sub> × 86,400 s/day ÷ 43,560 ft²/acre = 1.98347 × Σ *Q*<sub>i</sub>, in acre-ft, where *Q*<sub>i</sub> is in cfs.
- **Peak and minimum:** the largest and smallest *Q*<sub>i</sub> in the period, with their dates.
- **Reading age:** now − *t*<sub>last</sub>, shown in hours or days.
- Times from the API are UTC. They are shown in Mountain Time (America/Denver).

## Outputs
- **Map** (OpenStreetMap tiles): basin boundary outline; active gages as blue markers; historical gages as gray markers (only when the checkbox is on). The selected gage is drawn in a highlight color.
- **Gage list:** a sortable table of the gages shown, with site number, name, and latest flow (cfs).
- **Info panel** for the selected gage:
  - name
  - site number
  - county and state (where USGS locates the gage; this can differ from the town in its name)
  - drainage area (mi²)
  - latest flow (cfs)
  - date and time of the latest reading (MT), with its age
  - an "Open USGS page" button linking to `https://waterdata.usgs.gov/monitoring-location/<site number>/`
- **Hydrograph:** daily mean discharge (cfs) against date for the chosen period, with axis labels and units, a dashed line for *Q̄*, and the peak marked.
- **Statistics:** *Q̄* (cfs), *n* (days), peak (cfs and date), minimum (cfs and date), runoff volume (acre-ft).
- **Status bar:** what is downloading, how many gages are active and historical, and any errors.

## Look and feel
- A single window about 1300 × 800 px that can be resized. The map takes the left ~55%; the right side has the gage list on top, then the info panel, then the hydrograph.
- On opening, the map is zoomed to fit the whole basin, the status bar reads "Downloading…", and the right panel says "Click a gage to see its data." The markers appear when the download finishes.
- Restrained colors (navy, blue, gray); every number shows its units; active/historical status uses both color and text.
- A menu bar with File (Open Session, Save Session, Export Daily Flow, Export Gage Table, Quit) and Help (About).

## Error handling
- No internet or an API timeout (30 s): the status bar shows an error, an error dialog offers File > Open Session, and the app does not crash.
- A gage with no daily data in the period: the plot shows "No daily data for this period" and the statistics show "-".
- A missing latest value (for example, ice-affected): latest flow shows "No value (ice/equipment)".
- A missing drainage area shows "not reported".
- Clicks while a download is running are queued; the hydrograph shows a loading message.
- An invalid or corrupt session file: an error dialog; the current data is kept.

## Platform
- Python 3.10+ desktop app, built with Tkinter and started with `python app.py`. Tested on Windows 11 with Python 3.13.
- Packages: `requests`, `pandas`, `matplotlib`, `tkintermapview`, `openpyxl` (see `requirements.txt`).
- Needs internet for live data and map tiles. An opened session file shows saved data offline (map tiles may be missing).
- Network calls run in a worker thread, and results go back to the Tk main loop through `after()`.

## Features added (not in the web version)
1. **Interactive hydrograph toolbar:** the hydrograph is an embedded matplotlib figure with the navigation toolbar (pan, zoom, home, save as PNG/PDF), plus a log-scale toggle and a period dropdown that redraws the plot.
2. **Export to CSV/Excel:** with pandas, export the selected gage's daily flow (date, cfs) and statistics, or the table of all gages (site, name, drainage area, latest flow, reading time, active), to `.csv` or `.xlsx`.
3. **Save/open session (my own idea):** save every downloaded site, latest reading, boundary, and cached hydrograph to a `.json` file, then reopen it later without internet. This is useful in the field, and it freezes a snapshot of conditions on a date for a report.

## Validation
1. **Reference values (USGS Water Data pages):** for three gages (10126000 Bear River near Corinne, UT; 10092700 Bear River at Idaho-Utah state line; 10011500 Bear River near Utah-Wyoming state line), the app's drainage area must match the USGS page exactly, and its latest flow must match the page's latest value within the time between the two looks.
2. **Hand/Excel calculation:** download one year of daily discharge for 10126000 from USGS Water Data as CSV, compute the mean in Excel with `=AVERAGE()`, and compare it to the app's *Q̄* for the same dates. It must agree within 0.1%.
3. **Property checks:**
   - **(a)** drainage area increases downstream along the Bear River main stem (10011500 → 10020100 → 10039500 → 10068500 → 10092700 → 10126000);
   - **(b)** proportionality: runoff volume equals 1.98347 × *n* × *Q̄* to within rounding.

## Validation results
The agent ran these checks with `python validation/run_validation.py` on 2026-11-24 at 20:54 MST.

**Where the expected values come from:**
- **Case 1:** each gage was requested on its own from the USGS Water Data API, the source behind the waterdata.usgs.gov gage pages, without using the app's code.
- **Case 2:** a year of daily values was downloaded as CSV (`validation/10126000_daily.csv`) and averaged outside the app. The same data is in `validation/10126000_daily.xlsx`, with Excel `=AVERAGE()`, `=COUNT()`, and `=SUM()*86400/43560` formulas.
- **Case 3:** property checks on the app's own values.

| Case | Quantity | Expected | App (actual) | Result |
|---|---|---|---|---|
| 1 | 10126000 drainage area (mi²) | 7,029 | 7,029 | PASS |
| 1 | 10126000 latest flow (cfs) at 2026-11-24 20:30 MST | 1,080 | 1,080 | PASS |
| 1 | 10092700 drainage area (mi²) | 4,884 | 4,884 | PASS |
| 1 | 10092700 latest flow (cfs) at 2026-11-24 19:45 MST | 401 | 401 | PASS |
| 1 | 10011500 drainage area (mi²) | 172 | 172 | PASS |
| 1 | 10011500 latest flow (cfs) at 2026-11-24 20:30 MST | 107 | 107 | PASS |
| 2 | 10126000 days with values, 2025-11-25 to 2026-11-23 | 364 | 364 | PASS |
| 2 | 10126000 mean flow *Q̄* (cfs) | 796.28 | 796.28 | PASS |
| 3a | Main-stem drainage area, upstream → downstream (mi²) | strictly increasing | 172 → 755 → 2,480 → 3,705 → 4,884 → 7,029 | PASS |
| 3b | 10126000 runoff volume = 1.98347 × *n* × *Q̄* (acre-ft) | 574,899 | 574,899 | PASS |

**Hand check (case 2):** *V* = 1.98347 × 364 days × 796.28 cfs = 574,899 acre-ft, which matches the app.

**My own check in the app:** _(fill in)_ I opened the app, clicked 10126000 Bear River near Corinne, and compared it with https://waterdata.usgs.gov/monitoring-location/USGS-10126000/ on Nov 24, 2026: drainage area 7029 mi² vs. app 7029 mi²; latest flow 1080 cfs vs. app 1080 cfs. I also opened `10126000_daily.xlsx` in Excel: `=AVERAGE` gave 796.28 cfs vs. the app's 796.28 cfs.

## Out of scope
- The old waterservices.usgs.gov service.
- Gages outside HUC 1601, and non-stream sites (wells, springs, lakes).
- Parameters other than discharge (no gage height, temperature, or water quality).
- Forecasts, flood frequency analysis, and statistics older than the chosen period.
- Editing or uploading data to USGS.

## Build stages
1. **Layout mockup:** the Tkinter window with the map (basin centered), gage list, info panel, an embedded plot with placeholder data, a status bar, and menus. No downloads. *Check:* the window opens and resizes, and every area is labeled.
2. **Live data on the map:** download the boundary, sites, and latest readings in a background thread; draw the boundary and active markers; the historical checkbox and active-window spinbox; fill the gage list. *Check:* about two dozen active gages appear, the toggle shows ~300, and the window stays responsive while loading.
3. **Gage details and hydrograph (first working version):** clicking a marker or list row fills the info panel, downloads daily flow, and draws the hydrograph with statistics; error handling. *Check:* values look reasonable against USGS pages, and gages with no data do not crash the app.
4. **Validation:** run the validation cases, fill in the Validation results table, and fix any mismatch.
5. **Feature 1:** navigation toolbar, log-scale toggle, period dropdown.
6. **Feature 2:** CSV/Excel export.
7. **Feature 3:** save/open session.
