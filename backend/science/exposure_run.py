"""Exposure of a case study, written to cases/out/<case>_exposure.json for science/cases.py.

    python -m science.exposure_run --case panama-2026 --event us6000u18k --iso3 PAN
    python -m science.exposure_run --case haouz-flood-2026 --iso3 MAR --flood-mask ../results/haouz-flood-2026/flood_mask.tif

Earthquake zone: |LOS| > 10 cm on any co-seismic GUNW pair covering the epicentre. The tracks are put on the grid of
the first pair (nearest neighbour) and the largest |LOS| is kept. The noise is the largest per-track robust sigma
far from the epicentre (recipes/displacement.referenced).
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject

import catalog
from recipes import displacement
from science import exposure as ex
from science import usgs

log = logging.getLogger(__name__)
OUT_DIR = Path(__file__).resolve().parents[1] / "cases" / "out"


def quake_inputs(event_id: str) -> tuple[np.ndarray, ex.Grid, float, list[str]]:
    """(max |LOS| in cm on the first pair's grid, that grid, noise sigma in cm, pair ids)."""
    ev = usgs.event(event_id)
    origin = datetime.fromtimestamp(ev.time_ms / 1000, tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
    pairs = catalog.straddling(catalog.find(ev.lat, ev.lon, "GUNW"), origin)
    if not pairs:
        raise ex.ExposureError(f"no co-seismic GUNW pair covers {event_id}")
    acc, grid, sigmas = None, None, []
    for p in pairs:
        d, _coh, prof, sigma, _notes = displacement.referenced(p, ev.lat, ev.lon)
        sigmas.append(float(sigma))
        a = np.abs(d).astype("float32")
        if acc is None:
            grid = ex.Grid(prof["transform"], prof["crs"], a.shape)
            acc = a
            continue
        on_grid = np.full(grid.shape, np.nan, dtype="float32")
        reproject(a, on_grid, src_transform=prof["transform"], src_crs=prof["crs"], dst_transform=grid.transform,
                  dst_crs=grid.crs, src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.nearest)
        acc = np.fmax(acc, on_grid)
    return acc, grid, max(sigmas), [p.id for p in pairs]


def flood_inputs(path: Path) -> tuple[np.ndarray, ex.Grid]:
    if not path.is_file():
        raise ex.ExposureError(f"flood mask not found: {path}")
    with rasterio.open(path) as src:
        arr = src.read(1)
        grid = ex.Grid(src.transform, src.crs, arr.shape)
    return arr == 1, grid


def run(case_id: str, iso3: str, event_id: str | None = None, flood_mask: Path | None = None,
        out_dir: Path = OUT_DIR) -> dict:
    if (event_id is None) == (flood_mask is None):
        raise ValueError("give exactly one of --event (earthquake) or --flood-mask (flood)")
    if event_id:
        abs_disp, grid, noise, pairs = quake_inputs(event_id)
        central, variants = ex.quake_masks(abs_disp, noise)
        zone = {"kind": "earthquake", "rule": f"|LOS| > {ex.QUAKE_THRESHOLD_CM} cm",
                "variants": [f"|LOS| > {ex.QUAKE_THRESHOLD_CM - noise:.2f} cm",
                             f"|LOS| > {ex.QUAKE_THRESHOLD_CM + noise:.2f} cm"],
                "noise_cm": noise, "noise_method": "largest per-track robust sigma far from the epicentre",
                "pairs": pairs}
    else:
        central, grid = flood_inputs(flood_mask)
        central, variants = ex.flood_masks(central)
        zone = {"kind": "flood", "rule": f"flood mask {flood_mask.name}",
                "variants": ["eroded by 1 pixel", "dilated by 1 pixel"]}
    pop = ex.population_source(iso3)
    largest = np.logical_or.reduce([central, *variants])
    lonlat, osm_date = ex.osm_buildings(largest, grid)
    result = ex.exposure(central, variants, grid, pop, lonlat)
    out = {"case": case_id, "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
           "zone": zone, "detail": result, "exposure": ex.to_case_exposure(result, pop, osm_date)}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{case_id}_exposure.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", required=True)
    ap.add_argument("--iso3", required=True, help="country of the population raster, e.g. PAN, VEN, MAR")
    ap.add_argument("--event", help="USGS event id (earthquake)")
    ap.add_argument("--flood-mask", type=Path, help="GeoTIFF, 1 = flooded (flood)")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    out = run(a.case, a.iso3, a.event, a.flood_mask, a.out_dir)
    print(json.dumps(out["exposure"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
