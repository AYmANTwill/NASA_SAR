"""Render frontend image assets and 300 dpi slide figures from measured GeoTIFFs."""
from __future__ import annotations

import json
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import numpy as _np
import pandas as pd
import rasterio
from PIL import Image, ImageDraw
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, calculate_default_transform, reproject, transform_bounds
from scipy.ndimage import binary_dilation, binary_erosion

from common import BIG_OUT, OUTPUTS
from evaluate import slug
from timeseries import best_method

FIGURES = OUTPUTS / "figures"
RASTERS = OUTPUTS / "rasters"
CREDIT = "NISAR (NASA/ISRO), OPERA DSWx (NASA/JPL)"


def warp(path, band=1, max_dim=1600, resampling=Resampling.nearest):
    from common import dpath

    path = dpath(path)
    with rasterio.open(path) as src:
        bounds = transform_bounds(src.crs, "EPSG:4326", *src.bounds, densify_pts=21)
        scale = min(1.0, max_dim / max(src.width, src.height))
        width, height = max(1, int(src.width * scale)), max(1, int(src.height * scale))
        tr = from_bounds(*bounds, width, height)
        out = np.full((height, width), np.nan, np.float32)
        reproject(src.read(band), out, src_transform=src.transform, src_crs=src.crs,
                  dst_transform=tr, dst_crs="EPSG:4326", src_nodata=src.nodata, dst_nodata=np.nan,
                  resampling=resampling)
    return out, tr, list(bounds)


def save_rgba(arr, path, color, alpha=150, valid=None):
    rgba = np.zeros(arr.shape + (4,), np.uint8)
    mask = np.isfinite(arr) if valid is None else valid
    rgba[mask, :3] = color
    rgba[mask, 3] = alpha
    Image.fromarray(rgba, "RGBA").save(path)


def grayscale(arr, path, lo=-28, hi=2):
    x = np.clip((arr - lo) / (hi - lo), 0, 1)
    g = (255 * np.nan_to_num(x, nan=0)).astype(np.uint8)
    rgba = np.dstack([g, g, g, np.where(np.isfinite(arr), 255, 0).astype(np.uint8)])
    Image.fromarray(rgba, "RGBA").save(path)


