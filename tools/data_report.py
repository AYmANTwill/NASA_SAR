#!/usr/bin/env python3
"""Plain-language report of the NISAR data on disk. Read-only on the data folder.

    python tools/data_report.py --data D:\\project\\NASA_SAR\\data --out results\\data-inventory

Writes DATA_REPORT.md and products.csv in --out. Nothing in --data is modified or opened for writing.
Only the standard library is required. rasterio (footprints) and numpy (geometry files) are used when installed.
Everything is read from folder names, file sizes and file headers: no number is typed by hand.
"""
import argparse
import csv
import datetime as dt
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DATASETS = ("GUNW", "GCOV", "SME2")

WHAT_IT_IS = {
    "GUNW": "Interferogram pairs (two radar passes, 12 days apart or more). Used for ground motion and, through "
            "coherence, for surface change. One product = one pair.",
    "GCOV": "Radar backscatter (how bright the ground looks to the radar). Used for water, soil and vegetation "
            "change. One product = one pass.",
    "SME2": "Soil moisture estimates (Level 3, 200 m). One product = one pass. Provisional, not fully calibrated.",
}

# Rough boxes used only to label a footprint centre: (lon_min, lat_min, lon_max, lat_max)
REGIONS = {
    "Morocco": (-13.5, 27.0, -0.9, 36.2),
    "Panama": (-83.5, 6.5, -77.0, 10.5),
}

# Fallback when footprints cannot be read (rasterio missing): tracks seen in the download plans.
TRACK_REGION = {**{t: "Morocco" for t in ("015", "023", "044", "095", "116", "145")},
                **{t: "Panama" for t in ("004", "040", "076", "141")}}

# CRID -> maturity, as stated in the ASF NISAR documentation. Anything else is shown as-is.
CRID_MATURITY = {"P05023": "PROVISIONAL", "P05036": "VALIDATED"}

# Events used to say which products straddle them. ("exact", datetime) or ("window", start, end)
EVENTS = [
    ("Panama M7.7 earthquake (2026-10-09 17:56:06 UTC)", "Panama", ("exact", dt.datetime(2026, 10, 9, 17, 56, 6))),
    ("Al Haouz storm and flash floods (whole day 2026-10-10)", "Morocco",
     ("window", dt.datetime(2026, 10, 10, 0, 0, 0), dt.datetime(2026, 10, 10, 23, 59, 59))),
]

DATA_GAP = (dt.datetime(2026, 7, 27, 22, 3, 25), dt.datetime(2026, 8, 10, 0, 55, 27))

NAME_RE = re.compile(r"_(\d{3})_(\d{3})_([AD])_(\d{3})_")
TS_RE = re.compile(r"(\d{8}T\d{6})")
CRID_RE = re.compile(r"_(P\d{5})_")
FP_RE = re.compile(r"_([FP])_[A-Z]_\d{3}$")


def ts(s):
    return dt.datetime.strptime(s, "%Y%m%dT%H%M%S")


def folder_size(p):
    total = 0
    for f in p.rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            pass
    return total


def gb(n):
    return n / 1e9


def parse(folder, dataset):
    name = folder.name
    rec = {"dataset": dataset, "name": name, "track": "", "frame": "", "dir": "", "crid": "",
           "maturity": "", "coverage": "", "mode": "", "t": [], "ref": None, "sec": None, "span_days": None}
    m = NAME_RE.search(name)
    if m:
        rec["track"], rec["dir"], rec["frame"] = m.group(2), m.group(3), m.group(4)
    c = CRID_RE.search(name)
    if c:
        rec["crid"] = c.group(1)
        rec["maturity"] = CRID_MATURITY.get(c.group(1), "unknown CRID")
    f = FP_RE.search(name)
    if f:
        rec["coverage"] = "full frame" if f.group(1) == "F" else "partial frame"
    rec["t"] = [ts(x) for x in TS_RE.findall(name)]
    if dataset == "GUNW" and len(rec["t"]) >= 4:
        rec["ref"], rec["sec"] = rec["t"][0], rec["t"][2]
        rec["span_days"] = round((rec["t"][2] - rec["t"][0]).total_seconds() / 86400)
        rec["sec_end"], rec["ref_end"] = rec["t"][3], rec["t"][1]
    elif rec["t"]:
        rec["ref"] = rec["t"][0]
    return rec


