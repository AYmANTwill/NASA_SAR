"""Recipe 'sudden_motion': ground displacement between two NISAR passes (one GUNW pair).

phase (rad) -> line-of-sight displacement (cm), low-coherence and badly unwrapped pixels masked,
referenced to a stable area far from the point."""
from __future__ import annotations

from functools import lru_cache

import numpy as np

import raster
from catalog import Product
from config import COHERENCE_MIN, LOS_SIGN, POINT_RADIUS_M, WAVELENGTH_M
from uncertainty import robust_sigma

REF_DISTANCE_M = 25_000      # reference area = pixels farther than this from the point


@lru_cache(maxsize=8)
def los_cm(p: Product):
    """Displacement map in cm (not yet referenced), coherence map, profile, notes."""
    phase, prof = raster.read(p.files["phase"])
    notes = []
    if "iono" in p.files:
        iono, _ = raster.read(p.files["iono"])
        if iono.shape == phase.shape:
            phase = phase - np.nan_to_num(iono)
            notes.append("ionospheric correction applied")
    coh = raster.read(p.files["coherence"])[0] if "coherence" in p.files else np.ones_like(phase)
    disp = LOS_SIGN * (-WAVELENGTH_M / (4 * np.pi)) * phase * 100.0
    bad = ~np.isfinite(disp) | (coh < COHERENCE_MIN)
    if "conncomp" in p.files:
        cc, _ = raster.read(p.files["conncomp"])
        if cc.shape == disp.shape:
            bad |= cc == 0
    disp = np.where(bad, np.nan, disp).astype("float32")
    return disp, coh, prof, tuple(notes)


def referenced(p: Product, lat: float, lon: float):
    disp, coh, prof, notes = los_cm(p)
    far = raster.distance_mask(prof, lat, lon, REF_DISTANCE_M) & np.isfinite(disp)
    if far.sum() < 500:                              # small frame: use the whole scene
        far = np.isfinite(disp)
    ref = float(np.nanmedian(disp[far])) if far.any() else 0.0
    d = disp - ref
    sigma = robust_sigma(d[far])
    return d, coh, prof, sigma, notes


def analyze(p: Product, lat: float, lon: float, make_layer: bool = True) -> dict:
    d, coh, prof, sigma, notes = referenced(p, lat, lon)
    w = raster.window(d, prof, lat, lon, POINT_RADIUS_M)
    wc = raster.window(coh, prof, lat, lon, POINT_RADIUS_M)
    big = raster.window(d, prof, lat, lon, 10_000)
    signal = float(np.nanmedian(w)) if np.isfinite(w).any() else float("nan")
    facts = {
        "product": p.id, "direction": p.direction, "track": p.track, "frame": p.frame,
        "date_before": p.ref[:8], "date_after": p.sec[:8], "span_days": p.span_days,
        "los_cm": None if not np.isfinite(signal) else round(signal, 2),
        "noise_cm": None if not np.isfinite(sigma) else round(sigma, 2),
        "coherence": round(float(np.nanmedian(wc)), 2) if wc.size else None,
        "masked_fraction_10km": round(float(np.mean(~np.isfinite(big))), 2) if big.size else 1.0,
        "max_abs_cm_10km": round(float(np.nanmax(np.abs(big))), 2) if np.isfinite(big).any() else None,
        "profile": raster.profile_line(d, prof, lat, lon),
        "notes": list(notes),
        "meaning": "positive = ground moved toward the satellite" if LOS_SIGN > 0 else
                   "positive = ground moved away from the satellite",
    }
    if make_layer:
        lim = float(np.nanpercentile(np.abs(d), 98)) if np.isfinite(d).any() else 1.0
        facts["layer"] = raster.render_png(d, prof, f"disp_{p.id}", "RdBu_r", -lim, lim)
        facts["layer"]["title"] = f"Displacement (cm), {p.direction}, {p.ref[:8]}→{p.sec[:8]}"
    return facts
