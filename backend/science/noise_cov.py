"""Spatially correlated noise of a track, from a pre-event pair (plan_validation.json part 2).

1. Empirical semivariogram of a pre-event LOS map (same geometry as the co-seismic pair, same processing, a linear
   ramp removed): gamma(h) = 1/2 mean (v_i - v_j)^2 over point pairs at distance h.
2. Fit gamma(h) = nugget + sill (1 - exp(-h / range)). The covariance is C(h) = sill exp(-h / range), plus the
   nugget on the diagonal.
3. C on the co-seismic points gives the Cholesky factor L (C = L L^T) used by the inversion (generalised least
   squares) and by the Monte-Carlo uncertainty (noise realisations L z).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import curve_fit

MAX_PAIRS = 300_000
N_BINS = 20
MIN_PAIRS_PER_BIN = 30


@dataclass(frozen=True)
class NoiseModel:
    sill_cm2: float          # correlated variance
    range_km: float          # e-folding distance
    nugget_cm2: float        # uncorrelated variance
    source: str              # the pre-event pair it comes from
    bins: tuple = ()         # (h_km, gamma_cm2, n_pairs) of the empirical variogram

    @property
    def sigma_cm(self) -> float:
        return math.sqrt(self.sill_cm2 + self.nugget_cm2)

    def covariance(self, east: np.ndarray, north: np.ndarray) -> np.ndarray:
        h = np.hypot(east[:, None] - east[None, :], north[:, None] - north[None, :])
        return self.sill_cm2 * np.exp(-h / self.range_km) + self.nugget_cm2 * np.eye(east.size)

    def cholesky(self, east: np.ndarray, north: np.ndarray) -> np.ndarray:
        c = self.covariance(east, north)
        return np.linalg.cholesky(c + 1e-9 * np.trace(c) / c.shape[0] * np.eye(c.shape[0]))

    def summary(self) -> dict:
        return {"sill_cm2": self.sill_cm2, "range_km": self.range_km, "nugget_cm2": self.nugget_cm2,
                "sigma_cm": self.sigma_cm, "source": self.source, "variogram_bins": list(self.bins)}


def deramp(east: np.ndarray, north: np.ndarray, v: np.ndarray) -> np.ndarray:
    G = np.column_stack([np.ones_like(east), east, north])
    return v - G @ np.linalg.lstsq(G, v, rcond=None)[0]


def semivariogram(east: np.ndarray, north: np.ndarray, v: np.ndarray, max_km: float | None = None,
                  n_bins: int = N_BINS, seed: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(bin centres km, gamma cm², pairs per bin) from random point pairs (at most MAX_PAIRS)."""
    n = v.size
    if n < 10:
        raise ValueError(f"too few points for a variogram ({n})")
    rng = np.random.default_rng(seed)
    m = min(MAX_PAIRS, n * (n - 1) // 2)
    i, j = rng.integers(0, n, m), rng.integers(0, n, m)
    keep = i != j
    i, j = i[keep], j[keep]
    h = np.hypot(east[i] - east[j], north[i] - north[j])
    g = 0.5 * (v[i] - v[j]) ** 2
    max_km = max_km or float(np.percentile(h, 60))       # at large lags few pairs and the ramp removal bias
    edges = np.linspace(0, max_km, n_bins + 1)
    idx = np.digitize(h, edges) - 1
    centres, gam, cnt = [], [], []
    for b in range(n_bins):
        sel = idx == b
        if sel.sum() >= MIN_PAIRS_PER_BIN:
            centres.append(float(h[sel].mean()))
            gam.append(float(g[sel].mean()))
            cnt.append(int(sel.sum()))
    return np.array(centres), np.array(gam), np.array(cnt)


def _model(h, nugget, sill, rng_km):
    return nugget + sill * (1.0 - np.exp(-h / rng_km))


def fit_variogram(h: np.ndarray, gamma: np.ndarray, counts: np.ndarray, source: str) -> NoiseModel:
    """Least-squares fit of the exponential model, weighted by the pairs per bin, all parameters >= 0."""
    if h.size < 4:
        raise ValueError("too few variogram bins to fit a model")
    top = float(gamma.max())
    p0 = (0.1 * top, 0.9 * top, float(h.max()) / 3)
    try:
        (nug, sill, rng_km), _ = curve_fit(_model, h, gamma, p0=p0, sigma=1 / np.sqrt(counts),
                                           bounds=([0, 0, 1e-3], [np.inf, np.inf, 10 * float(h.max())]),
                                           maxfev=20000)
    except RuntimeError as exc:
        raise ValueError(f"variogram fit failed: {exc}") from exc
    bins = tuple((round(float(a), 3), round(float(b), 4), int(c)) for a, b, c in zip(h, gamma, counts))
    return NoiseModel(float(sill), float(rng_km), float(nug), source, bins)


def from_points(east: np.ndarray, north: np.ndarray, los: np.ndarray, source: str) -> NoiseModel:
    v = deramp(east, north, los)
    if float(np.std(v)) < 1e-6:
        raise ValueError(f"{source}: the pre-event map has no measurable noise (constant field?)")
    return fit_variogram(*semivariogram(east, north, v), source=source)
