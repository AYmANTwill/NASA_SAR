"""Diagnose the reservoir water mask against SAME-DATE optical imagery (no model changes).

For key NISAR dates, the HLS scene that the matched OPERA DSWx was computed from is read remotely
(window only, authenticated range requests), reprojected onto the NISAR 10 m grid and used as the
basemap. Outputs (no number typed by hand; everything goes to outputs/diagnostics.json):
  - outputs/figures/diagnostic_<date>.png: (a) same-date HLS true colour, (b) our mask over (a),
    (c) DSWx outline over (a), (d) our mask vs DSWx (white agree, red miss, orange false alarm)
  - alignment: shift (metres) maximising IoU of our mask vs DSWx and vs HLS MNDWI water, and
    phase correlation of NISAR HH vs HLS NIR (classifier-independent)
  - false alarms on every clear date: our water where DSWx says land, split into shoreline
    (<= 30 m from DSWx water), exposed lakebed (inside the season's maximum DSWx water extent),
    steep slope (> 15 deg, layover/shadow-prone, from the DSWx DEM layer) and other land;
    on key dates also restricted to pixels where same-date HLS MNDWI says land
  - Esri World Imagery source dates at sample points (basemap used in earlier figures)
Usage: python diagnose_mask.py
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import from_bounds
from scipy.ndimage import binary_erosion, distance_transform_edt, uniform_filter

from common import BIG_OUT, DATA, OUTPUTS, dpath, retry
from evaluate import slug
from timeseries import best_method

from nisar_search import CMR  # public CMR granule search endpoint (defined once)
KEY_TAGS = None  # default: hero pair + validation date (from change_pair.json / validation choice)
SHORE_PX = 3      # 30 m on the 10 m grid = one DSWx pixel
SLOPE_DEG = 15.0
HLS_DIR = DATA / "hls"


def esri_dates(points):
    out = []
    for lon, lat in points:
        u = ("https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/identify"
             f"?geometry={lon},{lat}&geometryType=esriGeometryPoint&sr=4326&layers=all&tolerance=1"
             "&mapExtent=-6.5,32.0,-6.3,32.2&imageDisplay=800,800,96&returnGeometry=false&f=json")
        try:
            a = retry(lambda: requests.get(u, timeout=60).json(), tries=3, base_wait=5)["results"][0]["attributes"]
            out.append({"lon": lon, "lat": lat, "date": a.get("DATE (YYYYMMDD)"), "sensor": a.get("DESCRIPTION"),
                        "resolution_m": a.get("RESOLUTION (M)"), "accuracy_m": a.get("ACCURACY (M)")})
        except Exception as e:
            out.append({"lon": lon, "lat": lat, "error": str(e)[:80]})
    return out


def hls_urls(day: str, tile: str, sensor: str, bbox):
    short = "HLSS30" if sensor.startswith("S2") else "HLSL30"
    r = retry(lambda: requests.get(CMR, params={"short_name": short, "bounding_box": ",".join(map(str, bbox)),
                                                "temporal": f"{day}T00:00:00Z,{day}T23:59:59Z", "page_size": 50},
                                   timeout=60).json())
    for it in r["items"]:
        if f".{tile}." in it["umm"]["GranuleUR"]:
            urls = {x["URL"].rsplit(".", 2)[-2]: x["URL"] for x in it["umm"]["RelatedUrls"]
                    if x["URL"].startswith("https") and x["URL"].endswith(".tif")}
            nir = "B8A" if short == "HLSS30" else "B05"
            swir = "B11" if short == "HLSS30" else "B06"
            return it["umm"]["GranuleUR"], {"red": urls["B04"], "green": urls["B03"], "blue": urls["B02"],
                                            "nir": urls[nir], "swir1": urls[swir], "fmask": urls["Fmask"]}
    raise SystemExit(f"no {short} granule for tile {tile} on {day}")


def read_to_grid(url, fs, dst_crs, dst_transform, shape, resampling):
    def _read():
        with rasterio.open(url, opener=fs.open) as src:
            bb = transform_bounds(dst_crs, src.crs, *rasterio.transform.array_bounds(*shape, dst_transform))
            w = from_bounds(*bb, transform=src.transform).round_offsets().round_lengths()
            w = w.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
            a = src.read(1, window=w).astype(np.float32)
            nod = src.nodata
            if nod is not None:
                a[a == nod] = np.nan
            out = np.full(shape, np.nan, np.float32)
            reproject(a, out, src_transform=src.window_transform(w), src_crs=src.crs, src_nodata=np.nan,
                      dst_transform=dst_transform, dst_crs=dst_crs, dst_nodata=np.nan, resampling=resampling)
            return out
    return retry(_read, tries=4, base_wait=15, what=url.rsplit("/", 1)[-1])


def hls_on_grid(tag, row, fs, crs, transform, shape, bbox):
    cache = HLS_DIR / f"{tag}_hls.npz"
    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        return {k: z[k] for k in z.files if k != "granule"}, str(z["granule"])
    gran, urls = hls_urls(row["dswx_date"], row["tiles"].split("+")[0], row["sensor"], bbox)
    bands = {}
    for k, u in urls.items():
        rs = Resampling.nearest if k == "fmask" else Resampling.bilinear
        bands[k] = read_to_grid(u, fs, crs, transform, shape, rs)
        print(f"   {tag} {k} ok", flush=True)
    HLS_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, granule=gran, **{k: v.astype(np.float32) for k, v in bands.items()})
    return bands, gran


def truecolor(b):
    rgb = np.dstack([b["red"], b["green"], b["blue"]]) * 1e-4
    v = rgb[np.isfinite(rgb)]
    lo, hi = np.percentile(v, [2, 98]) if v.size else (0, 0.3)
    return np.clip(np.nan_to_num((rgb - lo) / (hi - lo)), 0, 1)


def shift_iou(a, b, rng=10):
    """IoU of a shifted by (dy, dx) against b, over the common interior; returns best (dy, dx) subpixel."""
    h, w = a.shape
    best, grid = None, np.full((2 * rng + 1, 2 * rng + 1), np.nan)
    core_b = b[rng:h - rng, rng:w - rng]
    for i, dy in enumerate(range(-rng, rng + 1)):
        for j, dx in enumerate(range(-rng, rng + 1)):
            sa = a[rng + dy:h - rng + dy, rng + dx:w - rng + dx]
            inter, union = (sa & core_b).sum(), (sa | core_b).sum()
            grid[i, j] = inter / max(union, 1)
    i, j = np.unravel_index(np.nanargmax(grid), grid.shape)

    def parab(v, k):
        if 0 < k < len(v) - 1:
            d = v[k - 1] - 2 * v[k] + v[k + 1]
            return k + (0.5 * (v[k - 1] - v[k + 1]) / d if d != 0 else 0)
        return k
    sy, sx = parab(grid[:, j], i) - rng, parab(grid[i, :], j) - rng
    return sy, sx, float(grid[i, j]), float(grid[rng, rng])


def slope_deg(dem, res):
    gy, gx = np.gradient(np.nan_to_num(dem, nan=np.nanmedian(dem)), res)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def main() -> None:
    import earthaccess
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    earthaccess.login(strategy="environment")
    fs = earthaccess.get_fsspec_https_session()
    held = json.loads((OUTPUTS / "heldout_eval.json").read_text())
    method, thr = held["variant_selected_on_selection_track"], held["probability_threshold"]
    aoi = json.loads((OUTPUTS / "aoi.json").read_text())
    res = aoi["chosen"]["reservoir"]
    bbox = aoi["aois"][res]["bbox"]
    scenes = pd.read_csv(OUTPUTS / "nisar_scenes.csv").set_index("tag")
    cand = pd.read_csv(OUTPUTS / "candidate_scenes.csv")
    cand = cand[(cand["reservoir"] == res) & cand["usable"]].set_index(["date", "track"])
    hp = pd.read_csv(OUTPUTS / "heldout_per_date.csv")
    pair = json.loads((OUTPUTS / "change_pair.json").read_text())
    hv = hp[hp["set"] == "held-out"].sort_values(f"iou|{method}")
    val_tag = hv.iloc[len(hv) // 2]["tag"]
    key = [pair["pre"]["tag"], pair["post"]["tag"], val_tag]

    def load(tag):
        sc = scenes.loc[tag]
        with rasterio.open(BIG_OUT / f"prob_{slug(method)}_{tag}.tif") as s:
            prob, crs, tr = s.read(1), s.crs, s.transform
        with rasterio.open(dpath(sc.dswx_tif)) as s:
            ref = s.read(1)
        with rasterio.open(dpath(sc.nisar_tif)) as s:
            hh = s.read(1)
        valid = np.isfinite(prob) & (ref != 255)
        return {"ours": np.nan_to_num(prob) >= thr, "dswx": ref == 1, "valid": valid, "hh": hh,
                "crs": crs, "tr": tr, "shape": prob.shape}

    # DEM (DSWx B10_DEM of the first key scene's DSWx granule), once per grid
    first = load(key[0])
    d0 = cand.loc[(scenes.loc[key[0]].date, int(scenes.loc[key[0]].track))]
    dem_url = d0["wtr_urls"].split(";")[0].replace("_B01_WTR.tif", "_B10_DEM.tif")
    dem_cache = HLS_DIR / "dem_grid.npz"
    if dem_cache.exists():
        dem = np.load(dem_cache)["dem"]
    else:
        dem = read_to_grid(dem_url, fs, first["crs"], first["tr"], first["shape"], Resampling.bilinear)
        HLS_DIR.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(dem_cache, dem=dem)
    px = abs(first["tr"].a)

    out = {"method": method, "probability_threshold": thr,
           "esri_world_imagery_sources": esri_dates([(-6.42, 32.10), (-6.36, 32.13), (-6.35, 32.10),
                                                     (-6.46, 32.09), (-6.43, 32.065), (-6.475, 32.105)]),
           "key_dates": [], "false_alarms_all_clear_dates": []}

    # season maximum DSWx water extent per track grid (clear, used dates only)
    used = hp[hp["use"]] if "use" in hp else hp
    season_max = {}
    for trk, g in used.groupby("track"):
        acc = None
        for tag in g["tag"]:
            with rasterio.open(dpath(scenes.loc[tag].dswx_tif)) as s:
                w = s.read(1) == 1
            acc = w if acc is None else (acc | w)
        season_max[int(trk)] = acc

    def categorize(d, extra_land=None):
        fa = d["ours"] & ~d["dswx"] & d["valid"]
        if extra_land is not None:
            fa &= extra_land
        miss = ~d["ours"] & d["dswx"] & d["valid"]
        dist = distance_transform_edt(~d["dswx"])
        shore = fa & (dist <= SHORE_PX)
        lake = fa & ~shore & d["smax"]
        steep = fa & ~shore & ~lake & (d["slope"] > SLOPE_DEG)
        other = fa & ~shore & ~lake & ~steep
        k = px * px / 1e6
        return {"false_alarm_km2": float(fa.sum() * k), "miss_km2": float(miss.sum() * k),
                "net_fa_minus_miss_km2": float((fa.sum() - miss.sum()) * k),
                "shoreline_km2": float(shore.sum() * k), "exposed_lakebed_km2": float(lake.sum() * k),
                "steep_slope_km2": float(steep.sum() * k), "other_land_km2": float(other.sum() * k)}, \
            {"fa": fa, "shore": shore, "lake": lake, "steep": steep, "other": other}

    slope = slope_deg(dem, px)
    slope_by_track = {}

    def track_slope(trk, d):
        """Per-track DEM (cached by fix_slope_eval / water_level_eval as dem_T<track>.npz)."""
        if trk not in slope_by_track:
            f = HLS_DIR / f"dem_T{trk:03d}.npz"
            dm = np.load(f)["dem"] if f.exists() else None
            if dm is None or dm.shape != d["shape"]:
                dm = dem if d["shape"] == first["shape"] else None
            slope_by_track[trk] = slope_deg(dm, px) if dm is not None else None
        return slope_by_track[trk]

    for _, r in used.iterrows():
        d = load(r["tag"])
        sl = track_slope(int(r["track"]), d)
        if sl is None:
            continue  # no DEM on this grid
        d["slope"], d["smax"] = sl, season_max[int(r["track"])]
        stats, _ = categorize(d)
        out["false_alarms_all_clear_dates"].append({"tag": r["tag"], "set": r["set"], "track": int(r["track"]), **stats})
    out["false_alarm_summary_by_track"] = None  # filled below

    for tag in key:
        sc = scenes.loc[tag]
        crow = cand.loc[(sc.date, int(sc.track))]
        d = load(tag)
        sl = track_slope(int(sc.track), d)
        d["slope"], d["smax"] = (sl if sl is not None else np.zeros(d["shape"])), season_max[int(sc.track)]
        bands, gran = hls_on_grid(tag, crow, fs, d["crs"], d["tr"], d["shape"], bbox)
        fm = np.nan_to_num(bands["fmask"], nan=255).astype(np.uint16)
        clear = np.isfinite(bands["green"]) & ((fm & 0b1110) == 0)  # bits 1-3: cloud, adjacent, shadow
        mndwi = (bands["green"] - bands["swir1"]) / (bands["green"] + bands["swir1"])
        opt_water = clear & (mndwi > 0)
        opt_land = clear & (mndwi <= 0)
        stats_all, _ = categorize(d)
        stats_both, cat = categorize(d, extra_land=opt_land)
        # alignment
        sy, sx, iou_best, iou0 = shift_iou(d["ours"] & d["valid"], d["dswx"] & d["valid"])
        oy, ox, oiou, oiou0 = shift_iou(d["ours"] & clear, opt_water)
        from skimage.registration import phase_cross_correlation
        nir = np.nan_to_num(bands["nir"], nan=np.nanmedian(bands["nir"]))
        hhs = uniform_filter(np.nan_to_num(d["hh"], nan=np.nanmedian(d["hh"])), 3)
        z = lambda a: (a - a.mean()) / (a.std() + 1e-9)
        (py, pxx), err, _ = phase_cross_correlation(z(nir), z(hhs), upsample_factor=10)
        item = {"tag": tag, "nisar_date": sc.date, "track": int(sc.track), "hls_granule": gran,
                "dswx_date": crow["dswx_date"], "hls_clear_frac": float(clear.mean()),
                "false_alarms_vs_dswx": stats_all, "false_alarms_vs_dswx_and_hls_mndwi_land": stats_both,
                "alignment_m": {
                    "ours_vs_dswx_shift_east_north": [round(sx * px, 1), round(-sy * px, 1)],
                    "ours_vs_dswx_iou_at_best_vs_zero_shift": [round(iou_best, 4), round(iou0, 4)],
                    "ours_vs_hls_mndwi_shift_east_north": [round(ox * px, 1), round(-oy * px, 1)],
                    "ours_vs_hls_mndwi_iou_at_best_vs_zero_shift": [round(oiou, 4), round(oiou0, 4)],
                    "nisar_hh_vs_hls_nir_phase_corr_east_north": [round(-pxx * px, 1), round(py * px, 1)],
                    "pixel_m": px}}
        out["key_dates"].append(item)

        tc = truecolor(bands)
        tr = d["tr"]
        h, w = d["shape"]
        ext = (tr.c, tr.c + w * tr.a, tr.f + h * tr.e, tr.f)
        fig, ax = plt.subplots(2, 2, figsize=(14, 10))
        ax = ax.ravel()
        ax[0].imshow(tc, extent=ext)
        ax[0].set_title(f"(a) HLS true colour {crow['dswx_date']} ({crow['sensor']}), same scene as DSWx", fontsize=9)
        ax[1].imshow(tc, extent=ext)
        m = np.zeros((h, w, 4)); m[d["ours"] & d["valid"]] = (0.10, 0.45, 1.0, 0.75)
        ax[1].imshow(m, extent=ext, interpolation="nearest")
        ax[1].set_title(f"(b) our water mask, NISAR {sc.date} T{int(sc.track)} (one colour = water)", fontsize=9)
        ax[1].legend(handles=[Patch(color=(0.10, 0.45, 1.0), label="NISAR U-Net water")], loc="lower left", fontsize=8)
        ax[2].imshow(tc, extent=ext)
        e = d["dswx"] & ~binary_erosion(d["dswx"], iterations=1)
        o = np.zeros((h, w, 4)); o[e] = (1, 1, 0, 1)
        ax[2].imshow(o, extent=ext, interpolation="nearest")
        ax[2].set_title("(c) OPERA DSWx water outline (yellow) over (a)", fontsize=9)
        ax[3].imshow(tc, extent=ext)
        v = np.zeros((h, w, 4))
        v[d["ours"] & d["dswx"] & d["valid"]] = (1, 1, 1, .85)
        v[~d["ours"] & d["dswx"] & d["valid"]] = (.84, .15, .16, .95)
        v[d["ours"] & ~d["dswx"] & d["valid"]] = (1, .55, 0, .95)
        ax[3].imshow(v, extent=ext, interpolation="nearest")
        ax[3].set_title(f"(d) ours vs DSWx: false alarm {stats_all['false_alarm_km2']:.2f} km², miss {stats_all['miss_km2']:.2f} km²",
                        fontsize=9)
        ax[3].legend(handles=[Patch(color="white", label="agreement"), Patch(color="#d62728", label="miss (DSWx only)"),
                              Patch(color="#ff8c00", label="false alarm (NISAR only)")], loc="lower left", fontsize=8)
        for a in ax:
            a.set_xticks([]); a.set_yticks([])
        fig.suptitle(f"{res.replace('_', ' ')}: diagnostic for NISAR {sc.date} (track {int(sc.track)}) with same-date optical "
                     f"basemap · HLS {gran}", fontsize=10)
        fig.text(.01, .005, "HLS (NASA LP DAAC), OPERA DSWx (NASA/JPL), NISAR (NASA/ISRO); UTM 29N, 10 m grid", fontsize=7)
        fig.tight_layout(rect=[0, .02, 1, .96])
        fig.savefig(OUTPUTS / "figures" / f"diagnostic_{sc.date}.png", dpi=150)
        plt.close(fig)
        print(f"wrote diagnostic_{sc.date}.png", flush=True)

    fa = pd.DataFrame(out["false_alarms_all_clear_dates"])
    if len(fa):
        out["false_alarm_summary_by_track"] = fa.groupby("track")[[c for c in fa.columns if c.endswith("_km2")]].mean().round(3).to_dict("index")
        out["false_alarm_summary_by_set"] = fa.groupby("set")[[c for c in fa.columns if c.endswith("_km2")]].mean().round(3).to_dict("index")
    (OUTPUTS / "diagnostics.json").write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps({k: out[k] for k in ("esri_world_imagery_sources", "false_alarm_summary_by_set") if k in out}, indent=1, default=float))
    for k in out["key_dates"]:
        print(k["tag"], json.dumps(k["alignment_m"], default=float), json.dumps(k["false_alarms_vs_dswx_and_hls_mndwi_land"], default=float))


if __name__ == "__main__":
    main()
