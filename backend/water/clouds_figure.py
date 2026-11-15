"""Why radar: same-day OPERA DSWx (optical, cloud-masked) vs NISAR water map.

Picks the DSWx overpass within 0 days of a NISAR pass that has the highest CMR tile cloud cover
and no valid AOI pixels (so the gap is cloud, not a swath edge), renders its public browse PNG
(grey = masked) next to the NISAR U-Net water map of the same day.
Writes outputs/figures/clouds.png (300 dpi) and outputs/clouds_figure.json (what was shown).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from common import BIG_OUT, OUTPUTS
from evaluate import method_threshold, slug
from nisar_search import dswx_acquisitions, sample_browse, search_dswx, utm_box, utm_of
from output_assets import CREDIT, basemap, decorate, overlay, warp
from timeseries import best_method


def main() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    chosen = json.loads((OUTPUTS / "aoi.json").read_text())
    res = chosen["chosen"]["reservoir"]
    bbox = chosen["aois"][res]["bbox"]
    acq = pd.read_csv(OUTPUTS / f"dswx_acquisitions_{res}.csv")
    scenes = pd.read_csv(OUTPUTS / "nisar_scenes.csv")
    same = acq.merge(scenes[["date", "tag", "track"]], left_on="dswx_date", right_on="date")
    cand = same[(same["dswx_aoi_valid_frac"] < 0.05)].sort_values("dswx_cloud_max_pct", ascending=False)
    if cand.empty:
        raise SystemExit("no same-day cloudy DSWx overpass found")
    c = cand.iloc[0]
    d = pd.to_datetime(c["dswx_date"])
    a = dswx_acquisitions(search_dswx(bbox, f"{d:%Y-%m-%d}T00:00:00Z", f"{d:%Y-%m-%d}T23:59:59Z"), bbox)
    a = a[a["sensor"] == c["sensor"]].iloc[0]
    utm = utm_of(bbox)
    xmin, xmax, ymin, ymax = utm_box(bbox, utm)
    rgba = sample_browse(a["browse_urls"].split(";"), a["polys"], utm, xmin, xmax, ymin, ymax, 30.0)

    method = best_method()
    prob, _, b = warp(BIG_OUT / f"prob_{slug(method)}_{c['tag']}.tif")
    thr = method_threshold(method)
    water = (np.nan_to_num(prob, nan=0) >= thr).astype(np.uint8)
    px = abs((b[2] - b[0]) / prob.shape[1] * 111.32 * np.cos(np.radians((b[1] + b[3]) / 2))
             * (b[3] - b[1]) / prob.shape[0] * 110.57)
    area = float(water.sum() * px)

    fig, ax = plt.subplots(1, 2, figsize=(14, 5.6))
    # DSWx browse is on a UTM grid; show it in its own UTM frame with a grey "masked" background
    ax[0].set_facecolor("#9a9a9a")
    ax[0].imshow(rgba, extent=(xmin, xmax, ymin, ymax), interpolation="nearest")
    ax[0].set_xlim(xmin, xmax); ax[0].set_ylim(ymin, ymax); ax[0].set_aspect("equal")
    ax[0].set_xticks([]); ax[0].set_yticks([])
    ax[0].set_title(f"OPERA DSWx-HLS, {c['dswx_date']} ({c['sensor']}): tile cloud cover "
                    f"{c['dswx_cloud_max_pct']:.0f}%, valid reservoir pixels {c['dswx_aoi_valid_frac']:.0%}\n"
                    "→ no optical water map", fontsize=9)
    ax[0].legend(handles=[Patch(color="#9a9a9a", label="masked (cloud / no data)")], loc="lower right", fontsize=8)
    bg = basemap(ax[1], b, c["tag"])  # the 07-13 clear acquisition matched to this pass, not the old Esri mosaic
    overlay(ax[1], water, b, {1: (0.15, 0.52, 1.0, 0.7)})
    # the nearest CLEAR optical water map (matched to this NISAR pass), drawn as a shoreline: the old basemap photo
    # shows a lower, drought-time lake, so the comparison must be against same-period optical water
    from matplotlib.lines import Line2D
    sc = scenes.set_index("tag").loc[c["tag"]]
    handles = [Patch(color=(0.15, 0.52, 1.0), label="NISAR water (U-Net)")]
    ref_txt = ""
    if isinstance(sc.get("dswx_tif"), str) and sc["dswx_tif"]:
        ref, _, rb = warp(sc["dswx_tif"])
        ref = np.where(ref == 1, 1.0, 0.0)
        yy = np.linspace(rb[3], rb[1], ref.shape[0]); xx = np.linspace(rb[0], rb[2], ref.shape[1])
        ax[1].contour(xx, yy, ref, levels=[0.5], colors=["#ffd400"], linewidths=1.1, zorder=6)
        handles.append(Line2D([], [], color="#ffd400", lw=1.5, label=f"optical shoreline, nearest clear day ({sc['dswx_date']})"))
        ref_txt = f"; yellow = OPERA DSWx water edge on {sc['dswx_date']}"
    decorate(ax[1], b, f"NISAR L-band, same day (track {int(c['track'])}): U-Net water {area:.1f} km²")
    ax[1].legend(handles=handles, loc="upper left", fontsize=8)
    fig.suptitle(f"{res.replace('_', ' ')}: clouds stop the optical water map, radar does not", fontsize=12)
    fig.text(.01, .01, f"Background: {bg}, nearest clear day" + ref_txt + " · " + CREDIT, fontsize=7.5)
    fig.tight_layout(rect=[0, .06, 1, .95])
    fig.savefig(OUTPUTS / "figures" / "clouds.png", dpi=300)
    plt.close(fig)
    (OUTPUTS / "clouds_figure.json").write_text(json.dumps({
        "dswx_date": c["dswx_date"], "dswx_sensor": c["sensor"], "dswx_tile_cloud_pct": float(c["dswx_cloud_max_pct"]),
        "dswx_valid_frac_over_aoi": float(c["dswx_aoi_valid_frac"]), "nisar_tag": c["tag"],
        "nisar_water_km2_approx": round(area, 2), "method": method}, indent=2))
    print("wrote outputs/figures/clouds.png", c["dswx_date"], c["sensor"], c["tag"])


if __name__ == "__main__":
    main()
