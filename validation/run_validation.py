"""Run the spec.md validation cases and write validation/validation_results.md.

Run from the project folder:  python validation/run_validation.py

Expected values come from requests that do NOT use the app's code:
  Case 1 - each gage requested by itself from the USGS Water Data API
           (the same data the waterdata.usgs.gov gage page shows).
  Case 2 - daily values downloaded as CSV, averaged with the csv module, and saved
           with an Excel =AVERAGE() formula (10126000_daily.xlsx) to check by hand.
  Case 3 - property checks on the app's own outputs.
Actual values come from the app's functions in app.py.
"""

import csv
import io
import os
import sys
from datetime import datetime, timezone

import requests
from openpyxl import Workbook

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import app  # noqa: E402

OGC = app.OGC
REF_GAGES = ["10126000", "10092700", "10011500"]
MAIN_STEM = ["10011500", "10020100", "10039500", "10068500", "10092700", "10126000"]
EXCEL_GAGE = "10126000"
rows = []  # (case, quantity, expected, actual, pass)


def add(case, qty, expected, actual, ok):
    rows.append((case, qty, expected, actual, "PASS" if ok else "FAIL"))


def ref_site(site):
    r = requests.get(f"{OGC}/monitoring-locations/items/USGS-{site}", params={"f": "json"}, timeout=30)
    r.raise_for_status()
    return r.json()["properties"]


def ref_latest(site):
    r = requests.get(f"{OGC}/latest-continuous/items", timeout=30, params={
        "f": "json", "monitoring_location_id": f"USGS-{site}", "parameter_code": "00060"})
    r.raise_for_status()
    feats = sorted(r.json()["features"], key=lambda f: f["properties"]["time"])
    p = feats[-1]["properties"]
    return app.to_float(p["value"]), app.parse_time(p["time"])


def main():
    now = datetime.now(timezone.utc)
    print("Downloading app data...")
    sites = app.fetch_sites()
    app.fetch_latest(sites)

    # ---- Case 1: reference values for three gages
    for site in REF_GAGES:
        s = sites[f"USGS-{site}"]
        ref = ref_site(site)
        add(1, f"{site} drainage area (mi²)", ref["drainage_area"], s["drainage_area"],
            ref["drainage_area"] == s["drainage_area"])
        q_ref, t_ref = ref_latest(site)
        add(1, f"{site} latest flow (cfs) at {t_ref.astimezone(app.MOUNTAIN):%Y-%m-%d %H:%M %Z}",
            q_ref, s["latest_value"], t_ref == s["latest_time"] and q_ref == s["latest_value"])

    # ---- Case 2: mean annual flow vs. CSV/Excel
    df = app.fetch_daily(f"USGS-{EXCEL_GAGE}", 365)
    st = app.flow_stats(df)
    r = requests.get(f"{OGC}/daily/items", timeout=60, params={
        "f": "csv", "limit": 1000, "monitoring_location_id": f"USGS-{EXCEL_GAGE}",
        "parameter_code": "00060", "statistic_id": "00003", "time": "P365D"})
    r.raise_for_status()
    recs = sorted(csv.DictReader(io.StringIO(r.text)), key=lambda d: d["time"])
    csv_path = os.path.join(HERE, f"{EXCEL_GAGE}_daily.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "flow_cfs"])
        for d in recs:
            w.writerow([d["time"], d["value"]])
    vals = [float(d["value"]) for d in recs if d["value"] not in ("", None)]
    ref_mean = sum(vals) / len(vals)
    wb = Workbook()
    ws = wb.active
    ws.title = f"USGS-{EXCEL_GAGE}"
    ws.append(["date", "flow_cfs"])
    for d in recs:
        ws.append([d["time"], float(d["value"]) if d["value"] else None])
    n = len(recs) + 1
    ws["D1"], ws["E1"] = "Mean flow (cfs)", f"=AVERAGE(B2:B{n})"
    ws["D2"], ws["E2"] = "Days with values", f"=COUNT(B2:B{n})"
    ws["D3"], ws["E3"] = "Runoff volume (acre-ft)", f"=SUM(B2:B{n})*86400/43560"
    ws["D5"] = f"Downloaded {now:%Y-%m-%d %H:%M} UTC from api.waterdata.usgs.gov (daily, 00060, 00003, P365D)"
    wb.save(os.path.join(HERE, f"{EXCEL_GAGE}_daily.xlsx"))
    add(2, f"{EXCEL_GAGE} days with values, {recs[0]['time']} to {recs[-1]['time']}",
        len(vals), st["n"], len(vals) == st["n"])
    add(2, f"{EXCEL_GAGE} mean flow (cfs)", round(ref_mean, 2), round(st["mean"], 2),
        abs(ref_mean - st["mean"]) <= 0.001 * ref_mean)

    # ---- Case 3a: drainage area increases downstream along the main stem
    areas = [sites[f"USGS-{g}"]["drainage_area"] for g in MAIN_STEM]
    add("3a", "Main-stem drainage area increases downstream (mi²)",
        "strictly increasing", " → ".join(f"{a:,.0f}" for a in areas),
        all(b > a for a, b in zip(areas, areas[1:])))
    # ---- Case 3b: runoff volume = 1.98347 × n × mean
    expect_v = 1.98347 * st["n"] * st["mean"]
    add("3b", f"{EXCEL_GAGE} runoff volume (acre-ft) = 1.98347 × n × Q̄",
        round(expect_v), round(st["volume_af"]), abs(expect_v - st["volume_af"]) <= 1e-4 * expect_v)

    lines = [f"Run {now.astimezone(app.MOUNTAIN):%Y-%m-%d %H:%M %Z}", "",
             "| Case | Quantity | Expected | App (actual) | Result |", "|---|---|---|---|---|"]
    lines += [f"| {c} | {q} | {e} | {a} | {p} |" for c, q, e, a, p in rows]
    out = "\n".join(lines)
    with open(os.path.join(HERE, "validation_results.md"), "w", encoding="utf-8") as fh:
        fh.write(out + "\n")
    print(out)
    print(f"\n{sum(r[4] == 'PASS' for r in rows)}/{len(rows)} checks passed")


if __name__ == "__main__":
    main()
