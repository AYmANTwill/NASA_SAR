"""Pair quality filter: a GUNW pair that cannot carry a measurement is left out, and listed.

Rejected when (real case: the track 23 pairs touching 2026-09-07):
  - the unwrapped phase is flat: robust sigma below NISAR_FLAT_PHASE_SIGMA_RAD (default 0.001 rad), or no valid phase;
  - the median coherence is below NISAR_MIN_PAIR_COHERENCE (default 0.15).
Statistics use a decimated read (at most ~500 x 500 pixels) of the pixels where the phase is valid; coherence fill
values (0 outside the swath) are not counted. Rejected pairs are excluded from time series, surface-change baselines
(and before / event pairs), sudden-motion pairs, discoveries and the GPS comparison; each answer lists them in
facts["rejected_pairs"]."""
from __future__ import annotations

import math
import os
from functools import lru_cache

import numpy as np

from uncertainty import robust_sigma

FLAT_PHASE_SIGMA_RAD = float(os.environ.get("NISAR_FLAT_PHASE_SIGMA_RAD", "0.001"))
MIN_PAIR_COHERENCE = float(os.environ.get("NISAR_MIN_PAIR_COHERENCE", "0.15"))
MAX_SIDE = 500


def _read_small(path) -> np.ndarray:
    import rasterio
    from rasterio.enums import Resampling
    with rasterio.open(path) as src:
        step = max(1, math.ceil(max(src.width, src.height) / MAX_SIDE))
        arr = src.read(1, out_shape=(math.ceil(src.height / step), math.ceil(src.width / step)),
                       resampling=Resampling.nearest).astype("float32")
        if src.nodata is not None and not np.isnan(src.nodata):
            arr[arr == src.nodata] = np.nan
    return arr


def assess(phase: np.ndarray, coherence: np.ndarray | None,
           flat_sigma: float = FLAT_PHASE_SIGMA_RAD, min_coherence: float = MIN_PAIR_COHERENCE) -> dict:
    """{ok, reasons, phase_sigma_rad, coherence_median} from a phase and a coherence array (pure function)."""
    valid = np.isfinite(phase)
    sigma = robust_sigma(phase[valid]) if valid.any() else float("nan")
    reasons = []
    if not np.isfinite(sigma):
        reasons.append("no valid unwrapped phase")
    elif sigma < flat_sigma:
        reasons.append(f"flat unwrapped phase (robust sigma {sigma:.2g} rad < {flat_sigma:g})")
    coh_med = None
    if coherence is not None and coherence.shape == phase.shape:
        c = coherence[valid & np.isfinite(coherence) & (coherence > 0)]
        coh_med = float(np.median(c)) if c.size else 0.0
        if coh_med < min_coherence:
            reasons.append(f"median coherence {coh_med:.2f} < {min_coherence:g}")
    return {"ok": not reasons, "reasons": reasons,
            "phase_sigma_rad": None if not np.isfinite(sigma) else round(float(sigma), 4),
            "coherence_median": None if coh_med is None else round(coh_med, 3)}


@lru_cache(maxsize=4096)
def check(p) -> dict:
    """Quality of one GUNW product (cached). Products without a phase layer are not judged (ok)."""
    if p.level != "GUNW" or "phase" not in p.files:
        return {"product": p.id, "ok": True, "reasons": [], "phase_sigma_rad": None, "coherence_median": None}
    try:
        ph = _read_small(p.files["phase"])
        coh = _read_small(p.files["coherence"]) if "coherence" in p.files else None
        return {"product": p.id, **assess(ph, coh)}
    except Exception as e:                       # noqa: BLE001 - an unreadable pair is rejected, with the reason
        return {"product": p.id, "ok": False, "reasons": [f"unreadable: {type(e).__name__}"],
                "phase_sigma_rad": None, "coherence_median": None}


def split(products) -> tuple[list, list[dict]]:
    """(good products, rejected [{product, reasons, phase_sigma_rad, coherence_median}])."""
    good, bad = [], []
    for p in products:
        q = check(p)
        if q["ok"]:
            good.append(p)
        else:
            bad.append({k: q[k] for k in ("product", "reasons", "phase_sigma_rad", "coherence_median")})
    return good, bad
