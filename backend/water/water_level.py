"""Water-level constraint: a reservoir surface is flat.

For one date: take high-confidence water (probability >= CORE_P), find the boundary pixels of that core,
estimate the water-surface elevation as the median DEM elevation along that boundary, and reject
predicted water whose DEM elevation exceeds that level + T metres. Everything else is kept.
Applies to reservoirs and lakes only (one flat surface); NOT to flash floods on slopes (Haouz).
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import binary_erosion

CORE_P = 0.9


def surface_level(prob: np.ndarray, dem: np.ndarray, core_p: float = CORE_P) -> float:
    core = np.nan_to_num(prob) >= core_p
    edge = core & ~binary_erosion(core, iterations=1)
    z = dem[edge & np.isfinite(dem)]
    return float(np.median(z)) if z.size else float("nan")


def apply(prob: np.ndarray, dem: np.ndarray, thr: float, T: float, level: float | None = None) -> np.ndarray:
    """Boolean water mask after the constraint (pixels without DEM are kept)."""
    lvl = surface_level(prob, dem) if level is None else level
    water = np.nan_to_num(prob) >= thr
    if not np.isfinite(lvl):
        return water
    too_high = np.isfinite(dem) & (dem > lvl + T)
    return water & ~too_high
