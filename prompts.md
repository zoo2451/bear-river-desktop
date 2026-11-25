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
