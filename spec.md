# Bear River Gage Explorer (Desktop)

## Purpose
A Tkinter desktop app that maps the USGS stream gages in the Bear River basin (HUC 1601: Utah, Idaho, Wyoming) and shows each gage's information and past-year hydrograph. For hydrology students and water managers. It is a port of my web app with added desktop features.

## Inputs
- Click a gage marker on the map to select it.
- Checkbox: show historical (inactive) gages. Default off.
- (Features) Open/save a session file, export button.

## Calculations
- Download the gages in HUC 1601 and the basin boundary when the app starts.
- A gage is "active" if it has reported discharge (parameter 00060, cfs) recently.
- Mean flow (cfs) = sum of daily mean flows / number of days, over the past year.

## Outputs
- Map with the basin boundary and gage markers (active and historical look different).
- For the selected gage: name, site number, drainage area (mi²), latest flow (cfs), date/time of the latest reading, link to its USGS page.
- Hydrograph of daily flow (cfs) for the past year.

## Look and feel
Map on the left, gage info and hydrograph on the right. Opens showing the whole basin with the active gages.

## Platform
Python 3 desktop app using Tkinter, started with `python app.py`. Needs an internet connection.

## Validation
1. For three gages, compare the latest flow and drainage area to the USGS Water Data pages.
2. Download one year of daily flow for one gage, compute the mean in Excel, and compare it to the app's mean.
3. Property check: drainage area increases going downstream on the Bear River main stem.

## Features added
1. Embedded matplotlib hydrograph with the navigation toolbar (pan, zoom, save as image).
2. Export daily flow and a gage summary table to CSV/Excel with pandas.
3. Save and open a session file so the data can be viewed offline.

## Out of scope
- The old waterservices.usgs.gov service.
- Forecasts, water quality, and gages outside HUC 1601.
