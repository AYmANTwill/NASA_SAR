"""Recipes 'flood' and 'deforestation' from GCOV backscatter (HH and HV power) before / after.

flood         : open water = strong HH drop to a dark surface; flooded vegetation = HH rise
                (double bounce, an L-band speciality) with HV stable.
deforestation : HV drop (less volume scattering from the canopy)."""
from __future__ import annotations

import numpy as np

import raster
from catalog import Product
from config import POINT_RADIUS_M


def _db(a):
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10 * np.log10(np.where(a > 0, a, np.nan))


def _pair(products: list[Product], date: str | None):
    """Latest acquisition after `date` and latest before it, on the same geometry."""
    ps = sorted(products, key=lambda p: p.ref)
    if len(ps) < 2:
        return None, None
    if date:
        after = [p for p in ps if p.ref >= date]
        if after:
            a = after[0]
            b = [p for p in ps if p.ref < date and p.geometry == a.geometry]
            return (b[-1] if b else None), a
    a = ps[-1]
    b = [p for p in ps[:-1] if p.geometry == a.geometry]
    return (b[-1] if b else None), a


def analyze(products: list[Product], lat: float, lon: float, kind: str, date: str | None = None,
            radius_m: float = 2000) -> dict:
    b, a = _pair(products, date)
    if b is None:
        return {"error": "needs two GCOV acquisitions on the same track/frame",
                "have": [p.id for p in products]}
    hh_b, prof = raster.read(b.files["hh"])
    hh_a, _ = raster.read(a.files["hh"])
    hv_b = raster.read(b.files["hv"])[0] if "hv" in b.files else None
    hv_a = raster.read(a.files["hv"])[0] if "hv" in a.files else None
    d_hh = _db(hh_a) - _db(hh_b)
    px_ha = raster.pixel_size_m(prof) ** 2 / 1e4
    if kind == "flood":
        water = (d_hh < -3) & (_db(hh_a) < -18)
        flooded_veg = (d_hh > 3) & ((np.abs(_db(hv_a) - _db(hv_b)) < 1.5) if hv_a is not None else True)
        change = np.where(water, -1.0, np.where(flooded_veg, 1.0, np.nan)).astype("float32")
        w_water = raster.window(water.astype("float32"), prof, lat, lon, radius_m)
        w_veg = raster.window(flooded_veg.astype("float32"), prof, lat, lon, radius_m)
        facts = {"open_water_ha": round(float(np.nansum(w_water) * px_ha), 1),
                 "flooded_vegetation_ha": round(float(np.nansum(w_veg) * px_ha), 1)}
        layer = raster.render_png(change, prof, f"flood_{a.id}", "coolwarm", -1, 1)
        layer["title"] = "Flood: blue = open water, red = flooded vegetation"
    else:
        if hv_a is None or hv_b is None:
            return {"error": "deforestation needs the HV channel"}
        d_hv = _db(hv_a) - _db(hv_b)
        loss = np.where(d_hv < -3, d_hv, np.nan).astype("float32")
        w = raster.window(np.isfinite(loss).astype("float32"), prof, lat, lon, radius_m)
        facts = {"vegetation_loss_ha": round(float(np.nansum(w) * px_ha), 1),
                 "hv_change_db_at_point": round(float(np.nanmedian(raster.window(d_hv, prof, lat, lon, POINT_RADIUS_M))), 2)}
        layer = raster.render_png(loss, prof, f"defor_{a.id}", "YlOrRd_r", -8, -3)
        layer["title"] = "Vegetation loss (HV drop, dB)"
    w_dhh = raster.window(d_hh, prof, lat, lon, POINT_RADIUS_M)
    facts.update({"kind": kind, "before": b.ref[:8], "after": a.ref[:8], "direction": a.direction,
                  "hh_change_db_at_point": None if not np.isfinite(w_dhh).any() else round(float(np.nanmedian(w_dhh)), 2),
                  "radius_m": radius_m, "layer": layer})
    return facts