def raster_assets():
    RASTERS.mkdir(parents=True, exist_ok=True)
    scenes = pd.read_csv(OUTPUTS / "nisar_scenes.csv")
    method = best_method()
    thr = json.loads((OUTPUTS / "thresholds.json").read_text())["unet_probability_threshold"]
    pair = json.loads((OUTPUTS / "change_pair.json").read_text())
    ts = pd.read_csv(OUTPUTS / "water_area_timeseries.csv")
    # DSWx references excluded from comparisons (outlier / partial coverage) are not offered as map layers
    excluded = {(d, int(t)) for d, t, why in zip(ts["date"], ts["track"], ts["dswx_excluded_reason"].fillna(""))
                if why} if "dswx_excluded_reason" in ts else set()
    entries = []
    for _, r in scenes.iterrows():
        tag = r.tag
        meta = {"date": r.date, "track": int(r.track), "direction": r.direction.lower()}
        hh, _, bounds = warp(r.nisar_tif, 1, resampling=Resampling.bilinear)
        name = f"{tag}_hh.png"
        grayscale(hh, RASTERS / name)
        entries.append({"id": f"{tag}_hh", "kind": "image", "layer": "nisar_hh_db", "file": f"rasters/{name}",
                        "bounds": bounds, **meta, "source": "NISAR GCOV frequency-A HHHH",
                        "style": "grayscale, -28 dB black to +2 dB white"})
        prob_path = BIG_OUT / f"prob_{slug(method)}_{tag}.tif"
        if prob_path.exists():
            p, _, bounds = warp(prob_path)
            name = f"{tag}_water.png"
            save_rgba(p, RASTERS / name, (38, 132, 255), 150, p >= thr)
            entries.append({"id": f"{tag}_water", "kind": "image", "layer": "model_water_mask", "file": f"rasters/{name}",
                            "bounds": bounds, **meta, "source": method,
                            "style": f"blue semi-transparent where water probability >= {thr}"})
        if isinstance(r.dswx_tif, str) and r.dswx_tif and (r.date, int(r.track)) not in excluded:
            d, _, bounds = warp(r.dswx_tif)
            water = d == 1
            edge = water & ~binary_erosion(water)
            name = f"{tag}_dswx_outline.png"
            save_rgba(d, RASTERS / name, (255, 255, 255), 230, edge)
            entries.append({"id": f"{tag}_dswx", "kind": "image", "layer": "dswx_water_outline", "file": f"rasters/{name}",
                            "bounds": bounds, **meta, "dswx_date": r.dswx_date, "source": "OPERA DSWx-HLS",
                            "style": "white outline of DSWx water (classes 1-2)"})
    for src, name in ((BIG_OUT / "change.tif", "change.png"),
                      (BIG_OUT / "uncertainty_pre.tif", "uncertainty_pre.png"),
                      (BIG_OUT / "uncertainty_post.tif", "uncertainty_post.png")):
        if not src.exists():
            continue
        band = 2 if "uncertainty" in name else 1
        a, _, bounds = warp(src, band)
        if "change" in name:
            rgba = np.zeros(a.shape + (4,), np.uint8)
            rgba[a == 1] = (31, 119, 180, 190)
            rgba[a == 2] = (214, 39, 40, 190)
            Image.fromarray(rgba, "RGBA").save(RASTERS / name)
        else:
            high = np.isfinite(a) & (a >= max(0.1, float(np.nanpercentile(a, 75))))
            save_rgba(a, RASTERS / name, (255, 170, 0), 170, high)
        stem = Path(name).stem
        layer = "change" if stem == "change" else "uncertainty"
        when = ({"period": {"start": pair["pre"]["date"], "end": pair["post"]["date"]}} if layer == "change"
                else {"date": pair[stem.split("_")[1]]["date"]})
        entries.append({"id": stem, "kind": "image", "layer": layer, "file": f"rasters/{name}",
                        "bounds": bounds, **when, "source": f"Water U-Net ({method})",
                        "style": ("blue gain, red loss" if layer == "change"
                                  else "orange where MC-dropout std is in the top quartile and >= 0.1")})
    (OUTPUTS / "raster_index.json").write_text(json.dumps({"crs": "EPSG:4326", "bounds_order":
        "[west,south,east,north] pixel outer edges", "layers": entries}, indent=2), encoding="utf-8")


def basemap(ax, bounds):
    ax.set_xlim(bounds[0], bounds[2]); ax.set_ylim(bounds[1], bounds[3])
    try:
        import contextily as cx
        cx.add_basemap(ax, crs="EPSG:4326", source=cx.providers.Esri.WorldImagery, attribution=False, zorder=0)
    except Exception as e:  # never silently ship a figure without its basemap
        print(f"WARNING basemap unavailable ({type(e).__name__}: {e}); figure has no satellite background")


def decorate(ax, bounds, title):
    import numpy as _np
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("longitude (°)"); ax.set_ylabel("latitude (°)")
    ax.set_aspect(1 / _np.cos(_np.radians((bounds[1] + bounds[3]) / 2)))
    ax.annotate("N", xy=(0.94, .95), xytext=(.94, .80), xycoords="axes fraction", textcoords="axes fraction",
                arrowprops={"arrowstyle": "-|>", "lw": 1.5, "color": "white"}, ha="center", color="white", weight="bold")
    lat = (bounds[1] + bounds[3]) / 2
    km_per_deg = 111.32 * _np.cos(_np.radians(lat))
    span_km = (bounds[2] - bounds[0]) * km_per_deg
    L = 5 if span_km > 12 else 2
    x0 = bounds[0] + 0.05 * (bounds[2] - bounds[0]); y0 = bounds[1] + 0.06 * (bounds[3] - bounds[1])
    ax.plot([x0, x0 + L / km_per_deg], [y0, y0], color="white", lw=4, solid_capstyle="butt")
    ax.text(x0 + L / km_per_deg / 2, y0 + 0.02 * (bounds[3] - bounds[1]), f"{L} km", color="white",
            ha="center", va="bottom", fontsize=8, weight="bold")


def overlay(ax, arr, bounds, rgba_lut):
    """arr: integer class raster; rgba_lut: {class: (r,g,b,a)} in 0-1."""
    img = _np.zeros(arr.shape + (4,))
    for k, c in rgba_lut.items():
        img[arr == k] = c
    ax.imshow(img, extent=(bounds[0], bounds[2], bounds[1], bounds[3]), origin="upper", zorder=2,
              interpolation="nearest")


