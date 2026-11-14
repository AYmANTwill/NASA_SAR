#!/usr/bin/env python3
"""Builds plan_validation.json: the Panama M7.7 (9 Oct 2026 17:56:06 UTC, USGS us6000u18k) validation download.

Reads the `panama` rows of plan_nisar.json (never modifies it) and keeps, per viewing geometry (track, frame, direction):
  - every 12-day pair that straddles the earthquake (ref <= origin time <= sec), role "co";
  - the most recent pair that ends before the earthquake, role "pre" (the no-event reference for the noise floor).
Rows keep the plan_nisar.json format; they get part = tier = 1 and extra_layers = true, so the troposphere and
solid-earth-tide cubes are extracted for the correction tests. Directly usable as:

    python download_all.py run --plan plan_validation.json --part 1 [--keep-raw]

Usage (from the repo root):  python tools/make_validation_plan.py [--out plan_validation.json] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "plan_nisar.json"
DEFAULT_OUT = REPO / "plan_validation.json"
EVENT = "20261009T175606"          # USGS origin time, exact instant
CO_SPAN_DAYS = 12
TIERS = {"1": "Panama validation (outside Morocco)"}


def geometry(r: dict) -> tuple:
    return (r["track"], r["frame"], r["dir"])


def straddles(r: dict, event: str = EVENT) -> bool:
    return r["ref_ts"] <= event <= r["sec_ts"]


def select(rows: list[dict], event: str = EVENT) -> list[dict]:
    """Co-seismic 12-day pairs + the most recent pre-event pair, per geometry. Returns new rows (inputs untouched)."""
    pan = [r for r in rows if r.get("dataset") == "panama" and r.get("level") == "GUNW"]
    out = []
    for g in sorted({geometry(r) for r in pan}):
        mine = [r for r in pan if geometry(r) == g]
        co = [r for r in mine if straddles(r, event) and r["span"] == CO_SPAN_DAYS]
        pre = [r for r in mine if r["sec_ts"] < event]
        picked = [(r, "co") for r in co]
        if pre:
            picked.append((max(pre, key=lambda r: r["sec_ts"]), "pre"))
        out += [{**r, "part": 1, "tier": 1, "extra_layers": True, "event_role": role} for r, role in picked]
    return sorted(out, key=lambda r: (r["track"], r["frame"], r["dir"], r["ref_ts"]))


def build(source: Path = SOURCE) -> dict:
    rows = json.loads(source.read_text())["files"]
    files = select(rows)
    return {"created": time.strftime("%Y-%m-%d %H:%M"), "scheme": "validation-v1", "tiers": TIERS,
            "event": EVENT, "event_usgs_id": "us6000u18k", "source_plan": source.name, "files": files}


def summary(plan: dict) -> str:
    files = plan["files"]
    gb = sum(r["size"] for r in files) / 1e9
    n_co = sum(r["event_role"] == "co" for r in files)
    n_geo = len({geometry(r) for r in files})
    return (f"{len(files)} files, {gb:.2f} GB ({n_co} co-seismic + {len(files) - n_co} pre-event, "
            f"{n_geo} geometries)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--dry-run", action="store_true", help="print the summary without writing the file")
    a = ap.parse_args()
    if Path(a.out).resolve() == SOURCE.resolve():
        sys.exit("Refused: plan_nisar.json must not be modified.")
    plan = build()
    if not plan["files"]:
        sys.exit("No Panama row found in plan_nisar.json.")
    print(summary(plan))
    for r in plan["files"]:
        print(f"  {r['event_role']:<3} T{r['track']:03d} {r['dir']} F{r['frame']:03d} {r['ref_ts'][:8]}->{r['sec_ts'][:8]} "
              f"{r['span']:>2} d  {r['size'] / 1e9:.2f} GB")
    if not a.dry_run:
        Path(a.out).write_text(json.dumps(plan, indent=1))
        print(f"Written: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
