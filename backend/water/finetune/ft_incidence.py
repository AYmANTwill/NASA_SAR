"""v3 input: per-pixel radar incidence angle (degrees) for every scene, on the scene's own grid.

Source: GCOV /science/LSAR/GCOV/metadata/radarGrid/incidenceAngle, a coarse cube (height x y x x) in the same
projection as the backscatter grid. The height level closest to H_REF is read over the scene box only (a few
hundred kB) and interpolated bilinearly onto the scene pixels. No labels are involved.
Scenes: fine-tuning dataset (outputs/finetune/dataset.csv) and the case reservoir scenes (outputs/nisar_scenes.csv).
Writes NASA_DATA/finetune/incidence/<tag>_inc.tif and outputs/finetune/incidence.csv.
Usage: python finetune/ft_incidence.py [--workers 3]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from common import DATA, OUTPUTS, dpath, rel  # noqa: E402

FT_OUT = OUTPUTS / "finetune"
INC_DIR = DATA / "finetune" / "incidence"
RG = "/science/LSAR/GCOV/metadata/radarGrid"
H_REF = 500.0  # m above the ellipsoid; incidence changes by well under 0.1 deg per 100 m of height
BLOCK = 4 * 2**20


def _job(tag: str, nisar_tif: str, url: str) -> dict:
    import h5py
    import rasterio
    from scipy.interpolate import RegularGridInterpolator

    from common import https_fs
    from nisar_prep import epsg_of, write_tif

    out = INC_DIR / f"{tag}_inc.tif"
    rec = {"tag": tag, "inc_tif": rel(out)}
    if out.exists():
        return {**rec, "cached": True}
    with rasterio.open(dpath(nisar_tif)) as s:
        tr, h, w, epsg_scene = s.transform, s.height, s.width, s.crs.to_epsg()
    xs = tr.c + tr.a * (np.arange(w) + 0.5)
    ys = tr.f + tr.e * (np.arange(h) + 0.5)
    last = None
    for attempt in range(3):
        try:
            fs = https_fs()
            t0 = time.perf_counter()
            with fs.open(url, "rb", block_size=BLOCK, cache_type="blockcache") as f, h5py.File(f, "r") as h5:
                if epsg_of(h5) != epsg_scene:
                    return {**rec, "error": f"EPSG mismatch {epsg_of(h5)} vs {epsg_scene}"}
                gx, gy, hh = h5[f"{RG}/xCoordinates"][()], h5[f"{RG}/yCoordinates"][()], h5[f"{RG}/heightAboveEllipsoid"][()]
                k = int(np.argmin(np.abs(hh - H_REF)))
                c = np.where((gx >= xs.min()) & (gx <= xs.max()))[0]
                r = np.where((gy >= min(ys)) & (gy <= max(ys)))[0]
                c0, c1 = max(c.min() - 2, 0), min(c.max() + 3, len(gx))
                r0, r1 = max(r.min() - 2, 0), min(r.max() + 3, len(gy))
                cube = h5[f"{RG}/incidenceAngle"][k, r0:r1, c0:c1].astype(np.float64)
            sx, sy = gx[c0:c1], gy[r0:r1]
            if sy[0] > sy[-1]:
                sy, cube = sy[::-1], cube[::-1]
            if sx[0] > sx[-1]:
                sx, cube = sx[::-1], cube[:, ::-1]
            f_int = RegularGridInterpolator((sy, sx), cube, method="linear", bounds_error=False, fill_value=None)
            yy, xx = np.meshgrid(ys, xs, indexing="ij")
            inc = f_int(np.stack([yy.ravel(), xx.ravel()], 1)).reshape(h, w).astype(np.float32)
            out.parent.mkdir(parents=True, exist_ok=True)
            write_tif(out, inc, epsg_scene, tr, np.nan, "float32", ["incidence_angle_deg"])
            return {**rec, "read_s": round(time.perf_counter() - t0, 1), "height_m": float(hh[k]),
                    "inc_min": float(np.nanmin(inc)), "inc_mean": float(np.nanmean(inc)), "inc_max": float(np.nanmax(inc))}
        except Exception as e:  # transient network errors
            last = f"{type(e).__name__}: {str(e)[:160]}"
            time.sleep(10 * (attempt + 1))
    return {**rec, "error": last}


def scenes() -> pd.DataFrame:
    ds = pd.read_csv(FT_OUT / "dataset.csv")
    cand = pd.read_csv(FT_OUT / "candidates.csv")[["site", "date", "track", "direction", "h5_url"]]
    cand["tag"] = cand["site"] + "_T" + cand["track"].map("{:03d}".format) + cand["direction"].str[0] + "_" + cand["date"]
    a = ds.merge(cand[["tag", "h5_url"]].drop_duplicates("tag"), on="tag", how="left")[["tag", "nisar_tif", "h5_url"]]
    held = json.loads((OUTPUTS / "aoi.json").read_text())["chosen"]["reservoir"]
    ns = pd.read_csv(OUTPUTS / "nisar_scenes.csv")
    cs = pd.read_csv(OUTPUTS / "candidate_scenes.csv")
    cs = cs[(cs["reservoir"] == held) & cs["usable"]][["date", "track", "h5_url"]]
    b = ns.merge(cs, on=["date", "track"], how="left", validate="one_to_one")[["tag", "nisar_tif", "h5_url"]]
    parts = [a, b]
    hz = OUTPUTS / "haouz_scenes.csv"  # Haouz pre/post scenes (haouz_flood.py naming)
    if hz.exists():
        h = pd.read_csv(hz)
        h["tag"] = "Haouz_T" + h["track"].map("{:03d}".format) + h["direction"].str[0] + "_" + h["period"] + "_" + h["date"]
        h["nisar_tif"] = "$NASA_DATA/nisar/haouz/" + h["tag"] + ".tif"
        h = h[[dpath(p).exists() for p in h["nisar_tif"]]]
        parts.append(h[["tag", "nisar_tif", "h5_url"]])
    return pd.concat(parts, ignore_index=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    sc = scenes()
    missing = sc["h5_url"].isna()
    if missing.any():
        print("no h5 url for:", sc.loc[missing, "tag"].tolist())
    sc = sc[~missing]
    rows = []
    with ProcessPoolExecutor(a.workers) as ex:
        futs = [ex.submit(_job, r.tag, r.nisar_tif, r.h5_url) for r in sc.itertuples()]
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result(); rows.append(r)
            print(f"[{i}/{len(futs)}] {r['tag']} " + ("cached" if r.get("cached") else r.get("error") or
                  f"{r['inc_min']:.1f}-{r['inc_max']:.1f} deg (mean {r['inc_mean']:.1f}), {r['read_s']} s"), flush=True)
    log = pd.DataFrame(rows)
    old = FT_OUT / "incidence.csv"
    if old.exists():
        log = pd.concat([pd.read_csv(old), log], ignore_index=True).drop_duplicates("tag", keep="last")
    log.to_csv(old, index=False)
    bad = log["error"].notna().sum() if "error" in log else 0
    print(f"incidence rasters: {len(log) - bad} ok, {bad} failed")
    if bad > 0.05 * len(log):
        sys.exit("more than 5% of incidence reads failed")


if __name__ == "__main__":
    main()