def figures():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    FIGURES.mkdir(parents=True, exist_ok=True)
    pair = json.loads((OUTPUTS / "change_pair.json").read_text())
    held = json.loads((OUTPUTS / "heldout_eval.json").read_text())
    reservoir = held["reservoir"].replace("_", " ")
    BLUE, RED = (0.15, 0.52, 1.0, 0.65), (0.84, 0.15, 0.16, 0.9)

    w0, _, b0 = warp(BIG_OUT / "water_pre.tif")
    w1, _, b1 = warp(BIG_OUT / "water_post.tif")
    ch, _, bc = warp(BIG_OUT / "change.tif")
    fig, ax = plt.subplots(1, 3, figsize=(16, 5.6))
    for a, w, b, lab in ((ax[0], w0, b0, f"Before: {pair['pre']['date']} ({pair['water_pre_km2']:.1f} km²)"),
                         (ax[1], w1, b1, f"After: {pair['post']['date']} ({pair['water_post_km2']:.1f} km²)")):
        basemap(a, b); overlay(a, w, b, {1: BLUE}); decorate(a, b, lab)
    basemap(ax[2], bc); overlay(ax[2], ch, bc, {1: (0.12, 0.47, 0.71, 0.95), 2: RED})
    decorate(ax[2], bc, f"Change: gain {pair['gain_km2']:.2f} km², loss {pair['loss_km2']:.2f} km²")
    ax[0].legend(handles=[Patch(color=BLUE, label="NISAR water (U-Net)")], loc="upper left", fontsize=8)
    ax[2].legend(handles=[Patch(color=(0.12, 0.47, 0.71), label="gain (water after, not before)"),
                          Patch(color=RED[:3], label="loss (water before, not after)")], loc="upper left", fontsize=8)
    fig.suptitle(f"{reservoir}: NISAR L-band water extent, track {pair['pre']['tag'].split('_T')[1][:4]}", fontsize=12)
    fig.text(.01, .01, "Basemap: Esri World Imagery · " + CREDIT, fontsize=8)
    fig.tight_layout(rect=[0, .03, 1, .95]); fig.savefig(FIGURES / "hero.png", dpi=300); plt.close(fig)

    ts = pd.read_csv(OUTPUTS / "water_area_timeseries.csv")
    fig, ax = plt.subplots(figsize=(10, 5))
    for (track, direction), g in ts.groupby(["track", "direction"]):
        g = g.sort_values("date")
        role = "selection" if track == held["selection_track"] else "held-out"
        ax.plot(pd.to_datetime(g.date), g.model_water_km2, "o-", label=f"NISAR T{track} {direction.lower()} ({role})")
        w = g.flag.fillna("").str.contains("wind")
        if w.any():
            ax.scatter(pd.to_datetime(g.loc[w, "date"]), g.loc[w, "model_water_km2"], s=180, facecolors="none",
                       edgecolors="red", linewidths=1.5, zorder=5)
    d = ts.dropna(subset=["dswx_water_km2"]).drop_duplicates("dswx_date").sort_values("dswx_date")
    ax.plot(pd.to_datetime(d.dswx_date), d.dswx_water_km2, "ks--", alpha=.65, label="OPERA DSWx (clear, outliers removed)")
    ax.scatter([], [], s=180, facecolors="none", edgecolors="red", label="possible wind effect (>20% drop)")
    b = held["area_bias"]["held-out raw"]
    ax.set(ylabel="water area (km²)",
           title=f"{reservoir} water area by orbit ({held['variant_selected_on_selection_track']}); "
                 f"held-out bias {b['mean_km2']:+.2f} km² [{b['ci95_km2'][0]:+.2f}, {b['ci95_km2'][1]:+.2f}]")
    ax.title.set_fontsize(10)
    ax.grid(alpha=.25); ax.legend(fontsize=8, loc="lower left"); fig.text(.01, .01, CREDIT, fontsize=8)
    fig.tight_layout(rect=[0, .03, 1, 1]); fig.savefig(FIGURES / "timeseries.png", dpi=300); plt.close(fig)

    # validation: held-out track, the date with the MEDIAN IoU (not the best one)
    method = best_method()
    hp = pd.read_csv(OUTPUTS / "heldout_per_date.csv")
    hp = hp[hp["set"] == "held-out"].sort_values(f"iou|{method}")
    row = hp.iloc[len(hp) // 2]
    scenes = pd.read_csv(OUTPUTS / "nisar_scenes.csv").set_index("tag")
    prob, _, bounds = warp(BIG_OUT / f"prob_{slug(method)}_{row.tag}.tif")
    ref, _, _ = warp(scenes.loc[row.tag].dswx_tif)
    thr = held["probability_threshold"]
    pred, truth, rv = prob >= thr, ref == 1, ref != 255
    view = np.zeros(pred.shape, np.uint8)
    view[truth & pred & rv] = 1; view[truth & ~pred & rv] = 2; view[~truth & pred & rv] = 3
    fig, ax = plt.subplots(figsize=(8, 6.5))
    basemap(ax, bounds)
    overlay(ax, view, bounds, {1: (1, 1, 1, .85), 2: (0.84, 0.15, 0.16, .95), 3: (1, 0.55, 0, .95)})
    decorate(ax, bounds, f"{reservoir} {row.date}, held-out track {int(row.track)}: U-Net vs OPERA DSWx "
                         f"{row.dswx_date}\nIoU {row[f'iou|{method}']:.3f} (median held-out date)")
    ax.legend(handles=[Patch(color="white", label="agreement (water in both)"), Patch(color="#d62728", label="miss (DSWx only)"),
                       Patch(color="#ff8c00", label="false alarm (NISAR only)")], loc="upper left", fontsize=8)
    fig.text(.01, .01, "Basemap: Esri World Imagery · " + CREDIT, fontsize=8)
    fig.tight_layout(rect=[0, .03, 1, 1]); fig.savefig(FIGURES / "validation.png", dpi=300); plt.close(fig)

    frames = []
    ordered = scenes.reset_index().query("track == @held['selection_track']").sort_values("date")
    first_path = BIG_OUT / f"prob_{slug(method)}_{ordered.iloc[0].tag}.tif"
    _, frame_transform, frame_bounds = warp(first_path, max_dim=900)
    frame_width = 900
    frame_height = max(1, int(900 * (frame_bounds[3] - frame_bounds[1]) /
                              (frame_bounds[2] - frame_bounds[0])))
    frame_transform = from_bounds(*frame_bounds, frame_width, frame_height)
    for _, r in ordered.iterrows():
        p = BIG_OUT / f"prob_{slug(method)}_{r.tag}.tif"
        if not p.exists(): continue
        a = np.full((frame_height, frame_width), np.nan, np.float32)
        with rasterio.open(p) as src:
            reproject(src.read(1), a, src_transform=src.transform, src_crs=src.crs,
                      dst_transform=frame_transform, dst_crs="EPSG:4326",
                      src_nodata=src.nodata, dst_nodata=np.nan,
                      resampling=Resampling.nearest)
        im = np.zeros(a.shape + (3,), np.uint8); im[a >= .4] = (38, 132, 255)
        img = Image.fromarray(im)
        ImageDraw.Draw(img).text((12, 12), f"{reservoir} | T{r.track} | {r.date} | U-Net water",
                                 fill="white", stroke_width=2, stroke_fill="black")
        frames.append(np.asarray(img))
    if frames:
        imageio.mimsave(FIGURES / "timelapse.gif", frames, duration=1000, loop=0)

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set(xlim=(-13.5, -1), ylim=(27, 36.5), xlabel="longitude", ylabel="latitude", title=f"{reservoir}, Morocco")
    bb = json.loads((OUTPUTS / "aoi.json").read_text())["aois"][held["reservoir"]]["bbox"]
    ax.scatter([(bb[0] + bb[2]) / 2], [(bb[1] + bb[3]) / 2], marker="*", s=220, color="#2684ff", edgecolor="white", zorder=5)
    try:
        import contextily as cx
        cx.add_basemap(ax, crs="EPSG:4326", source=cx.providers.Esri.WorldImagery, attribution=False)
    except Exception: pass
    fig.text(.01, .01, CREDIT, fontsize=8); fig.tight_layout(rect=[0, .03, 1, 1])
    fig.savefig(FIGURES / "locator.png", dpi=300); plt.close(fig)


def main():
    raster_assets()
    figures()
    print("wrote", OUTPUTS / "raster_index.json", "and", FIGURES)


if __name__ == "__main__":
    main()

