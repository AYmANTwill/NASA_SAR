"""Choose reservoir + track after nisar_search.py --all (outlier-robust, team rule 2026-11-14 evening).

DSWx areas used for selection are the coarse (100 m) browse-derived areas, available for every
OPERA DSWx-HLS overpass of all three reservoirs (outputs/dswx_acquisitions_<reservoir>.csv).

1. Clear acquisition: >= 95% valid AOI pixels. Others stay in the CSV flagged "partial coverage".
2. Outlier: a clear acquisition whose area differs by > 15% from the median of its comparators,
   where comparators = the previous and next clear acquisitions in time plus every other clear
   acquisition (any sensor/orbit) within +-3 days. Outliers are flagged "dswx outlier" and ignored.
3. Genuine change of a reservoir = (max - min) / max of the 30-day centred rolling median of its
   clear, non-outlier acquisitions in the NISAR period (seasonal signal). The plain min-max after
   outlier removal is also reported; it is not used because isolated single-sensor dips just
   under 15% (e.g. 27.4 vs 31.2 km2 on the same day at Bin El Ouidane) still dominate it.
4. Choose the reservoir with the largest genuine change if it exceeds 10%; its track with the most
   clear matched dates is the main track, other usable tracks are kept as separate lines.
   If no reservoir exceeds 10%, choose the site with the best data (most clear matched dates over
   usable tracks) and frame the case as monitoring ("stable within noise").
Writes outputs/reservoir_comparison.csv, outputs/dswx_outliers.csv; updates candidate_scenes.csv
(dswx_flag, same_track_group, also_used) and aoi.json["chosen"].
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from common import OUTPUTS

CLEAR = 0.95
OUTLIER = 0.15
NEAR_DAYS = 3
MIN_CHANGE = 0.10
RESERVOIRS = ["Al_Massira", "Bin_El_Ouidane", "Al_Wahda"]


def _deviations(a: pd.DataFrame, keep: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Relative deviation of every row from the median of its comparators among kept rows."""
    k = np.flatnonzero(keep)
    med = np.full(len(a), np.nan)
    ncmp = np.zeros(len(a), int)
    for i in range(len(a)):
        before, after = k[k < i], k[k > i]
        idx = set()
        if len(before):
            idx.add(before[-1])
        if len(after):
            idx.add(after[0])
        near = k[(np.abs((a["t"].iloc[k] - a["t"].iloc[i]).dt.days.to_numpy()) <= NEAR_DAYS) & (k != i)]
        idx |= set(near.tolist())
        if idx:
            med[i] = float(np.median(a["dswx_water_km2_browse"].to_numpy()[sorted(idx)]))
            ncmp[i] = len(idx)
    dev = np.abs(a["dswx_water_km2_browse"].to_numpy() - med) / med
    return dev, med, ncmp


def flag_outliers(acq: pd.DataFrame) -> pd.DataFrame:
    """Iterative: drop the single worst offender (> 15% from its comparator median), recompute
    against the remaining acquisitions, repeat. Avoids flagging good dates next to bad ones."""
    a = acq[acq["dswx_aoi_valid_frac"] >= CLEAR].copy()
    a["t"] = pd.to_datetime(a["dswx_date"])
    a = a.sort_values("t").reset_index(drop=True)
    keep = np.ones(len(a), bool)
    while True:
        dev, med, ncmp = _deviations(a, keep)
        cand = np.where(keep & (dev > OUTLIER), dev, -1)
        if cand.max() < 0:
            break
        keep[int(np.argmax(cand))] = False
    dev, med, ncmp = _deviations(a, keep)  # final deviations w.r.t. the kept set
    a["comparator_median_km2"] = med
    a["n_comparators"] = ncmp
    a["rel_dev"] = dev
    a["outlier"] = ~keep
    return a


def seasonal_change(a: pd.DataFrame) -> float:
    s = a.groupby("t")["dswx_water_km2_browse"].median().sort_index()
    if len(s) < 3:
        return 0.0
    rm = s.rolling("30D", center=True, min_periods=2).median()
    return round(float((rm.max() - rm.min()) / rm.max()), 3)


