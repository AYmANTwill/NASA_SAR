"""Step 6: NISAR GCOV subset extraction (remote, no full-granule download) + DSWx reference.

Needs credentials from the process environment or the external token file loaded by common.py.

Per NISAR date of the chosen (track, frame, direction):
  - open the .h5 remotely (earthaccess.open -> fsspec file) with h5py
  - read only the AOI window of frequencyA HHHH and HVHV (+ mask)
  - Lee 5x5 filter in linear power, then 10*log10 (<=0 / NaN masked)
  - write NASA_DATA/nisar/<reservoir>_<date>.tif (2 bands: HH_dB, HV_dB)
  - read the matched DSWx WTR COG window(s) remotely with rasterio, reproject (nearest) onto
    that grid, map to 1 water / 0 not-water / 255 masked, write NASA_DATA/dswx/<reservoir>_<date>.tif

Layout documented at https://nisar-docs.asf.alaska.edu/gcov :
  /science/LSAR/GCOV/grids/frequencyA/{HHHH,HVHV,mask,numberOfLooks}
Coordinate / projection dataset names are discovered from the file (printed with --tree).

Usage:
  python src/nisar_prep.py --check-login
  python src/nisar_prep.py --tree            # print HDF5 tree of the first granule (metadata only)
  python src/nisar_prep.py --limit 1         # one date first
  python src/nisar_prep.py                   # all dates of the chosen track
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from common import DATA, OUTPUTS, check_budget, dir_size, rel, retry

GRID = "/science/LSAR/GCOV/grids/frequencyA"
NISAR_DIR = DATA / "nisar"
DSWX_DIR = DATA / "dswx"


# ---------------------------------------------------------------- auth
def login():
    import earthaccess

    try:
        auth = earthaccess.login(strategy="environment")
        if auth and auth.authenticated:
            print("Earthdata login OK via environment")
            return auth
    except Exception:
        pass
    raise SystemExit("STOP: Earthdata token unavailable or rejected; refresh the external token file, then rerun.")


# ---------------------------------------------------------------- helpers
def lee_filter(img: np.ndarray, size: int = 5) -> np.ndarray:
    """Classic Lee filter on linear power; NaNs ignored (normalized convolution)."""
    from scipy.ndimage import uniform_filter

    valid = np.isfinite(img)
    x = np.where(valid, img, 0.0).astype(np.float64)
    w = uniform_filter(valid.astype(np.float64), size)
    w_safe = np.maximum(w, 1e-6)
    mean = uniform_filter(x, size) / w_safe
    sq = uniform_filter(x * x, size) / w_safe
    var = np.maximum(sq - mean**2, 0)
    noise = np.nanmean(var[valid] / np.maximum(mean[valid], 1e-12) ** 2) if valid.any() else 0
    var_x = np.maximum((var - noise * mean**2) / (1 + noise), 0)
    k = var_x / np.maximum(var, 1e-12)
    out = mean + k * (x - mean)
    out[~valid] = np.nan
    return out.astype(np.float32)


def to_db(p: np.ndarray) -> np.ndarray:
    p = np.where(np.isfinite(p) & (p > 0), p, np.nan)
    return (10 * np.log10(p)).astype(np.float32)


def find(h5, names: list[str], under: str = GRID):
    """Find the first dataset whose basename is in names under a group (layout discovery)."""
    found = []

    def visit(n, obj):
        if hasattr(obj, "shape") and n.split("/")[-1] in names:
            found.append(n)

    h5[under].visititems(visit)
    return under + "/" + sorted(found, key=len)[0] if found else None


def epsg_of(h5) -> int:
    for cand in (f"{GRID}/projection", "/science/LSAR/GCOV/grids/frequencyA/projection"):
        if cand in h5:
            d = h5[cand]
            for key in ("epsg_code", "epsg"):
                if key in d.attrs:
                    return int(np.asarray(d.attrs[key]).ravel()[0])
            v = np.asarray(d[()]).ravel()
            if v.size == 1 and 1000 < int(v[0]) < 100000:
                return int(v[0])
    raise KeyError("projection / EPSG not found; run --tree and update epsg_of()")


def print_tree(h5, root="/", max_items=400):
    n = [0]

    def visit(name, obj):
        if n[0] < max_items:
            shape = getattr(obj, "shape", None)
            dt = getattr(obj, "dtype", None)
            print(f"  /{name}" + (f"  {shape} {dt}" if shape is not None else "/"))
            n[0] += 1

    h5[root].visititems(visit)


# ---------------------------------------------------------------- core
def read_subset(fobj, bbox_ll):
    """Return dict with hh, hv (linear), mask, x, y, epsg, transform for the AOI window."""
    import h5py
    from rasterio.transform import from_origin
    from rasterio.warp import transform_bounds

    with h5py.File(fobj, "r") as h5:
        xs_path = find(h5, ["xCoordinates"])
        ys_path = find(h5, ["yCoordinates"])
        x = h5[xs_path][()]
        y = h5[ys_path][()]
        epsg = epsg_of(h5)
        xmin, ymin, xmax, ymax = transform_bounds("EPSG:4326", f"EPSG:{epsg}", *bbox_ll, densify_pts=21)
        cols = np.where((x >= xmin) & (x <= xmax))[0]
        rows = np.where((y >= ymin) & (y <= ymax))[0]
        if cols.size == 0 or rows.size == 0:
            raise ValueError("AOI outside granule grid")
        c0, c1, r0, r1 = cols.min(), cols.max() + 1, rows.min(), rows.max() + 1
        nbytes = (c1 - c0) * (r1 - r0) * 4 * 3
        check_budget(nbytes, "NISAR subset read")
        hh = h5[f"{GRID}/HHHH"][r0:r1, c0:c1].astype(np.float32)
        hv = h5[f"{GRID}/HVHV"][r0:r1, c0:c1].astype(np.float32)
        mask = h5[f"{GRID}/mask"][r0:r1, c0:c1] if f"{GRID}/mask" in h5 else None
        mask_attrs = {k: str(v) for k, v in h5[f"{GRID}/mask"].attrs.items()} if mask is not None else {}
    dx, dy = float(x[1] - x[0]), float(y[1] - y[0])
    # coordinates are pixel centres (checked against spec in NOTES.md); dy is negative (north-up)
    transform = from_origin(x[c0] - dx / 2, y[r0] - dy / 2, dx, -dy)
    return {"hh": hh, "hv": hv, "mask": mask, "mask_attrs": mask_attrs, "epsg": epsg,
            "transform": transform, "shape": hh.shape, "dx": dx, "dy": dy}


def write_tif(path, arr, epsg, transform, nodata, dtype, descriptions=None):
    import rasterio

    arr = arr if arr.ndim == 3 else arr[None]
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[1], width=arr.shape[2], count=arr.shape[0],
                       dtype=dtype, crs=f"EPSG:{epsg}", transform=transform, nodata=nodata,
                       compress="deflate", predictor=3 if dtype == "float32" else 2, tiled=True) as dst:
        dst.write(arr.astype(dtype))
        for i, d in enumerate(descriptions or [], 1):
            dst.set_band_description(i, d)


# DSWx-HLS WTR layer values (OPERA DSWx-HLS product spec): 0 not water, 1 open water,
# 2 partial surface water, 252 snow/ice, 253 cloud/cloud shadow, 254 ocean masked, 255 fill.
def dswx_reference(urls: list[str], epsg, transform, shape) -> np.ndarray:
    import rasterio
    from rasterio.warp import Resampling, reproject

    out = np.full(shape, 255, np.uint8)
    for u in urls:
        with rasterio.open(u) as src:
            tmp = np.full(shape, 255, np.uint8)
            reproject(rasterio.band(src, 1), tmp, src_nodata=255, dst_nodata=255, dst_transform=transform,
                      dst_crs=f"EPSG:{epsg}", resampling=Resampling.nearest)
        fill = (out == 255) & (tmp != 255)
        out[fill] = tmp[fill]
    ref = np.full(shape, 255, np.uint8)
    ref[out == 0] = 0
    ref[(out == 1) | (out == 2)] = 1
    return ref


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-login", action="store_true")
    ap.add_argument("--tree", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--main-track-only", action="store_true", help="skip the other usable tracks")
    a = ap.parse_args()

    login()
    if a.check_login:
        return
    import earthaccess
    import h5py

    meta = json.loads((OUTPUTS / "aoi.json").read_text())
    ch = meta["chosen"]
    bbox = meta["aois"][ch["reservoir"]]["bbox"]
    cand = pd.read_csv(OUTPUTS / "candidate_scenes.csv")
    cand = cand[(cand["reservoir"] == ch["reservoir"]) & cand["usable"]]
    keep = cand["same_track_group"] | (cand["also_used"] if "also_used" in cand else False)
    if a.main_track_only:
        keep = cand["same_track_group"]
    cand = cand[keep]
    cand = cand.sort_values("date")
    if a.limit:
        cand = cand.head(a.limit)

    if a.tree:
        f = earthaccess.open([cand.iloc[0]["h5_url"]])[0]
        with h5py.File(f, "r") as h5:
            print_tree(h5)
        return

    import rasterio

    # One authenticated HTTPS session; large blocks = few range requests (campus DNS is flaky).
    fs = earthaccess.get_fsspec_https_session()

    def nisar_date(url, out):
        with fs.open(url, "rb", block_size=8 * 1024**2, cache_type="blockcache") as f:
            s = read_subset(f, bbox)
        hh, hv = lee_filter(s["hh"]), lee_filter(s["hv"])
        tmp = out.with_suffix(".part.tif")
        write_tif(tmp, np.stack([to_db(hh), to_db(hv)]), s["epsg"], s["transform"], np.nan, "float32",
                  ["HH_dB", "HV_dB"])
        tmp.replace(out)  # only complete files get the final name
        print(f"   wrote {out.name} shape={s['shape']} dx={s['dx']} dy={s['dy']} epsg={s['epsg']}", flush=True)

    def dswx_date(urls, ref_path, epsg, transform, shape):
        fobjs = [fs.open(u, "rb") for u in urls]  # WTR COGs are < 1 MB each
        ref = dswx_reference(fobjs, epsg, transform, shape)
        write_tif(ref_path, ref, epsg, transform, 255, "uint8", ["water(1)/not(0)/masked(255)"])

    rows, failed = [], []
    for _, r in cand.iterrows():
        tag = f"{ch['reservoir']}_T{r['track']:03d}{r['direction'][0]}_{r['date']}"
        out = NISAR_DIR / f"{tag}.tif"
        print(f"== {tag}  (data root {dir_size()/1e6:.0f} MB)", flush=True)
        try:
            if not out.exists():
                retry(nisar_date, r["h5_url"], out, what=f"NISAR {tag}")
            with rasterio.open(out) as src:
                epsg, transform, shape = src.crs.to_epsg(), src.transform, (src.height, src.width)
            ref_path = DSWX_DIR / f"{tag}_dswx.tif"
            if str(r.get("dswx_date", "none")) != "none" and isinstance(r.get("wtr_urls"), str) \
                    and not ref_path.exists():
                retry(dswx_date, [u for u in r["wtr_urls"].split(";") if u], ref_path, epsg, transform, shape,
                      what=f"DSWx {tag}")
        except Exception as e:  # keep going; a rerun only redoes the missing dates
            print(f"   FAILED {tag}: {type(e).__name__}: {str(e)[:150]}", flush=True)
            failed.append(tag)
            continue
        rows.append({"tag": tag, "date": r["date"], "track": r["track"], "direction": r["direction"],
                     "nisar_tif": rel(out), "dswx_tif": rel(ref_path) if ref_path.exists() else "",
                     "dswx_date": r.get("dswx_date"), "dswx_flag": r.get("dswx_flag", "")})
    pd.DataFrame(rows).to_csv(OUTPUTS / "nisar_scenes.csv", index=False)
    print(f"done: {len(rows)} dates ok, {len(failed)} failed {failed}; data root {dir_size()/1e6:.0f} MB")


if __name__ == "__main__":
    main()
