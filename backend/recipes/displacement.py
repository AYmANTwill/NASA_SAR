"""Recipe 'sudden_motion': ground displacement between two NISAR passes (one GUNW pair).

phase (rad) -> line-of-sight displacement (cm), low-coherence and badly unwrapped pixels masked,
referenced to a stable area far from the point."""
from __future__ import annotations

from functools import lru_cache

import numpy as np

import raster
from catalog import Product
from recipes import corrections as corrections_mod
from config import COHERENCE_MIN, LOS_SIGN, POINT_RADIUS_M, SIGN_BASIS, WAVELENGTH_M
from uncertainty import robust_sigma

REF_DISTANCE_M = 25_000      # reference area = pixels farther than this from the point
REF_SAME_COMPONENT_MIN = 0.9  # share of reference pixels that must be in the point's connected component


def los_cm(p: Product, corrections: tuple | None = None, signs: tuple = ()):
    """Displacement map in cm (not yet referenced), coherence map, profile, notes.
    corrections: names from recipes/corrections.py (None = the NISAR_CORRECTIONS setting, default "iono")."""
    return los_cm_full(p, corrections, signs)[:4]


def los_cm_full(p: Product, corrections: tuple | None = None, signs: tuple = ()):
    """Like los_cm, plus the per-correction report {name: {applied, reason, convention, units, ...}}."""
    names = corrections_mod.active() if corrections is None else tuple(corrections)
    return _los_cm(p, names, tuple(signs))


@lru_cache(maxsize=8)
def _los_cm(p: Product, names: tuple, signs: tuple):
    phase, prof = raster.read(p.files["phase"])
    phase, report = corrections_mod.apply(p, phase, prof, names, WAVELENGTH_M, dict(signs))
    notes = ["ionospheric correction applied"] if report.get("iono", {}).get("applied") else []
    notes += [f"{n} correction applied" for n in ("tropo", "tide") if report.get(n, {}).get("applied")]
    coh = raster.read(p.files["coherence"])[0] if "coherence" in p.files else np.ones_like(phase)
    disp = LOS_SIGN * (-WAVELENGTH_M / (4 * np.pi)) * phase * 100.0
    bad = ~np.isfinite(disp) | (coh < COHERENCE_MIN)
    if "conncomp" in p.files:
        cc, _ = raster.read(p.files["conncomp"])
        if cc.shape == disp.shape:
            bad |= cc == 0
    disp = np.where(bad, np.nan, disp).astype("float32")
    return disp, coh, prof, tuple(notes), report


@lru_cache(maxsize=8)
def _components_raster(p: Product):
    if "conncomp" not in p.files:
        return None
    cc, _ = raster.read(p.files["conncomp"])
    return np.nan_to_num(cc, nan=0).astype("uint32")


def _reference_component(p: Product, d, prof, lat: float, lon: float) -> dict:
    """Phase is only unwrapped consistently inside one connected component; a reference taken in another component can be
    off by whole fringes. Reports the point's component and the share of the reference pixels that are in it."""
    out = {"point_component": None, "reference_share_in_point_component": None, "reference_same_component": None}
    cc = _components_raster(p)
    if cc is None or cc.shape != d.shape:
        return out
    wcc = raster.window(cc, prof, lat, lon, POINT_RADIUS_M)
    wd = raster.window(d, prof, lat, lon, POINT_RADIUS_M)
    lab = wcc[np.isfinite(wd) & (wcc > 0)]
    if lab.size == 0:
        return out
    point_cc = int(np.bincount(lab.astype(np.int64)).argmax())
    far = raster.distance_mask(prof, lat, lon, REF_DISTANCE_M) & np.isfinite(d)
    if far.sum() < 500:
        far = np.isfinite(d)
    share = float((cc[far] == point_cc).mean())
    out.update(point_component=point_cc, reference_share_in_point_component=round(share, 2),
               reference_same_component=bool(share >= REF_SAME_COMPONENT_MIN))
    return out


def reference_mask(disp, prof, lat: float, lon: float):
    """The stable reference area: valid pixels farther than REF_DISTANCE_M from the point (whole scene if too few)."""
    far = raster.distance_mask(prof, lat, lon, REF_DISTANCE_M) & np.isfinite(disp)
    return far if far.sum() >= 500 else np.isfinite(disp)


def referenced(p: Product, lat: float, lon: float, corrections: tuple | None = None, signs: tuple = ()):
    disp, coh, prof, notes = los_cm(p, corrections, signs)
    far = reference_mask(disp, prof, lat, lon)
    ref = float(np.nanmedian(disp[far])) if far.any() else 0.0
    d = disp - ref
    sigma = robust_sigma(d[far])
    return d, coh, prof, sigma, notes


def analyze(p: Product, lat: float, lon: float, make_layer: bool = True) -> dict:
    d, coh, prof, sigma, notes = referenced(p, lat, lon)
    names = corrections_mod.active()
    report = los_cm_full(p, names)[4]
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
        "iono_applied": "ionospheric correction applied" in notes,
        "corrections_requested": list(names),
        "corrections_applied": [n for n in names if report.get(n, {}).get("applied")],
        "corrections": report,
        "sign_basis": SIGN_BASIS,
        "meaning": "positive = ground moved toward the satellite" if LOS_SIGN > 0 else
                   "positive = ground moved away from the satellite",
    }
    facts.update(_reference_component(p, d, prof, lat, lon))
    if make_layer:
        lim = float(np.nanpercentile(np.abs(d), 98)) if np.isfinite(d).any() else 1.0
        facts["layer"] = raster.render_png(d, prof, f"disp_{p.id}", "RdBu_r", -lim, lim)
        facts["layer"]["title"] = f"Displacement (cm), {p.direction}, {p.ref[:8]}→{p.sec[:8]}"
    return facts
