"""Pitch figure: the DSWx outlier check at the case reservoir (no number typed by hand).

Top: every clear OPERA DSWx acquisition (browse-derived area) with the outliers removed by
select_target.py marked, the median of their comparators, and NISAR model areas.
Bottom: DSWx browse on the outlier date, DSWx on the closest clean acquisition, NISAR water the same day.
Writes outputs/figures/dswx_outlier_check.png and outputs/dswx_outlier_check.json.
Usage: python outlier_figure.py
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from common import BIG_OUT, OUTPUTS
from evaluate import method_threshold, slug
from nisar_search import dswx_acquisitions, sample_browse, search_dswx, utm_box, utm_of
from output_assets import CREDIT, warp
from timeseries import best_method


def browse_for(bbox, date, sensor, res=30.0):
    d = pd.to_datetime(date)
    a = dswx_acquisitions(search_dswx(bbox, f"{d:%Y-%m-%d}T00:00:00Z", f"{d:%Y-%m-%d}T23:59:59Z"), bbox)
    a = a[a["sensor"] == sensor].iloc[0]
    utm = utm_of(bbox)
    xmin, xmax, ymin, ymax = utm_box(bbox, utm)
    return sample_browse(a["browse_urls"].split(";"), a["polys"], utm, xmin, xmax, ymin, ymax, res), (xmin, xmax, ymin, ymax)


def main() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    aoi = json.loads((OUTPUTS / "aoi.json").read_text())
    res = aoi["chosen"]["reservoir"]
    bbox = aoi["aois"][res]["bbox"]
    o = pd.read_csv(OUTPUTS / "dswx_outliers.csv")
    o = o[o["reservoir"] == res].copy()
    o["t"] = pd.to_datetime(o["dswx_date"])
    ts = pd.read_csv(OUTPUTS / "water_area_timeseries.csv")
    out_rows = o[o["outlier"]]
    nisar_hit = ts[ts["flag"].fillna("").str.contains("dswx outlier")]
    if nisar_hit.empty:
        raise SystemExit("no NISAR date matched to an outlier")
    hit = nisar_hit.iloc[0]
    bad = out_rows[out_rows["dswx_date"] == hit["dswx_date"]].iloc[0]
    clean = o[~o["outlier"]].copy()
    clean["dd"] = (clean["t"] - pd.to_datetime(bad["dswx_date"])).dt.days.abs()
    near = clean[clean["dd"] > 0].sort_values(["dd", "dswx_aoi_valid_frac"], ascending=[True, False]).iloc[0]
    tag = f"{res}_T{int(hit['track']):03d}{hit['direction'][0]}_{hit['date']}"

    fig = plt.figure(figsize=(15, 9.5))
    gs = fig.add_gridspec(2, 3, height_ratios=[1, 1.15])
    ax = fig.add_subplot(gs[0, :])
    ax.plot(clean["t"], clean["dswx_water_km2_browse"], "o", color="0.35", ms=4, label="OPERA DSWx, clear acquisitions kept")
    ax.plot(out_rows["t"], out_rows["dswx_water_km2_browse"], "X", color="#d62728", ms=12,
            label="DSWx removed by the outlier check (>15% from neighbours)")
    for _, r in out_rows.iterrows():
        ax.annotate("", xy=(r["t"], r["dswx_water_km2_browse"]), xytext=(r["t"], r["comparator_median_km2"]),
                    arrowprops={"arrowstyle": "->", "color": "#d62728", "lw": 1.2})
    for (trk, dirn), g in ts.groupby(["track", "direction"]):
        g = g.sort_values("date")
        ax.plot(pd.to_datetime(g["date"]), g["model_water_km2"], "-", lw=1, alpha=0.6, label=f"NISAR U-Net, track {trk} {dirn.lower()}")
    ax.set_ylabel("water area (km²)")
    ax.set_title(f"{res.replace('_', ' ')}: optical outliers caught before they could drive the case "
                 f"(arrows: drop from the neighbours' median)", fontsize=10)
    ax.set_ylim(min(10, out_rows["dswx_water_km2_browse"].min() - 3), None)
    ax.grid(alpha=0.25); ax.legend(fontsize=8, ncol=2, loc="lower right")

    rgba_bad, ext = browse_for(bbox, bad["dswx_date"], bad["sensor"])
    rgba_ok, _ = browse_for(bbox, near["dswx_date"], near["sensor"])
    method = best_method()
    thr = method_threshold(method)
    prob, _, b = warp(BIG_OUT / f"prob_{slug(method)}_{tag}.tif")
    for k, (img, title) in enumerate([
            (rgba_bad, f"DSWx {bad['dswx_date']} ({bad['sensor']}): {bad['dswx_water_km2_browse']:.1f} km²  → REMOVED"),
            (rgba_ok, f"DSWx {near['dswx_date']} ({near['sensor']}), clean: {near['dswx_water_km2_browse']:.1f} km²")]):
        a = fig.add_subplot(gs[1, k])
        a.set_facecolor("#9a9a9a")
        a.imshow(img, extent=ext, interpolation="nearest")
        a.set_xlim(ext[0], ext[1]); a.set_ylim(ext[2], ext[3]); a.set_aspect("equal")
        a.set_xticks([]); a.set_yticks([])
        a.set_title(title, fontsize=9, color="#b00000" if k == 0 else "black")
    a = fig.add_subplot(gs[1, 2])
    water = np.nan_to_num(prob) >= thr
    rgba = np.zeros(water.shape + (4,)); rgba[water] = (0.15, 0.52, 1.0, 1); rgba[~water & np.isfinite(prob)] = (1, 1, 1, 1)
    a.imshow(rgba, extent=(b[0], b[2], b[1], b[3]), interpolation="nearest")
    a.set_aspect(1 / np.cos(np.radians((b[1] + b[3]) / 2))); a.set_xticks([]); a.set_yticks([])
    a.set_title(f"NISAR {hit['date']} (track {int(hit['track'])}), same day: {hit['model_water_km2']:.1f} km²", fontsize=9)
    # DSWx browse colour table (OPERA PROTEUS dswx_hls.py): blue open water (1), light blue partial surface
    # water (2), cyan snow-masked (252), grey cloud-masked (253), white not water (0)
    fig.legend(handles=[Patch(color=(0, 0, 1), label="DSWx open water"), Patch(color=(180/255, 213/255, 244/255), label="DSWx partial water"),
                        Patch(color=(0, 1, 1), label="DSWx SNOW mask (in June: misclassified)"),
                        Patch(color=(175/255, 175/255, 175/255), label="DSWx cloud mask"),
                        Patch(facecolor="white", edgecolor="0.5", label="not water"), Patch(color=(0.15, 0.52, 1.0), label="NISAR water")],
               loc="lower center", ncol=6, fontsize=8, bbox_to_anchor=(0.5, 0.025))
    fig.text(.01, .004, CREDIT + " · DSWx areas from the public browse images · colour table: OPERA PROTEUS", fontsize=7)
    fig.tight_layout(rect=[0, .07, 1, 1])
    fig.savefig(OUTPUTS / "figures" / "dswx_outlier_check.png", dpi=200)
    plt.close(fig)
    snow = int(np.all(rgba_bad[..., :3] == (0, 255, 255), -1).sum())
    snow_ok = int(np.all(rgba_ok[..., :3] == (0, 255, 255), -1).sum())
    info = {"snow_masked_pixels_30m": {"outlier_date": snow, "nearest_clean_date": snow_ok},
            "outlier": {"date": bad["dswx_date"], "sensor": bad["sensor"], "km2_browse": float(bad["dswx_water_km2_browse"]),
                        "neighbours_median_km2": float(bad["comparator_median_km2"]), "relative_deviation": float(bad["rel_dev"])},
            "nearest_clean": {"date": near["dswx_date"], "sensor": near["sensor"], "km2_browse": float(near["dswx_water_km2_browse"])},
            "nisar_same_day": {"tag": tag, "model_km2": float(hit["model_water_km2"])},
            "all_outliers": out_rows[["dswx_date", "sensor", "dswx_water_km2_browse", "comparator_median_km2", "rel_dev"]].to_dict("records")}
    (OUTPUTS / "dswx_outlier_check.json").write_text(json.dumps(info, indent=2, default=float))
    print(json.dumps(info, indent=1, default=float))


if __name__ == "__main__":
    main()
