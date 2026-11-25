# Project Agent Guide

Tkinter desktop port of the Bear River Gage Explorer web app (CCE 270, Option A).

- `app.py` - the complete desktop app. Start it with `python app.py`.
- `spec.md` - project requirements and specification. Read it before every build request.
- `prompts.md` - a log of requests and resulting changes.
- `README.md` - how to install and run the app.
- `requirements.txt` - Python packages.
- `validation/` - validation script, downloaded reference data, Excel check, and results.

Keep the app in `app.py`. Do not use the old waterservices.usgs.gov service; use the USGS Water Data API (api.waterdata.usgs.gov).

After each request, add an entry to prompts.md describing what was asked, what changed, and whether it worked.
