"""Fine-tuning step 1: training sites, NISAR dates and same-date DSWx labels (search only, public CMR).

Sites = Moroccan reservoirs OTHER than the held-out case reservoir (aoi.json "chosen"). The held-out
reservoir is excluded by name and by footprint (no training site may intersect its bbox).
Labels: DSWx within +-2 days of the NISAR date, clear (>= 95% valid AOI pixels in the browse), and not an
outlier (select_target.flag_outliers: > 15% from the median of time neighbours and +-3 d acquisitions).
Writes outputs/finetune/sites.json and outputs/finetune/candidates.csv (does not touch the case outputs).
Usage: python finetune/ft_sites.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import pandas as pd  # noqa: E402
from shapely.geometry import box  # noqa: E402

import nisar_search as ns  # noqa: E402
from common import OUTPUTS, RESERVOIRS  # noqa: E402
from select_target import CLEAR, flag_outliers  # noqa: E402

FT = OUTPUTS / "finetune"
# Additional large Moroccan dams (approximate centres; real extent derived from OSM like the case sites)
EXTRA = {
    "Idriss_1er": (34.16, -4.75),
    "Sidi_Mohamed_Ben_Abdellah": (33.86, -6.70),
    "Oued_El_Makhazine": (35.02, -5.77),
    "Mohammed_V": (34.67, -2.97),
    # v3 (2026-11-15): more reservoirs, hence more tracks and incidence angles (approximate centres; the extent
    # is the largest OSM water body nearby; a site whose box meets the case reservoir is skipped automatically)
    "Lalla_Takerkoust": (31.36, -8.13),
    "Abdelmoumen": (30.68, -9.22),
    "Youssef_Ben_Tachfine": (29.86, -9.33),
    "Mansour_Eddahbi": (30.97, -6.78),
    "Hassan_Addakhil": (31.98, -4.45),
    "El_Kansera": (34.04, -5.92),
    "Allal_El_Fassi": (33.93, -4.68),
}
MAX_DAYS = 2


def main() -> None:
    FT.mkdir(parents=True, exist_ok=True)
    meta = json.loads((OUTPUTS / "aoi.json").read_text())
    held = meta["chosen"]["reservoir"]
    held_box = box(*meta["aois"][held]["bbox"])
    names = {k: v for k, v in RESERVOIRS.items() if k != held}
    ns.RESERVOIRS.update(EXTRA)
    names.update(EXTRA)
    sites, frames = {}, []
    for name in names:
        cache_csv, cache_js = FT / f"site_{name}.csv", FT / f"site_{name}.json"
        if cache_js.exists():  # resume: this site was already searched
            info = json.loads(cache_js.read_text())
            if info.get("skipped"):
                print(f"[{name}] cached: skipped ({info['skipped']})", flush=True)
                continue
            m = pd.read_csv(cache_csv)
            frames.append(m)
            sites[name] = info
            print(f"[{name}] cached: {len(m)} dates", flush=True)
            continue
        try:
            aoi = meta["aois"].get(name) or ns.derive_aoi(name)
        except Exception as e:
            print(f"[{name}] AOI failed: {e}")
            continue
        if box(*aoi["bbox"]).intersects(held_box):
            print(f"[{name}] intersects the held-out reservoir: skipped", flush=True)
            cache_js.write_text(json.dumps({"skipped": "intersects held-out reservoir"}))
            continue
        print(f"[{name}] OSM {aoi.get('osm')} '{aoi.get('osm_name')}' bbox={aoi['bbox']}", flush=True)
        nis = ns.search_nisar(aoi["bbox"])
        nis = nis[nis["usable"]] if len(nis) else nis
        if nis.empty:
            print(f"[{name}] no usable NISAR", flush=True)
            cache_js.write_text(json.dumps({"skipped": "no usable NISAR"}))
            continue
        t0 = (datetime.strptime(nis["date"].min(), "%Y-%m-%d") - timedelta(days=6)).strftime("%Y-%m-%dT00:00:00Z")
        t1 = (datetime.strptime(nis["date"].max(), "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%dT23:59:59Z")
        dsw = ns.search_dswx(aoi["bbox"], t0, t1)
        acq = ns.dswx_acquisitions(dsw, aoi["bbox"]) if len(dsw) else pd.DataFrame()
        if acq.empty:
            print(f"[{name}] no DSWx", flush=True)
            cache_js.write_text(json.dumps({"skipped": "no DSWx"}))
            continue
        fl = flag_outliers(acq.drop(columns=["polys"]))
        bad = set(fl.loc[fl["outlier"], "dswx_date"].astype(str) + "|" + fl.loc[fl["outlier"], "sensor"])
        acq = acq[acq["dswx_aoi_valid_frac"] >= CLEAR]
        acq = acq[~(acq["dswx_date"].astype(str) + "|" + acq["sensor"]).isin(bad)]
        m = ns.match_dswx(nis, acq, max_days=MAX_DAYS, min_valid=CLEAR)
        m = m[m["dswx_date"].astype(str) != "none"].copy()
        m.insert(0, "site", name)
        frames.append(m)
        sites[name] = {**aoi, "n_dates": int(len(m)), "tracks": sorted(m["track"].unique().tolist()),
                       "dswx_outliers_removed": len(bad)}
        print(f"[{name}] {len(m)} NISAR dates with clear same-date DSWx; tracks {sites[name]['tracks']}", flush=True)
        m.to_csv(cache_csv, index=False)
        cache_js.write_text(json.dumps(sites[name], default=str))
    cand = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    cand.to_csv(FT / "candidates.csv", index=False)
    (FT / "sites.json").write_text(json.dumps({"held_out": held, "sites": sites}, indent=2, default=str))
    print(cand.groupby("site").size() if len(cand) else "no candidates")


if __name__ == "__main__":
    main()
