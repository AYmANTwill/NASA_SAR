"""Automatic discovery: scan every downloaded geometry and list the zones that move.

Per track/frame: velocity map if >= 3 pairs, else the latest pair's displacement. A zone = connected
pixels beyond 3x the noise floor with good coherence. Ranked by |motion| x area, then exposure."""
from __future__ import annotations

import json
from collections import defaultdict

import numpy as np
from scipy import ndimage

import catalog
import evidence
import raster
from config import CACHE_DIR
from recipes import displacement, timeseries
from uncertainty import robust_sigma

OUT = CACHE_DIR / "discoveries.json"


def _smooth(arr, size=7):
    """NaN-aware moving average (~0.5 km at 80 m): lowers pixel noise before detection."""
    ok = np.isfinite(arr)
    num = ndimage.uniform_filter(np.where(ok, arr, 0).astype("float64"), size)
    den = ndimage.uniform_filter(ok.astype("float64"), size)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = num / den
    out[den < 0.3] = np.nan
    return out.astype("float32")


def _zones(arr, prof, unit, source, geom, direction, min_pixels=12, top=15):
    arr = _smooth(arr)
    sigma = robust_sigma(arr)
    if not np.isfinite(sigma) or sigma == 0:
        return []
    med = float(np.nanmedian(arr))
    hot = np.isfinite(arr) & (np.abs(arr - med) > 3 * sigma)
    hot = ndimage.binary_opening(hot, iterations=1)
    lab, n = ndimage.label(hot)
    if n == 0:
        return []
    px_km2 = (raster.pixel_size_m(prof) / 1000) ** 2
    idx = np.arange(1, n + 1)
    sizes = ndimage.sum(hot, lab, idx)
    means = ndimage.mean(np.nan_to_num(arr - med), lab, idx)
    peaks = ndimage.maximum(np.abs(np.nan_to_num(arr - med)), lab, idx)
    centers = ndimage.center_of_mass(hot, lab, idx)
    zones = []
    for i, size, mean, peak, (r, c) in zip(idx, sizes, means, peaks, centers):
        if size < min_pixels:
            continue
        lon, lat = raster.to_lonlat(prof, r, c)
        zones.append({"lat": round(lat, 5), "lon": round(lon, 5), "area_km2": round(float(size * px_km2), 2),
                      "mean": round(float(mean), 2), "peak": round(float(peak), 2), "unit": unit,
                      "snr": round(float(abs(mean) / sigma), 1), "source": source,
                      "track": geom[0], "frame": geom[1], "direction": direction,
                      "score": float(abs(mean) / sigma * np.sqrt(size))})
    return sorted(zones, key=lambda z: -z["score"])[:top]


def scan(with_exposure: bool = True, top: int = 20) -> dict:
    groups = defaultdict(list)
    for p in catalog.load():
        if p.level == "GUNW":
            groups[p.series_key].append(p)      # geometry AND CRID: never mix product versions
    zones = []
    for geom, ps in groups.items():
        twelve = [p for p in ps if p.span_days in (12, 24)]
        res = timeseries.velocity_map(twelve) if len(twelve) >= 3 else None
        if res is not None:
            vel, prof = res
            zones += _zones(vel, prof, "mm/yr", f"velocity from {len(twelve)} pairs", geom, ps[0].direction)
        else:
            latest = max(ps, key=lambda p: p.sec)
            d, _, prof, _ = displacement.los_cm(latest)
            zones += _zones(d, prof, "cm", f"pair {latest.ref[:8]}→{latest.sec[:8]}", geom, latest.direction)
    zones = sorted(zones, key=lambda z: -z["score"])[:top]
    for rank, z in enumerate(zones, 1):
        z["rank"] = rank
        z["confidence"] = "high" if z["snr"] >= 5 else "medium" if z["snr"] >= 3 else "low"
        if with_exposure:
            e = evidence.exposure(z["lat"], z["lon"], 1500)
            z["exposure"] = e.get("counts") if e["status"] != "unavailable" else None
            z["exposed"] = e.get("exposed")
        z["alert_level"] = ("red" if z["confidence"] == "high" and z.get("exposed") else
                            "orange" if z["confidence"] in ("high", "medium") else "yellow")
        z["id"] = f"zone-{rank}"
    out = {"zones": zones, "n_geometries": len(groups), "note":
           "Velocity maps need >= 3 pairs per geometry; with fewer, the latest pair is used."}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def cached() -> dict:
    return json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else scan(with_exposure=False)
