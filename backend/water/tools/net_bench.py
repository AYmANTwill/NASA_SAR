"""Network benchmark for NISAR/DSWx reads (rerun on Wi-Fi, VPN, hotspot and compare).

Each run opens a FRESH authenticated HTTPS session (no reuse, no local cache) and times:
  1. the same NISAR GCOV window (HHHH + HVHV over the Bin El Ouidane bbox) with fsspec defaults
  2. the same window with a 16 MB block size + blockcache (the setting used by the pipeline)
  3. the same small DSWx WTR tile (latency-dominated, about 0.1 MB)
  4. the same DSWx DEM layer (bandwidth-dominated, about 30 MB)
Results: printed table + backend/water/outputs/net_bench/<UTC time>_<label>.json
Usage:  python tools/net_bench.py --label wifi [--runs 2]
No credentials are printed or written (the token is read by common.py from the data root).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from common import OUTPUTS  # noqa: E402  (common.py also sets up the login environment)

GRID = "/science/LSAR/GCOV/grids/frequencyA"
TAG = "Bin_El_Ouidane_T044A_2026-06-17"


def targets():
    aoi = json.loads((OUTPUTS / "aoi.json").read_text())
    bbox = aoi["aois"]["Bin_El_Ouidane"]["bbox"]
    c = pd.read_csv(OUTPUTS / "candidate_scenes.csv")
    r = c[(c["reservoir"] == "Bin_El_Ouidane") & c["usable"] & (c["date"] == TAG[-10:]) & (c["track"] == 44)].iloc[0]
    wtr = r["wtr_urls"].split(";")[0]
    return bbox, r["h5_url"], wtr, wtr.replace("_B01_WTR.tif", "_B10_DEM.tif")


def window_slices(fs, url, bbox):
    """Row/col slices of the bbox in the frequency-A grid (metadata read, timed separately)."""
    import h5py
    from rasterio.warp import transform_bounds

    with fs.open(url, "rb", block_size=16 * 2**20, cache_type="blockcache") as f, h5py.File(f, "r") as h:
        x, y = h[f"{GRID}/xCoordinates"][()], h[f"{GRID}/yCoordinates"][()]
        epsg = int(np.asarray(h[f"{GRID}/projection"][()]).ravel()[0])
    xmin, ymin, xmax, ymax = transform_bounds("EPSG:4326", f"EPSG:{epsg}", *bbox, densify_pts=21)
    cols, rows = np.where((x >= xmin) & (x <= xmax))[0], np.where((y >= ymin) & (y <= ymax))[0]
    return slice(rows.min(), rows.max() + 1), slice(cols.min(), cols.max() + 1)


def read_window(fs, url, rs, cs, block_size=None):
    import h5py

    kw = {} if block_size is None else {"block_size": block_size, "cache_type": "blockcache"}
    t0 = time.perf_counter()
    with fs.open(url, "rb", **kw) as f, h5py.File(f, "r") as h:
        a = h[f"{GRID}/HHHH"][rs, cs]
        b = h[f"{GRID}/HVHV"][rs, cs]
        cache = getattr(f, "cache", None)
        fetched = getattr(cache, "total_requested_bytes", None)
        misses = getattr(cache, "miss_count", None)
    dt = time.perf_counter() - t0
    return dt, (a.nbytes + b.nbytes) / 1e6, (fetched / 1e6 if fetched else None), misses


def download(fs, url):
    t0 = time.perf_counter()
    with fs.open(url, "rb", block_size=16 * 2**20, cache_type="none") as f:
        n = len(f.read())
    return time.perf_counter() - t0, n / 1e6


def main() -> None:
    import earthaccess

    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True, help="network name, e.g. wifi, vpn, hotspot")
    ap.add_argument("--runs", type=int, default=2)
    a = ap.parse_args()
    earthaccess.login(strategy="environment")
    bbox, h5, wtr, dem = targets()
    rows = []
    fs0 = earthaccess.get_fsspec_https_session()
    t0 = time.perf_counter()
    rs, cs = window_slices(fs0, h5, bbox)
    meta_s = time.perf_counter() - t0
    print(f"window rows {rs.start}:{rs.stop}, cols {cs.start}:{cs.stop} (metadata + coordinates read in {meta_s:.1f} s)")
    for run in range(1, a.runs + 1):
        for name, fn in (("nisar_window_default_blocks", lambda fs: read_window(fs, h5, rs, cs)),
                         ("nisar_window_16MB_blockcache", lambda fs: read_window(fs, h5, rs, cs, 16 * 2**20)),
                         ("dswx_wtr_tile", lambda fs: download(fs, wtr) + (None, None)),
                         ("dswx_dem_layer", lambda fs: download(fs, dem) + (None, None))):
            fs = earthaccess.get_fsspec_https_session()  # fresh session each time: no cache reuse
            try:
                dt, mb, fetched, misses = fn(fs)
                rows.append({"run": run, "test": name, "seconds": round(dt, 2), "payload_mb": round(mb, 2),
                             "fetched_mb": round(fetched, 2) if fetched else None, "block_misses": misses,
                             "mb_per_s_payload": round(mb / dt, 3), "mb_per_s_fetched": round(fetched / dt, 3) if fetched else None})
            except Exception as e:
                rows.append({"run": run, "test": name, "error": f"{type(e).__name__}: {str(e)[:120]}"})
            print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    out = OUTPUTS / "net_bench"
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    res = {"label": a.label, "utc": stamp, "granule": h5.rsplit("/", 1)[-1], "window": [int(rs.start), int(rs.stop), int(cs.start), int(cs.stop)],
           "metadata_seconds": round(meta_s, 2), "results": rows}
    (out / f"{stamp}_{a.label}.json").write_text(json.dumps(res, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print("\n" + df.to_string(index=False))
    print(f"\nsaved {out / f'{stamp}_{a.label}.json'}")


if __name__ == "__main__":
    main()