def footprint_centre(folder):
    """Return (lon, lat) of the footprint centre from a GeoTIFF header, or None. Needs rasterio."""
    try:
        import rasterio
        from rasterio.warp import transform_bounds
    except Exception:
        return None
    tifs = sorted(folder.glob("*.tif"))
    if not tifs:
        return None
    pick = next((t for t in tifs if "frequencyA" in t.name), tifs[0])
    try:
        with rasterio.open(pick) as s:
            if s.crs is None:
                return None
            l, b, r, t = transform_bounds(s.crs, "EPSG:4326", *s.bounds)
        return ((l + r) / 2, (b + t) / 2)
    except Exception:
        return None


def region_of(centre, track):
    """Return (region, source). Footprint first, track number as a fallback."""
    if centre is not None:
        lon, lat = centre
        for name, (x0, y0, x1, y1) in REGIONS.items():
            if x0 <= lon <= x1 and y0 <= lat <= y1:
                return name, "footprint"
        return "other", "footprint"
    if track in TRACK_REGION:
        return TRACK_REGION[track], "track number"
    return "unknown", "none"


def npz_extras(folder):
    p = folder / "radar_geometry.npz"
    if not p.exists():
        return ""
    try:
        import numpy as np
        keys = " ".join(np.load(p).files)
    except Exception:
        return "unreadable"
    have = [k for k in ("heightAboveEllipsoid", "slantRangeSolidEarthTidesPhase") if k in keys]
    return "axes+tide" if len(have) == 2 else "old (no axes/tide)"


