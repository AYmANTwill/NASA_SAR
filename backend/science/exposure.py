"""Exposure inside an impact zone: people, buildings and area, with an uncertainty from the zone's own uncertainty.

Zones:
- earthquakes: |LOS displacement| > 10 cm on any co-seismic track. Recomputed with the threshold at 10 cm ± 1σ of
  the displacement noise; the uncertainty is the larger departure from the central value.
- flood: a mask GeoTIFF (1 = flooded, 0 = dry). Recomputed after a 1-pixel erosion and a 1-pixel dilation of its
  edge.

Population:
- a local raster if present: NISAR_POP_RASTER, or data/aux/pop/<ISO3>.tif (e.g. a GHSL GHS-POP 2025 100 m tile cut
  to the country);
- otherwise the latest WorldPop 100 m country raster, downloaded once.
Counts are summed on the population grid (never resampled).

Buildings: OpenStreetMap building centroids from Overpass, fetched in 0.25° tiles and cached. Every download is
cached under data/aux/ (git-ignored). The command line is in science/exposure_run.py.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
import requests
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import from_bounds
from scipy import ndimage

log = logging.getLogger(__name__)
AUX_DIR = Path(os.environ.get("NISAR_AUX", Path(__file__).resolve().parents[2] / "data" / "aux"))
QUAKE_THRESHOLD_CM = 10.0
OSM_TILE_DEG = 0.25
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
WORLDPOP_API = "https://hub.worldpop.org/rest/data/pop/wpgp?iso3={iso3}"
WORLDPOP_PAGE = "https://hub.worldpop.org/project/categories?id=3"
USER_AGENT = "nisar-pulse/1.0 (NASA Space Apps 2026)"
TIMEOUT_S = 300
KM2_PER_DEG2_EQ = 111.32 * 110.574


class ExposureError(RuntimeError):
    """An input needed for the exposure is missing."""


@dataclass(frozen=True)
class Grid:
    transform: rasterio.Affine
    crs: object
    shape: tuple[int, int]

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        h, w = self.shape
        x0, y0 = self.transform * (0, 0)
        x1, y1 = self.transform * (w, h)
        return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


@dataclass(frozen=True)
class PopSource:
    path: Path
    name: str
    url: str


# ---------------------------------------------------------------- zone metrics (pure, tested offline)
def area_km2(mask: np.ndarray, grid: Grid) -> float:
    if CRS.from_user_input(grid.crs).is_projected:
        return float(mask.sum()) * abs(grid.transform.a * grid.transform.e) / 1e6
    rows = np.arange(grid.shape[0])
    lat = np.array([(grid.transform * (0.5, r + 0.5))[1] for r in rows])
    cell = abs(grid.transform.a * grid.transform.e) * KM2_PER_DEG2_EQ * np.cos(np.radians(lat))
    return float((mask.sum(axis=1) * cell).sum())


def people_in(mask: np.ndarray, grid: Grid, pop: PopSource) -> float:
    """Sum of the population raster over its cells whose centre falls in the mask."""
    if not mask.any():
        return 0.0
    with rasterio.open(pop.path) as src:
        b = transform_bounds(grid.crs, src.crs, *grid.bounds)
        win = from_bounds(*b, transform=src.transform).round_offsets().round_lengths()
        counts = src.read(1, window=win, boundless=True, fill_value=0).astype("float64")
        if src.nodata is not None:
            counts[counts == src.nodata] = 0
        counts[~np.isfinite(counts) | (counts < 0)] = 0
        wt = src.window_transform(win)
        on_pop = np.zeros(counts.shape, dtype="uint8")
        reproject(mask.astype("uint8"), on_pop, src_transform=grid.transform, src_crs=grid.crs, dst_transform=wt,
                  dst_crs=src.crs, resampling=Resampling.nearest)
    return float(counts[on_pop == 1].sum())


def buildings_in(mask: np.ndarray, grid: Grid, lonlat: np.ndarray) -> int:
    if lonlat.size == 0:
        return 0
    x, y = Transformer.from_crs(4326, grid.crs, always_xy=True).transform(lonlat[:, 0], lonlat[:, 1])
    col, row = ~grid.transform * (np.asarray(x), np.asarray(y))
    r, c = np.floor(row).astype(int), np.floor(col).astype(int)
    ok = (r >= 0) & (r < grid.shape[0]) & (c >= 0) & (c < grid.shape[1])
    return int(mask[r[ok], c[ok]].sum())


def metrics(mask: np.ndarray, grid: Grid, pop: PopSource, lonlat: np.ndarray) -> dict:
    return {"people": people_in(mask, grid, pop), "buildings": buildings_in(mask, grid, lonlat),
            "area_km2": area_km2(mask, grid)}


def with_spread(central: dict, variants: list[dict]) -> dict:
    """{key: {value, uncertainty, range}}: uncertainty = largest departure of a variant from the central value."""
    out = {}
    for k, v in central.items():
        alts = [m[k] for m in variants]
        out[k] = {"value": v, "uncertainty": max((abs(a - v) for a in alts), default=0.0),
                  "range": [min([v, *alts]), max([v, *alts])]}
    return out


def quake_masks(abs_disp_cm: np.ndarray, noise_cm: float,
                threshold_cm: float = QUAKE_THRESHOLD_CM) -> tuple[np.ndarray, list[np.ndarray]]:
    """(central mask, [mask at threshold - sigma, mask at threshold + sigma])."""
    if not (math.isfinite(noise_cm) and noise_cm >= 0):
        raise ExposureError(f"invalid displacement noise {noise_cm}")
    a = np.nan_to_num(abs_disp_cm, nan=0.0)
    return a > threshold_cm, [a > max(threshold_cm - noise_cm, 0.0), a > threshold_cm + noise_cm]


def flood_masks(mask: np.ndarray) -> tuple[np.ndarray, list[np.ndarray]]:
    """(central mask, [eroded by 1 pixel, dilated by 1 pixel])."""
    m = mask.astype(bool)
    return m, [ndimage.binary_erosion(m), ndimage.binary_dilation(m)]


def exposure(central: np.ndarray, variants: list[np.ndarray], grid: Grid, pop: PopSource,
             lonlat: np.ndarray) -> dict:
    return with_spread(metrics(central, grid, pop, lonlat), [metrics(v, grid, pop, lonlat) for v in variants])


def to_case_exposure(result: dict, pop: PopSource, osm_date: str) -> dict:
    """The CaseStudy.exposure object (docs/CASE_CONTRACT.md)."""
    def meas(k: str, unit: str, nd: int) -> dict:
        return {"value": round(result[k]["value"], nd), "uncertainty": round(result[k]["uncertainty"], nd),
                "unit": unit, "sigma": 1}
    return {"people": meas("people", "people", 0), "buildings": meas("buildings", "count", 0),
            "area_km2": meas("area_km2", "km2", 2),
            "source": {"name": f"{pop.name}; OpenStreetMap buildings via Overpass ({osm_date})", "url": pop.url}}


# ---------------------------------------------------------------- downloads (cached)
def population_source(iso3: str) -> PopSource:
    iso3 = iso3.upper()
    env = os.environ.get("NISAR_POP_RASTER")
    if env:
        return PopSource(Path(env), f"population raster {Path(env).name}", WORLDPOP_PAGE)
    local = AUX_DIR / "pop" / f"{iso3}.tif"
    meta_path = local.with_suffix(".json")
    if local.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
        return PopSource(local, meta.get("name", f"population raster {local.name}"), meta.get("url", WORLDPOP_PAGE))
    if os.environ.get("NISAR_OFFLINE") == "1":
        raise ExposureError(f"no population raster for {iso3} in {local.parent} and NISAR_OFFLINE=1")
    try:
        r = requests.get(WORLDPOP_API.format(iso3=iso3), headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S)
        r.raise_for_status()
        entry = max(r.json().get("data", []), key=lambda e: int(e.get("popyear", 0)))
        file_url = entry["files"][0]
    except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
        raise ExposureError(f"WorldPop lookup failed for {iso3}: {exc}") from exc
    local.parent.mkdir(parents=True, exist_ok=True)
    tmp = local.with_suffix(".part")
    try:
        with requests.get(file_url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S, stream=True) as resp:
            resp.raise_for_status()
            with open(tmp, "wb") as fh:
                for chunk in resp.iter_content(1 << 20):
                    fh.write(chunk)
    except requests.RequestException as exc:
        raise ExposureError(f"WorldPop download failed ({file_url}): {exc}") from exc
    tmp.replace(local)
    meta = {"name": f"WorldPop 100 m, {entry.get('popyear')} ({iso3})", "url": file_url}
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    return PopSource(local, meta["name"], meta["url"])


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _osm_tile(s: float, w: float, n: float, e: float) -> tuple[list, str]:
    """(centroids [[lon, lat], ...], fetch date) of the buildings in one tile, cached."""
    key = hashlib.sha1(f"{s:.4f},{w:.4f},{n:.4f},{e:.4f}".encode()).hexdigest()[:16]
    path = AUX_DIR / "osm" / f"buildings_{key}.json"
    if path.is_file():
        d = json.loads(path.read_text(encoding="utf-8"))
        return d["centroids"], d["fetched"]
    if os.environ.get("NISAR_OFFLINE") == "1":
        raise ExposureError(f"OSM tile {s},{w},{n},{e} not cached and NISAR_OFFLINE=1")
    q = (f'[out:json][timeout:180];(way["building"]({s},{w},{n},{e});relation["building"]({s},{w},{n},{e});'
         f'node["building"]({s},{w},{n},{e}););out center;')
    els = None
    for attempt in range(3):
        try:
            r = requests.post(OVERPASS_URL, data={"data": q}, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S)
            r.raise_for_status()
            els = r.json()["elements"]
            break
        except (requests.RequestException, ValueError, KeyError) as exc:
            log.warning("Overpass attempt %d failed for %s: %s", attempt + 1, (s, w, n, e), exc)
            if attempt == 2:
                raise ExposureError(f"Overpass failed for tile {s},{w},{n},{e}: {exc}") from exc
            time.sleep(10 * (attempt + 1))
    pts = [[el["lon"], el["lat"]] if "lon" in el else [el["center"]["lon"], el["center"]["lat"]]
           for el in els if "lon" in el or "center" in el]
    path.parent.mkdir(parents=True, exist_ok=True)
    fetched = _today()
    path.write_text(json.dumps({"bbox": [s, w, n, e], "fetched": fetched, "centroids": pts}), encoding="utf-8")
    return pts, fetched


def osm_buildings(mask: np.ndarray, grid: Grid) -> tuple[np.ndarray, str]:
    """(centroids (lon, lat), oldest fetch date) of OSM buildings in the 0.25° tiles touching the mask."""
    rows, cols = np.nonzero(mask)
    if rows.size == 0:
        return np.zeros((0, 2)), _today()
    x, y = grid.transform * (cols + 0.5, rows + 0.5)
    lon, lat = Transformer.from_crs(grid.crs, 4326, always_xy=True).transform(x, y)
    tiles = sorted(set(zip(np.floor(np.asarray(lat) / OSM_TILE_DEG).astype(int).tolist(),
                           np.floor(np.asarray(lon) / OSM_TILE_DEG).astype(int).tolist())))
    pts, dates = [], []
    for i, j in tiles:
        p, d = _osm_tile(i * OSM_TILE_DEG, j * OSM_TILE_DEG, (i + 1) * OSM_TILE_DEG, (j + 1) * OSM_TILE_DEG)
        pts += p
        dates.append(d)
    return np.array(pts, dtype=float).reshape(-1, 2), min(dates)