def main() -> None:
    c = pd.read_csv(OUTPUTS / "candidate_scenes.csv")
    has = c["dswx_date"].astype(str) != "none"
    c["dswx_flag"] = ""
    c.loc[has & (c["dswx_aoi_valid_frac"] < CLEAR), "dswx_flag"] = "partial coverage"

    comp, outl = [], []
    for res in RESERVOIRS:
        cr = c[(c["reservoir"] == res) & c["usable"]]
        if cr.empty:
            comp.append({"reservoir": res, "usable_nisar_dates": 0})
            continue
        a = flag_outliers(pd.read_csv(OUTPUTS / f"dswx_acquisitions_{res}.csv"))
        lo, hi = pd.to_datetime(cr["date"].min()) - pd.Timedelta(days=5), pd.to_datetime(cr["date"].max()) + pd.Timedelta(days=5)
        a = a[(a["t"] >= lo) & (a["t"] <= hi)]
        a.insert(0, "reservoir", res)
        outl.append(a.drop(columns=["t"]))
        bad = set(a.loc[a["outlier"], "dswx_date"].astype(str))
        ok = a.loc[~a["outlier"], "dswx_water_km2_browse"]
        row = {"reservoir": res, "usable_nisar_dates": len(cr), "clear_dswx_acquisitions": len(a),
               "dswx_outliers": int(a["outlier"].sum()),
               "outlier_dates": ";".join(sorted(bad)),
               "dswx_km2_min": ok.min(), "dswx_km2_median": ok.median(), "dswx_km2_max": ok.max(),
               "genuine_change_frac": seasonal_change(a[~a["outlier"]]),
               "minmax_change_after_outliers": round((ok.max() - ok.min()) / ok.max(), 3) if len(ok) >= 2 else 0.0,
               "raw_change_frac_before_outlier_check": round((a["dswx_water_km2_browse"].max() - a["dswx_water_km2_browse"].min())
                                                             / a["dswx_water_km2_browse"].max(), 3) if len(a) >= 2 else 0.0}
        # per track: clear, non-outlier matched dates
        sel = c.index[(c["reservoir"] == res) & has & c["dswx_date"].astype(str).isin(bad)]
        c.loc[sel, "dswx_flag"] = c.loc[sel, "dswx_flag"].where(c.loc[sel, "dswx_flag"] != "", "dswx outlier")
        good = cr[(cr["dswx_date"].astype(str) != "none") & (cr["dswx_aoi_valid_frac"] >= CLEAR)
                  & ~cr["dswx_date"].astype(str).isin(bad)]
        tracks = good.groupby(["track", "frame", "direction"])
        best_track = tracks.size().sort_values(ascending=False)
        row["clear_matched_nisar_dates"] = len(good)
        row["tracks"] = "; ".join(f"T{t}{d[0]} f{f}: {n}" for (t, f, d), n in best_track.items())
        if len(best_track):
            (t, f, d) = best_track.index[0]
            g = good[(good["track"] == t) & (good["frame"] == f) & (good["direction"] == d)]["dswx_water_km2_browse"]
            row.update({"main_track": int(t), "main_frame": int(f), "main_direction": d,
                        "main_track_change_frac": round((g.max() - g.min()) / g.max(), 3) if len(g) >= 2 else 0.0})
        comp.append(row)
    comp = pd.DataFrame(comp)
    comp.to_csv(OUTPUTS / "reservoir_comparison.csv", index=False)
    pd.concat(outl, ignore_index=True).to_csv(OUTPUTS / "dswx_outliers.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(comp.to_string(index=False))

    cand = comp[comp["clear_matched_nisar_dates"].fillna(0) >= 2]
    changing = cand[cand["genuine_change_frac"] > MIN_CHANGE]
    if len(changing):
        best = changing.sort_values("genuine_change_frac", ascending=False).iloc[0]
        framing = "change"
        why = f"largest genuine DSWx change ({best['genuine_change_frac']:.1%} > {MIN_CHANGE:.0%}) after outlier removal"
    else:
        best = cand.sort_values(["clear_matched_nisar_dates", "clear_dswx_acquisitions"], ascending=False).iloc[0]
        framing = "monitoring"
        why = (f"no reservoir changes by more than {MIN_CHANGE:.0%} after outlier removal; "
               "best data coverage -> monitoring case (stable within noise)")
    res, trk, frm, dirn = best["reservoir"], int(best["main_track"]), int(best["main_frame"]), best["main_direction"]
    c["same_track_group"] = (c["reservoir"] == res) & (c["track"] == trk) & (c["frame"] == frm) \
        & (c["direction"] == dirn) & c["usable"]
    c["also_used"] = (c["reservoir"] == res) & c["usable"] & ~c["same_track_group"]
    c.to_csv(OUTPUTS / "candidate_scenes.csv", index=False)
    meta = json.loads((OUTPUTS / "aoi.json").read_text())
    meta["chosen"] = {"reservoir": res, "track": trk, "frame": frm, "direction": dirn, "framing": framing,
                      "reason": why, "rule": "outlier = >15% from median of time neighbours and +-3 d acquisitions"}
    (OUTPUTS / "aoi.json").write_text(json.dumps(meta, indent=2, default=str))
    print(f"\nCHOSEN: {res} track {trk} frame {frm} {dirn} [{framing}]  ({why})")


if __name__ == "__main__":
    main()
