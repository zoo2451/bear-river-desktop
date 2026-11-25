# Bear River Gage Explorer (Desktop)

A Tkinter desktop app that maps the USGS stream gages in the Bear River basin (HUC 1601: Utah, Idaho, and Wyoming). Click a gage to see its drainage area, its latest flow, and a daily hydrograph. This is a desktop port of my web app, with three added features: an interactive plot toolbar, CSV/Excel export, and save/open of session files for offline viewing. See [spec.md](spec.md) for the full specification and validation results.

## Install
1. Install Python 3.10 or newer from https://www.python.org. On Windows, check "Add Python to PATH" and keep "tcl/tk" selected; Tkinter is included.
2. In a terminal, from this folder:
   ```
   python -m pip install -r requirements.txt
   ```

## Run
```
python app.py
```
The app needs an internet connection to download live USGS data and map tiles. Without one, use **File > Open Session** to view a session you saved earlier.

## Use
- **Map:** blue dots are active gages (reported within the active window, 7 days by default); gray dots are historical. Use "Show historical gages" to show all ~300 sites. Scroll to zoom; drag to pan.
- **Select a gage:** click a dot or a row in the gage list. The orange dot is the selected gage. "Open USGS page" opens its page on waterdata.usgs.gov.
- **Hydrograph:** choose a period (30-730 days), switch to a log axis, and use the toolbar to pan, zoom, or save the plot as an image.
- **File menu:**
  - Export Daily Flow saves the selected gage's daily flow and statistics.
  - Export Gage Table saves all sites (`.xlsx` or `.csv`).
  - Save Session / Open Session store everything in a `.json` file for offline use.
  - Reload Live Data downloads fresh data.

## Validation
```
python validation/run_validation.py
```
This compares the app against independent USGS requests and an Excel `=AVERAGE()` check, then writes `validation/validation_results.md`.

## Data
All data comes from the USGS Water Data API (`api.waterdata.usgs.gov/ogcapi/v0`) and the USGS Watershed Boundary Dataset. The retiring waterservices.usgs.gov service is not used. Values marked "Provisional" by USGS may change.
