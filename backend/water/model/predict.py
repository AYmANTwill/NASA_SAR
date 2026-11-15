"""Water map from a NISAR L2 GCOV scene with the Water U-Net v3 (model/water_unet_v3.pt).

Two inputs:
  1. a NISAR GCOV HDF5 file (local path or Earthdata HTTPS URL) and a lon/lat box: reads only that window of
     HH/HV (5x5 Lee filter, dB) and the incidence-angle cube, exactly as the training data were prepared;
  2. a prepared 2-band GeoTIFF (HH dB, HV dB) and its incidence-angle GeoTIFF (degrees, same grid).
Writes <out>_prob.tif (water probability 0-1) and <out>_water.tif (1 water, 0 not water, 255 no data), prints the
water area. A remote URL needs EARTHDATA_TOKEN in the environment.

Examples (from backend/water/):
  python model/predict.py --h5 NISAR_L2_PR_GCOV_....h5 --bbox -6.49 32.05 -6.33 32.15 --out bin_el_ouidane
  python model/predict.py --tif scene.tif --inc scene_inc.tif --out scene
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from adabn import INC_MEAN, INC_STD, predict_scene  # noqa: E402
from data_s1 import normalize  # noqa: E402
from model import load_model  # noqa: E402
from nisar_prep import epsg_of, lee_filter, read_subset, to_db, write_tif  # noqa: E402

CHECKPOINT = HERE / "water_unet_v3.pt"
RG = "/science/LSAR/GCOV/metadata/radarGrid"


def incidence_on_grid(h5, transform, shape, h_ref: float = 500.0) -> np.ndarray:
    """Incidence angle (deg) on the backscatter grid: nearest height layer of the radarGrid cube, bilinear in x/y."""
    from scipy.interpolate import RegularGridInterpolator

    h, w = shape
    xs = transform.c + transform.a * (np.arange(w) + 0.5)
    ys = transform.f + transform.e * (np.arange(h) + 0.5)
    gx, gy, hh = h5[f"{RG}/xCoordinates"][()], h5[f"{RG}/yCoordinates"][()], h5[f"{RG}/heightAboveEllipsoid"][()]
    k = int(np.argmin(np.abs(hh - h_ref)))
    c = np.where((gx >= xs.min()) & (gx <= xs.max()))[0]
    r = np.where((gy >= ys.min()) & (gy <= ys.max()))[0]
    c0, c1 = max(c.min() - 2, 0), min(c.max() + 3, len(gx))
    r0, r1 = max(r.min() - 2, 0), min(r.max() + 3, len(gy))
    cube = h5[f"{RG}/incidenceAngle"][k, r0:r1, c0:c1].astype(np.float64)
    sx, sy = gx[c0:c1], gy[r0:r1]
    if sy[0] > sy[-1]:
        sy, cube = sy[::-1], cube[::-1]
    if sx[0] > sx[-1]:
        sx, cube = sx[::-1], cube[:, ::-1]
    f = RegularGridInterpolator((sy, sx), cube, bounds_error=False, fill_value=None)
    yy, xx = np.meshgrid(ys, xs, indexing="ij")
    return f(np.stack([yy.ravel(), xx.ravel()], 1)).reshape(h, w).astype(np.float32)


def from_h5(src: str, bbox) -> tuple[np.ndarray, np.ndarray, int, object]:
    import h5py

    if src.startswith("http"):
        from common import https_fs
        opener = lambda: https_fs().open(src, "rb", block_size=16 * 2**20, cache_type="blockcache")  # noqa: E731
    else:
        opener = lambda: open(src, "rb")  # noqa: E731
    with opener() as f:
        s = read_subset(f, bbox)
    x_db = np.stack([to_db(lee_filter(s["hh"])), to_db(lee_filter(s["hv"]))]).astype(np.float32)
    with opener() as f, h5py.File(f, "r") as h5:
        assert epsg_of(h5) == s["epsg"]
        inc = incidence_on_grid(h5, s["transform"], x_db.shape[1:])
    return x_db, inc, s["epsg"], s["transform"]


def from_tif(tif: str, inc_tif: str):
    import rasterio

    with rasterio.open(tif) as a, rasterio.open(inc_tif) as b:
        assert a.transform == b.transform and a.shape == b.shape, "incidence raster must be on the scene grid"
        return a.read().astype(np.float32), b.read(1).astype(np.float32), a.crs.to_epsg(), a.transform


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--h5", help="NISAR L2 GCOV HDF5 (path or https URL)")
    g.add_argument("--tif", help="2-band GeoTIFF: HH dB, HV dB")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"), help="lon/lat box (with --h5)")
    ap.add_argument("--inc", help="incidence-angle GeoTIFF in degrees (with --tif)")
    ap.add_argument("--out", required=True, help="output prefix")
    ap.add_argument("--checkpoint", default=str(CHECKPOINT))
    a = ap.parse_args()
    if a.h5 and not a.bbox:
        ap.error("--h5 needs --bbox")
    if a.tif and not a.inc:
        ap.error("--tif needs --inc")
    x_db, inc, epsg, tr = from_h5(a.h5, a.bbox) if a.h5 else from_tif(a.tif, a.inc)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(a.checkpoint, map_location="cpu", weights_only=False)
    model = load_model(a.checkpoint, device)
    thr = float(ck.get("probability_threshold", 0.35))
    xn, valid = normalize(x_db, ck["norm"]["mean_db"], ck["norm"]["std_db"])
    xn = np.concatenate([xn, np.nan_to_num((inc - INC_MEAN) / INC_STD, nan=0.0)[None]]).astype(np.float32)
    prob, _ = predict_scene(model, xn, device)
    prob[~valid] = np.nan
    water = np.where(valid, (prob >= thr).astype(np.uint8), 255).astype(np.uint8)
    write_tif(Path(f"{a.out}_prob.tif"), prob, epsg, tr, np.nan, "float32", ["water_probability"])
    write_tif(Path(f"{a.out}_water.tif"), water, epsg, tr, 255, "uint8", ["water(1)/not(0)/nodata(255)"])
    km2 = float((water == 1).sum() * abs(tr.a * tr.e) / 1e6)
    print(f"water {km2:.3f} km2 (p >= {thr}), {valid.mean():.1%} valid pixels, device {device}; "
          f"wrote {a.out}_prob.tif and {a.out}_water.tif")


if __name__ == "__main__":
    main()
