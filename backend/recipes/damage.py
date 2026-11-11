"""Recipe 'damage': coherence-loss damage proxy (same idea as JPL's Damage Proxy Maps).

coherence(before, before) - coherence(before, after) on the same track/frame. A large drop in a
built-up area that was coherent before the event is a likely sign of damage."""
from __future__ import annotations

import numpy as np

import raster
from catalog import Product, before, straddling
from config import POINT_RADIUS_M

DAMAGE_THRESHOLD = 0.3


def analyze(products: list[Product], lat: float, lon: float, event: str) -> dict:
    co = straddling(products, event)
    pre = before(products, event)
    for c in co:
        same = [p for p in pre if p.geometry == c.geometry and "coherence" in p.files]
        if not same or "coherence" not in c.files:
            continue
        b = max(same, key=lambda p: p.sec)                       # the most recent pre-event pair
        cb, prof = raster.read(b.files["coherence"])
        ca, prof_a = raster.read(c.files["coherence"])
        if ca.shape != cb.shape:
            continue
        loss = (cb - ca).astype("float32")
        loss[cb < 0.4] = np.nan                                   # only where it was coherent before
        w = raster.window(loss, prof, lat, lon, POINT_RADIUS_M)
        big = raster.window(loss, prof, lat, lon, 5_000)
        px_km2 = (raster.pixel_size_m(prof) / 1000) ** 2
        layer = raster.render_png(np.where(loss > 0.1, loss, np.nan), prof, f"dpm_{c.id}", "inferno", 0.1, 0.8)
        layer["title"] = f"Damage proxy (coherence loss), {c.ref[:8]}→{c.sec[:8]}"
        return {
            "pre_pair": b.id, "co_pair": c.id, "direction": c.direction,
            "loss_at_point": None if not np.isfinite(w).any() else round(float(np.nanmedian(w)), 2),
            "damaged_km2_5km": round(float(np.nansum(big > DAMAGE_THRESHOLD) * px_km2), 2),
            "coherent_before_fraction_5km": round(float(np.mean(np.isfinite(big))), 2),
            "threshold": DAMAGE_THRESHOLD, "layer": layer,
        }
    return {"error": "needs a pre-event pair and an event pair on the same track",
            "have_event_pairs": [p.id for p in co], "have_pre_pairs": [p.id for p in pre]}
