"""Step 9a: water-area time series per NISAR date and track (best method vs DSWx), with flags.

Flags (dates are kept, never dropped):
  - "possible wind effect": predicted area drops > 20% below the mean of the neighbouring dates
    of the same track (wind-roughened open water looks bright in SAR and can be missed)
  - "partial coverage": matched DSWx has < 95% valid pixels over the SAR-valid AOI; its area is
    left blank and the date is excluded from area comparisons and pair selection
  - "dswx outlier": matched DSWx acquisition flagged by select_target.py (> 15% from the median of
    its time neighbours and +-3 d acquisitions); its area is left blank and excluded likewise
Orbit-consistency check: ascending vs descending model areas on nearby dates (<= 3 days apart):
mean absolute difference in km² and %, appended to results.csv and outputs/orbit_consistency.csv.

Writes outputs/water_area_timeseries.csv and outputs/water_area_timeseries.png
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from common import OUTPUTS, append_results

WIND_DROP = 0.20
MIN_DSWX_VALID = 0.95
ORBIT_PAIR_DAYS = 3


def best_method() -> str:
    """Operational variant = the one chosen on the selection track only (heldout_eval.json).
    Falls back to the best pooled U-Net row only if the held-out protocol has not been run."""
    import json

    f = OUTPUTS / "heldout_eval.json"
    if f.exists():
        return json.loads(f.read_text())["variant_selected_on_selection_track"]
    r = pd.read_csv(OUTPUTS / "results.csv")
    r = r[r["domain"].str.startswith("NISAR") & r["iou"].notna()
          & r["method"].str.startswith("U-Net")]
    return r.sort_values("iou", ascending=False).iloc[0]["method"]


def orbit_consistency(ts: pd.DataFrame) -> pd.DataFrame:
    asc = ts[ts["direction"] == "ASCENDING"]
    desc = ts[ts["direction"] == "DESCENDING"]
    pairs = []
    for _, a in asc.iterrows():
        dt = (pd.to_datetime(desc["date"]) - pd.to_datetime(a["date"])).dt.days.abs()
        if len(dt) and dt.min() <= ORBIT_PAIR_DAYS:
            d = desc.loc[dt.idxmin()]
            pairs.append({"asc_date": a["date"], "desc_date": d["date"], "days_apart": int(dt.min()),
                          "asc_km2": a["model_water_km2"], "desc_km2": d["model_water_km2"],
                          "abs_diff_km2": abs(a["model_water_km2"] - d["model_water_km2"]),
                          "abs_diff_pct": 100 * abs(a["model_water_km2"] - d["model_water_km2"])
                          / np.mean([a["model_water_km2"], d["model_water_km2"]])})
    return pd.DataFrame(pairs)


def main() -> None:
    d = pd.read_csv(OUTPUTS / "nisar_eval_per_date.csv").sort_values(["track", "direction", "date"])
    import json

    res = json.loads((OUTPUTS / "aoi.json").read_text())["chosen"]["reservoir"]
    cand = pd.read_csv(OUTPUTS / "candidate_scenes.csv")
    cand = cand[(cand["reservoir"] == res) & cand["usable"]][["date", "track", "dswx_flag"]]
    d = d.drop(columns=["dswx_flag"], errors="ignore").merge(cand, on=["date", "track"], how="left", validate="one_to_one")
    m = best_method()
    out = []
    for (trk, dirn), g in d.groupby(["track", "direction"]):
        a = g[f"area_km2|{m}"].to_numpy()
        for i, (_, r) in enumerate(g.iterrows()):
            neigh = [a[j] for j in (i - 1, i + 1) if 0 <= j < len(a)]
            ref = float(np.mean(neigh)) if neigh else np.nan
            drop = (ref - a[i]) / ref if ref and ref > 0 else np.nan
            has = pd.notna(r["dswx_valid_frac"])
            outlier = str(r.get("dswx_flag", "")) == "dswx outlier"
            ok = has and r["dswx_valid_frac"] >= MIN_DSWX_VALID and not outlier
            flags = []
            if pd.notna(drop) and drop > WIND_DROP:
                flags.append("possible wind effect")
            if outlier:
                flags.append("dswx outlier")
            elif has and not ok:
                flags.append("partial coverage")
            out.append({
                "date": r["date"], "track": trk, "direction": dirn, "method": m,
                "model_water_km2": round(a[i], 3),
                "model_water_on_dswx_valid_km2": round(r[f"area_on_dswx_valid_km2|{m}"], 3) if ok else np.nan,
                "dswx_water_km2": round(r["dswx_water_km2"], 3) if ok else np.nan,
                "dswx_date": r["dswx_date"] if has else "",
                "dswx_valid_frac": round(r["dswx_valid_frac"], 3) if has else np.nan,
                "otsu_water_km2": round(r["area_km2|Otsu (HV dB, per scene)"], 3),
                "drop_vs_neighbours": round(drop, 3) if pd.notna(drop) else np.nan,
                "flag": "; ".join(flags),
                "dswx_excluded_reason": "; ".join(f for f in flags if f != "possible wind effect"),
            })
    ts = pd.DataFrame(out)
    ts.to_csv(OUTPUTS / "water_area_timeseries.csv", index=False)
    print(ts.to_string(index=False))

    oc = orbit_consistency(ts)
    if len(oc):
        oc.to_csv(OUTPUTS / "orbit_consistency.csv", index=False)
        print(oc.to_string(index=False))
        reservoir = d["tag"].iloc[0].split("_T")[0]
        append_results([{"domain": f"NISAR {reservoir}", "method": f"Orbit consistency ({m}, asc vs desc)",
                         "iou": np.nan, "precision": np.nan, "recall": np.nan, "n_pixels": np.nan,
                         "mae_km2": round(oc["abs_diff_km2"].mean(), 3), "mae_pct": round(oc["abs_diff_pct"].mean(), 2),
                         "notes": f"{len(oc)} asc/desc date pairs <= {ORBIT_PAIR_DAYS} days apart; model areas only"}])

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 4.5))
    for (trk, dirn), g in ts.groupby(["track", "direction"]):
        t = pd.to_datetime(g["date"])
        ax.plot(t, g["model_water_km2"], "o-", label=f"NISAR U-Net, track {trk} {dirn.lower()}")
        f = g["flag"].str.contains("wind")
        if f.any():
            ax.scatter(t[f], g["model_water_km2"][f], s=160, facecolors="none", edgecolors="red",
                       label=f"possible wind effect (track {trk})")
    dd = ts.dropna(subset=["dswx_water_km2"]).drop_duplicates("dswx_date")
    ax.plot(pd.to_datetime(dd["dswx_date"]), dd["dswx_water_km2"], "s--", color="k", alpha=0.6,
            label="DSWx-HLS (≥95% valid, matched ±5 d)")
    ax.set_ylabel("water area (km²)")
    ax.set_title(f"Water area, method: {m}", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUTPUTS / "water_area_timeseries.png", dpi=120)


if __name__ == "__main__":
    main()