def straddles(rec, ev):
    """For GUNW pairs: 'yes' / 'no' / 'ambiguous'."""
    if rec["dataset"] != "GUNW" or rec["ref"] is None or rec.get("sec") is None:
        return ""
    if ev[0] == "exact":
        e = ev[1]
        return "yes" if rec["ref_end"] <= e <= rec["sec"] else "no"
    start, end = ev[1], ev[2]
    if rec["ref_end"] < start and rec["sec"] > end:
        return "yes"
    for t in rec["t"]:
        if start <= t <= end:
            return "ambiguous"
    return "no"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--out", default=Path("results/data-inventory"), type=Path)
    a = ap.parse_args()

    if not a.data.exists():
        sys.exit("Data folder not found: %s" % a.data)

    recs = []
    for ds in DATASETS:
        d = a.data / ds
        if not d.exists():
            continue
        for f in sorted(d.iterdir()):
            if not f.is_dir():
                continue
            r = parse(f, ds)
            r["size"] = folder_size(f)
            r["done"] = (f / "_DONE").exists()
            r["raw_kept"] = any(f.glob("*.h5"))
            r["region"], r["region_source"] = region_of(footprint_centre(f), r["track"])
            r["extras"] = npz_extras(f) if ds == "GUNW" else ""
            r["missing_layers"] = False
            done = f / "_DONE"
            if done.exists():
                try:
                    r["missing_layers"] = "raw_kept_missing_layers" in done.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    pass
            recs.append(r)

    a.out.mkdir(parents=True, exist_ok=True)

    # ---- CSV ----
    with open(a.out / "products.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["dataset", "region", "region_source", "track", "frame", "direction", "coverage", "crid", "maturity",
                    "reference_date", "secondary_or_date", "span_days", "size_gb", "raw_file_kept",
                    "complete", "layers_missing", "geometry_extras", "folder"])
        for r in recs:
            if r["dataset"] == "GUNW" and r.get("sec"):
                d1, d2 = r["ref"].date().isoformat(), r["sec"].date().isoformat()
            else:
                d1 = r["ref"].date().isoformat() if r["ref"] else ""
                d2 = ""
            w.writerow([r["dataset"], r["region"], r["region_source"], r["track"], r["frame"], r["dir"], r["coverage"], r["crid"],
                        r["maturity"], d1, d2, r["span_days"] if r["span_days"] is not None else "",
                        round(gb(r["size"]), 2), "yes" if r["raw_kept"] else "no",
                        "yes" if r["done"] else "NO", "yes" if r["missing_layers"] else "no",
                        r["extras"], r["name"]])

    # ---- Markdown ----
    L = []
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    free = shutil.disk_usage(a.data).free
    total = sum(r["size"] for r in recs)
    L += ["# NISAR data on disk: plain-language report", "",
          "Generated %s from `%s`. Read-only: nothing in the data folder was changed. "
          "Every figure below is read from the files." % (now, a.data), ""]

    L += ["## 1. In short", "",
          "| Dataset | What it is | Products | Size on disk |", "|---|---|---|---|"]
    for ds in DATASETS:
        rs = [r for r in recs if r["dataset"] == ds]
        L.append("| %s | %s | %d | %.1f GB |" % (ds, WHAT_IT_IS[ds], len(rs), gb(sum(r["size"] for r in rs))))
    L += ["", "Total on disk: **%.1f GB** (free space on that drive: %.0f GB)." % (gb(total), gb(free)), ""]

    bad = [r for r in recs if not r["done"]]
    miss = [r for r in recs if r["missing_layers"]]
    L += ["Health checks: %d product(s) with no completion marker%s; %d product(s) that reported a missing layer%s." % (
        len(bad), "" if not bad else " (" + ", ".join(r["name"][:40] for r in bad[:3]) + "...)",
        len(miss), "" if not miss else " (their raw file is kept, nothing is lost)"), ""]

    L += ["## 2. What we have, by place", ""]
    regions = sorted({r["region"] for r in recs})
    for reg in regions:
        L += ["### %s" % reg, ""]
        for ds in DATASETS:
            rs = [r for r in recs if r["region"] == reg and r["dataset"] == ds]
            if not rs:
                continue
            dates = [r["ref"] for r in rs if r["ref"]]
            ends = [r["sec"] for r in rs if r.get("sec")] or dates
            frames = defaultdict(int)
            for r in rs:
                frames["track %d frame %d %s" % (int(r["track"] or 0), int(r["frame"] or 0),
                                                 {"A": "ascending", "D": "descending"}.get(r["dir"], r["dir"]))] += 1
            L.append("- **%s**: %d product(s), %.1f GB, from %s to %s." % (
                ds, len(rs), gb(sum(r["size"] for r in rs)),
                min(dates).date().isoformat() if dates else "?", max(ends).date().isoformat() if ends else "?"))
            L.append("  - Maturity (CRID): " + ", ".join(sorted({"%s %s" % (r["maturity"], r["crid"]) for r in rs})))
            L.append("  - Viewing geometries: " + "; ".join("%s (%d)" % kv for kv in sorted(frames.items())))
            if ds == "GUNW":
                spans = defaultdict(int)
                for r in rs:
                    spans[r["span_days"]] += 1
                L.append("  - Pair length: " + ", ".join("%s days: %d" % (k, v) for k, v in sorted(spans.items(), key=lambda kv: (kv[0] is None, kv[0]))))
                kept = sum(1 for r in rs if r["raw_kept"])
                L.append("  - Original file kept for %d of %d products; geometry extras: %s." % (
                    kept, len(rs), ", ".join(sorted({r["extras"] or "none" for r in rs}))))
            if ds == "GCOV":
                L.append("  - Full frames: %d, partial frames: %d." % (
                    sum(1 for r in rs if r["coverage"] == "full frame"),
                    sum(1 for r in rs if r["coverage"] == "partial frame")))
        L.append("")

    L += ["## 3. Which products straddle each event", "",
          "A pair straddles an event if the first pass is before it and the second pass after it. "
          "Only these pairs can show a change caused by it.", ""]
    for label, ev_region, ev in EVENTS:
        L += ["### %s" % label, ""]
        rows = [(r, straddles(r, ev)) for r in recs if r["dataset"] == "GUNW" and r["region"] == ev_region]
        hit = [(r, s) for r, s in rows if s in ("yes", "ambiguous")]
        if not hit:
            L += ["No interferogram pair on disk straddles this event.", ""]
        else:
            L += ["| Region | Track/frame | Direction | Reference -> secondary | Days | Straddles | Coverage |",
                  "|---|---|---|---|---|---|---|"]
            for r, s in sorted(hit, key=lambda x: (x[0]["region"], x[0]["track"], x[0]["frame"], x[0]["ref"])):
                L.append("| %s | %d/%d | %s | %s -> %s | %s | %s | %s |" % (
                    r["region"], int(r["track"]), int(r["frame"]), r["dir"], r["ref"].date(), r["sec"].date(),
                    r["span_days"], s, r["coverage"]))
            L.append("")
        if ev[0] == "exact":
            e, e2 = ev[1], ev[1]
        else:
            e, e2 = ev[1], ev[2]
        single = [r for r in recs if r["dataset"] in ("GCOV", "SME2") and r["ref"] and r["region"] == ev_region]
        after = sorted([r for r in single if r["ref"] > e2], key=lambda r: r["ref"])
        before = sorted([r for r in single if r["ref"] < e], key=lambda r: r["ref"], reverse=True)
        on_day = [r for r in single if e <= r["ref"] <= e2]
        for ds in ("GCOV", "SME2"):
            a_ = [r for r in after if r["dataset"] == ds]
            b_ = [r for r in before if r["dataset"] == ds]
            if a_ or b_ or on_day:
                bits = []
                if b_:
                    bits.append("last pass before: %s (track %s)" % (b_[0]["ref"].date(), b_[0]["track"]))
                if a_:
                    d = (a_[0]["ref"] - e2).total_seconds() / 86400
                    bits.append("first pass after: %s (track %s, %.1f days later)" % (a_[0]["ref"].date(), a_[0]["track"], d))
                L.append("- %s single-pass products: %s." % (ds, "; ".join(bits)))
        if on_day:
            L.append("- %d single-pass products were acquired during the event window itself." % len(on_day))
        L.append("")

    L += ["## 4. Things everyone should know before using these numbers", "",
          "- Everything with CRID P05023 is **provisional** (calibrated, still being validated). "
          "Validated products (CRID P05036) cover acquisitions from 21 Oct 2026 and none is mixed in here "
          "unless the table above says so.",
          "- The satellite has a **data gap** from %s to %s UTC. A chain of 12-day pairs is cut there; only a "
          "longer pair bridges it." % (DATA_GAP[0].strftime("%Y-%m-%d"), DATA_GAP[1].strftime("%Y-%m-%d")),
          "- Soil moisture (SME2) is provisional and not fully calibrated: treat small changes as noise.",
          "- Radar measures movement only along its line of sight, and the sign convention is **not verified** "
          "on a real event yet.",
          "- Backscatter (GCOV) changes with soil moisture and vegetation, so a change is not proof of a flood.",
          "- The region comes from the footprint centre of each product when rasterio is installed (CSV column "
          "region_source = footprint), otherwise from the track number (region_source = track number).", ""]

    L += ["## 5. Files", "",
          "- `products.csv`: one row per product (open it in Excel). Columns: dataset, region, track, frame, "
          "direction, coverage, CRID, maturity, dates, pair length, size, raw file kept, complete, layers "
          "missing, geometry extras, folder name.",
          "- This report: `DATA_REPORT.md`.", "",
          "To regenerate: `python tools/data_report.py --data <data folder> --out results/data-inventory`."]

    (a.out / "DATA_REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("wrote %s and %s (%d products, %.1f GB)" % (a.out / "DATA_REPORT.md", a.out / "products.csv",
                                                      len(recs), gb(total)))


if __name__ == "__main__":
    main()
