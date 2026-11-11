"""Recipe 'large_displacement': GOFF pixel offsets (glaciers, dunes, fast landslides), metres."""
from __future__ import annotations

import numpy as np

import raster
from catalog import Product
from config import POINT_RADIUS_M


def analyze(products: list[Product], lat: float, lon: float) -> dict:
    if not products:
        return {"error": "no GOFF product covers this point"}
    p = products[0]
    along, prof = raster.read(p.files["along"])
    rng = raster.read(p.files["range"])[0] if "range" in p.files else np.zeros_like(along)
    if "peak" in p.files:
        peak = raster.read(p.files["peak"])[0]
        along = np.where(peak > 0.1, along, np.nan)
    mag = np.hypot(along, rng).astype("float32")
    w = raster.window(mag, prof, lat, lon, POINT_RADIUS_M)
    lim = float(np.nanpercentile(mag, 98)) if np.isfinite(mag).any() else 1
    layer = raster.render_png(mag, prof, f"offset_{p.id}", "magma", 0, lim)
    layer["title"] = f"Displacement magnitude from pixel offsets (m), {p.ref[:8]}→{p.sec[:8]}"
    return {"product": p.id, "date_before": p.ref[:8], "date_after": p.sec[:8],
            "magnitude_m": None if not np.isfinite(w).any() else round(float(np.nanmedian(w)), 2),
            "along_track_m": round(float(np.nanmedian(raster.window(along, prof, lat, lon, POINT_RADIUS_M))), 2),
            "range_m": round(float(np.nanmedian(raster.window(rng, prof, lat, lon, POINT_RADIUS_M))), 2),
            "layer": layer}
