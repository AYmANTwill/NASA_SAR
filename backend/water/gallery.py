"""Visual performance gallery: one map per evaluated NISAR date + one contact sheet.

Per date (outputs/figures/gallery/<date>_T<track>.png, 110 dpi):
  left  = NISAR HH backscatter (dB) with the U-Net water outline (cyan)
  right = Esri World Imagery basemap + agreement with OPERA DSWx:
          white agreement, red miss (DSWx only), orange false alarm (NISAR only); IoU/P/R in title
Dates whose DSWx is flagged (partial coverage / outlier) or whose model area is wind-flagged are
still drawn, with the flag in the title, so failures are visible too.
Contact sheet: outputs/figures/gallery_contact_sheet.png (agreement panels, sorted by track/date).
Usage: python gallery.py
"""
from __future__ import annotations

import json
import textwrap

import numpy as np
import pandas as pd
from scipy.ndimage import binary_erosion

from common import BIG_OUT, OUTPUTS
from evaluate import slug
from output_assets import CREDIT, warp
from rasterio.warp import Resampling

GALLERY = OUTPUTS / "figures" / "gallery"


def fetch_basemap(bounds):
    try:
        import contextily as cx
        img, ext = cx.bounds2img(*bounds, ll=True, source=cx.providers.Esri.WorldImagery, zoom=13)
        from rasterio.warp import transform_bounds
        w, s, e, n = transform_bounds("EPSG:3857", "EPSG:4326", ext[0], ext[2], ext[1], ext[3])
        return img, (w, e, s, n)
    except Exception as ex:
        print(f"WARNING basemap unavailable: {ex}")
        return None, None


def agreement(pred, truth, rv):
    v = np.zeros(pred.shape, np.uint8)
    v[truth & pred & rv] = 1
    v[truth & ~pred & rv] = 2
    v[~truth & pred & rv] = 3
    rgba = np.zeros(pred.shape + (4,))
    for k, c in {1: (1, 1, 1, .85), 2: (.84, .15, .16, .95), 3: (1, .55, 0, .95)}.items():
        rgba[v == k] = c
    return rgba


