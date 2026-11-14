"""Raster helpers: read, sample around a lat/lon point, render a PNG overlay in EPSG:4326."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.warp import Resampling, calculate_default_transform, reproject

from config import CACHE_DIR


def read(path) -> tuple[np.ndarray, dict]:
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float32")
        if src.nodata is not None and not np.isnan(src.nodata):
            arr[arr == src.nodata] = np.nan
        prof = dict(transform=src.transform, crs=src.crs, width=src.width, height=src.height)
    return arr, prof


def to_pixel(prof: dict, lat: float, lon: float) -> tuple[int, int]:
    t = Transformer.from_crs(4326, prof["crs"], always_xy=True)
    x, y = t.transform(lon, lat)
    col, row = ~prof["transform"] * (x, y)
    return int(row), int(col)


def to_lonlat(prof: dict, row: float, col: float) -> tuple[float, float]:
    x, y = prof["transform"] * (col + 0.5, row + 0.5)
    t = Transformer.from_crs(prof["crs"], 4326, always_xy=True)
    return t.transform(x, y)


def pixel_size_m(prof: dict) -> float:
    return abs(prof["transform"].a)


def window(arr: np.ndarray, prof: dict, lat: float, lon: float, radius_m: float) -> np.ndarray:
    r, c = to_pixel(prof, lat, lon)
    k = max(1, int(radius_m / pixel_size_m(prof)))
    r0, r1, c0, c1 = max(r - k, 0), min(r + k + 1, arr.shape[0]), max(c - k, 0), min(c + k + 1, arr.shape[1])
    if r0 >= r1 or c0 >= c1:
        return np.array([], dtype="float32")
    return arr[r0:r1, c0:c1]


def _embed(block, r0, c0, r, c, k):
    """Puts block (the in-array part of a (2k+1)² window centred on pixel (r, c), starting at (r0, c0)) in a
    NaN-filled square. Returns (sub, inside); inside is True where the pixel lies in the array."""
    sub = np.full((2 * k + 1, 2 * k + 1), np.nan, dtype="float32")
    inside = np.zeros(sub.shape, dtype=bool)
    if block is not None and block.size:
        a, b = r0 - (r - k), c0 - (c - k)
        sub[a:a + block.shape[0], b:b + block.shape[1]] = block
        inside[a:a + block.shape[0], b:b + block.shape[1]] = True
    return sub, inside


def _disc(k: int, px: float, radius_m: float) -> np.ndarray:
    ii, jj = np.ogrid[-k:k + 1, -k:k + 1]
    return np.hypot(ii, jj) * px <= radius_m


def crop_around(arr: np.ndarray, prof: dict, lat: float, lon: float, radius_m: float):
    """Square crop centred on the point, NaN where it falls outside the array.
    Returns (sub, inside, circle): inside = the pixel is in the array; circle = within radius_m of the point
    (a geometric disc, whatever the data), so circle.sum() is the full disc even when it is clipped."""
    r, c = to_pixel(prof, lat, lon)
    px = pixel_size_m(prof)
    k = max(1, int(np.ceil(radius_m / px)))
    r0, r1, c0, c1 = max(r - k, 0), min(r + k + 1, arr.shape[0]), max(c - k, 0), min(c + k + 1, arr.shape[1])
    block = arr[r0:r1, c0:c1] if (r0 < r1 and c0 < c1) else None
    sub, inside = _embed(block, r0, c0, r, c, k)
    return sub, inside, _disc(k, px, radius_m)


def read_around(path, lat: float, lon: float, radius_m: float):
    """Like crop_around on a file, but reads only the window (fast on a 4000x4000 raster).
    Returns (sub, inside, circle, prof)."""
    from rasterio.windows import Window
    with rasterio.open(path) as src:
        prof = dict(transform=src.transform, crs=src.crs, width=src.width, height=src.height)
        r, c = to_pixel(prof, lat, lon)
        px = pixel_size_m(prof)
        k = max(1, int(np.ceil(radius_m / px)))
        r0, r1, c0, c1 = max(r - k, 0), min(r + k + 1, src.height), max(c - k, 0), min(c + k + 1, src.width)
        block = None
        if r0 < r1 and c0 < c1:
            block = src.read(1, window=Window(c0, r0, c1 - c0, r1 - r0)).astype("float32")
            if src.nodata is not None and not np.isnan(src.nodata):
                block[block == src.nodata] = np.nan
    sub, inside = _embed(block, r0, c0, r, c, k)
    return sub, inside, _disc(k, px, radius_m), prof


def distance_mask(prof: dict, lat: float, lon: float, min_m: float) -> np.ndarray:
    """True for pixels farther than min_m from the point (used as the stable reference area)."""
    r, c = to_pixel(prof, lat, lon)
    rows, cols = np.ogrid[: prof["height"], : prof["width"]]
    px = pixel_size_m(prof)
    return ((rows - r) ** 2 + (cols - c) ** 2) * px * px > min_m ** 2


def profile_line(arr: np.ndarray, prof: dict, lat: float, lon: float, half_km: float = 20) -> list[dict]:
    """West-east profile through the point."""
    r, c = to_pixel(prof, lat, lon)
    if not (0 <= r < arr.shape[0]):
        return []
    px = pixel_size_m(prof)
    k = int(half_km * 1000 / px)
    c0, c1 = max(c - k, 0), min(c + k + 1, arr.shape[1])
    step = max(1, (c1 - c0) // 200)
    return [{"km": round((cc - c) * px / 1000, 2),
             "value": None if not np.isfinite(arr[r, cc]) else round(float(arr[r, cc]), 3)}
            for cc in range(c0, c1, step)]


# The frontend's canonical palettes (palettes.json, copied from its src/design/palettes.json): the PNG pixels
# must use exactly these stops so its legends match. Each matplotlib name used by the recipes maps to one.
_CANONICAL = {"RdBu_r": "diverging_displacement", "coolwarm": "diverging_displacement",
              "inferno": "sequential_coherence_loss", "YlGnBu": "sequential_moisture",
              "magma": "sequential_coherence", "YlOrRd_r": "sequential_coherence_loss"}


def _colormap(cmap: str):
    from matplotlib import colormaps
    from matplotlib.colors import LinearSegmentedColormap
    import json as _json
    from pathlib import Path as _P
    f = _P(__file__).with_name("palettes.json")
    if cmap in _CANONICAL and f.exists():
        stops = _json.loads(f.read_text(encoding="utf-8")).get(_CANONICAL[cmap])
        if stops:
            return LinearSegmentedColormap.from_list(_CANONICAL[cmap], stops)
    return colormaps[cmap]


def render_png(arr: np.ndarray, prof: dict, name: str, cmap: str, vmin: float, vmax: float,
               max_px: int = 1600) -> dict:
    """Reprojects to EPSG:4326, colours with a matplotlib colormap, NaN transparent.
    Returns {"url", "bounds": [[south, west], [north, east]], "vmin", "vmax", "cmap"}."""
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import colormaps
    from PIL import Image

    h, w = arr.shape
    dst_t, dw, dh = calculate_default_transform(prof["crs"], "EPSG:4326", w, h,
                                                *rasterio.transform.array_bounds(h, w, prof["transform"])[::-1][::-1])
    scale = max(dw, dh) / max_px
    if scale > 1:
        dw, dh = int(dw / scale), int(dh / scale)
        dst_t = dst_t * dst_t.scale(scale, scale)
    dst = np.full((dh, dw), np.nan, dtype="float32")
    reproject(arr, dst, src_transform=prof["transform"], src_crs=prof["crs"], dst_transform=dst_t,
              dst_crs="EPSG:4326", resampling=Resampling.bilinear, src_nodata=np.nan, dst_nodata=np.nan)
    norm = np.clip((dst - vmin) / (vmax - vmin + 1e-12), 0, 1)
    rgba = (_colormap(cmap)(norm) * 255).astype("uint8")
    rgba[..., 3] = np.where(np.isfinite(dst), 210, 0)
    out = CACHE_DIR / "layers" / f"{name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(out, optimize=True)
    west, north = dst_t * (0, 0)
    east, south = dst_t * (dw, dh)
    return {"url": f"/layers/{name}.png", "bounds": [[south, west], [north, east]],
            "vmin": round(float(vmin), 3), "vmax": round(float(vmax), 3), "cmap": cmap}


def key(*parts) -> str:
    return hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:12]