def main() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    GALLERY.mkdir(parents=True, exist_ok=True)
    held = json.loads((OUTPUTS / "heldout_eval.json").read_text())
    method, thr = held["variant_selected_on_selection_track"], held["probability_threshold"]
    res = held["reservoir"].replace("_", " ")
    scenes = pd.read_csv(OUTPUTS / "nisar_scenes.csv")
    ev = pd.read_csv(OUTPUTS / "nisar_eval_per_date.csv").set_index("tag")
    ts = pd.read_csv(OUTPUTS / "water_area_timeseries.csv").set_index(["date", "track"])
    scenes = scenes.sort_values(["track", "date"])

    _, _, b0 = warp(BIG_OUT / f"prob_{slug(method)}_{scenes.iloc[0].tag}.tif")
    base, base_ext = fetch_basemap(b0)
    legend = [Patch(color="white", label="agreement"), Patch(color="#d62728", label="miss (DSWx only)"),
              Patch(color="#ff8c00", label="false alarm (NISAR only)")]
    sheet = []
    for _, sc in scenes.iterrows():
        prob, _, b = warp(BIG_OUT / f"prob_{slug(method)}_{sc.tag}.tif")
        hh, _, bh = warp(sc.nisar_tif, 1, resampling=Resampling.bilinear)
        pred = np.nan_to_num(prob, nan=0) >= thr
        ext = (b[0], b[2], b[1], b[3])
        e = ev.loc[sc.tag]
        t = ts.loc[(sc.date, sc.track)]
        role = "selection" if sc.track == held["selection_track"] else "held-out"
        flag = str(t["flag"]) if isinstance(t["flag"], str) else ""
        has_ref = isinstance(sc.dswx_tif, str) and len(sc.dswx_tif) > 0
        fig, ax = plt.subplots(1, 2, figsize=(14, 5.6))
        ax[0].imshow(hh, extent=(bh[0], bh[2], bh[1], bh[3]), cmap="gray", vmin=-25, vmax=0)
        edge = pred & ~binary_erosion(pred, iterations=2)
        ov = np.zeros(pred.shape + (4,)); ov[edge] = (0, 1, 1, 1)
        ax[0].imshow(ov, extent=ext, interpolation="nearest")
        ax[0].set_title(f"NISAR HH (dB) + U-Net water outline — model {t['model_water_km2']:.1f} km²", fontsize=9)
        if base is not None:
            ax[1].imshow(base, extent=base_ext)
        title = f"vs OPERA DSWx: no clear reference"
        if has_ref:
            from output_assets import warp as _w
            ref, _, _ = _w(sc.dswx_tif)
            rgba = agreement(pred, ref == 1, ref != 255)
            ax[1].imshow(rgba, extent=ext, interpolation="nearest")
            tp, fp, fn = e[f"tp|{method}"], e[f"fp|{method}"], e[f"fn|{method}"]
            iou, p, r = tp / max(tp + fp + fn, 1), tp / max(tp + fp, 1), tp / max(tp + fn, 1)
            title = (f"vs OPERA DSWx {sc.dswx_date}: IoU {iou:.3f}  P {p:.3f}  R {r:.3f}"
                     + (f"  DSWx {t['dswx_water_km2']:.1f} km²" if pd.notna(t["dswx_water_km2"]) else ""))
            sheet.append((sc, rgba, ext, iou, flag, role))
        ax[1].set_title(title, fontsize=9)
        ax[1].legend(handles=legend, loc="upper left", fontsize=7)
        for a in ax:
            a.set_xlim(b[0], b[2]); a.set_ylim(b[1], b[3])
            a.set_aspect(1 / np.cos(np.radians((b[1] + b[3]) / 2)))
            a.set_xlabel("longitude (°)"); a.set_ylabel("latitude (°)")
        head = f"{res} — {sc.date} — NISAR track {sc.track} {sc.direction.lower()} ({role}) — {method}"
        if flag:
            head += f" — FLAG: {flag}"
        fig.suptitle(head, fontsize=11, color="#b00000" if flag else "black")
        fig.text(.01, .01, "Basemap: Esri World Imagery · " + CREDIT, fontsize=7)
        fig.tight_layout(rect=[0, .03, 1, .95])
        fig.savefig(GALLERY / f"{sc.date}_T{sc.track:03d}.png", dpi=110)
        plt.close(fig)

    n = len(sheet); cols = 6; rows = int(np.ceil(n / cols))
    fig, axs = plt.subplots(rows, cols, figsize=(cols * 3.4, rows * 2.6))
    for a in axs.ravel():
        a.axis("off")
    for a, (sc, rgba, ext, iou, flag, role) in zip(axs.ravel(), sheet):
        if base is not None:
            a.imshow(base, extent=base_ext)
        a.imshow(rgba, extent=ext, interpolation="nearest")
        a.set_xlim(ext[0], ext[1]); a.set_ylim(ext[2], ext[3])
        a.set_title(textwrap.shorten(f"T{sc.track} {sc.date} IoU {iou:.2f} {'(sel)' if role == 'selection' else ''}"
                                     f"{' ' + flag if flag else ''}", 48), fontsize=7, color="#b00000" if flag else "black")
    fig.suptitle(f"{res}: U-Net ({method}) vs OPERA DSWx on every NISAR date — white agree, red miss, orange false alarm",
                 fontsize=11)
    fig.text(.01, .005, "Basemap: Esri World Imagery · " + CREDIT, fontsize=7)
    fig.tight_layout(rect=[0, .02, 1, .97])
    fig.savefig(OUTPUTS / "figures" / "gallery_contact_sheet.png", dpi=150)
    plt.close(fig)
    print(f"wrote {len(scenes)} gallery maps to {GALLERY} and the contact sheet")


if __name__ == "__main__":
    main()
