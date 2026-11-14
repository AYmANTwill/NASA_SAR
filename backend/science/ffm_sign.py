"""LOS sign test independent of the inversion: the USGS finite-fault model, run forward with Okada, against each track.

For each track: observed LOS ≈ k · model + a + b·east + c·north (linear least squares).
- k > 0 by more than 3σ: the data agree with the current NISAR_LOS_SIGN (positive = toward the satellite);
- k < 0 by more than 3σ: the sign is flipped;
- otherwise: inconclusive.
k is scale-free (the model runs with 1 m of uniform slip), so only its sign and significance matter.

Geometry of the USGS finite-fault model for us6000u18k (as given by the team): strike 295°, dip 60°, rake -16°,
length 55 km, width 33.6 km, centre 7.54 N 80.769 W.
Assumptions:
- the centre is the surface projection of the fault-plane centre;
- the top depth is 0 km unless set (it is not given; the sign of k barely depends on it).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from science.invert_fault import Track
from science.okada import fault_enu

SIGNIFICANCE = 3.0
KM_PER_DEG_LAT = 110.574
KM_PER_DEG_LON_EQ = 111.320


@dataclass(frozen=True)
class FiniteFault:
    strike: float
    dip: float
    rake: float
    length_km: float
    width_km: float
    lat: float
    lon: float
    top_depth_km: float = 0.0
    source: str = "USGS finite-fault model us6000u18k"


USGS_FFM_PANAMA = FiniteFault(295.0, 60.0, -16.0, 55.0, 33.6, 7.54, -80.769)


def forward(ff: FiniteFault, tracks: list[Track], lat0: float, lon0: float) -> list[np.ndarray]:
    """Model LOS (cm, + toward the satellite) on each track for 1 m of slip. Tracks are in km around (lat0, lon0)."""
    cx = (ff.lon - lon0) * KM_PER_DEG_LON_EQ * math.cos(math.radians(lat0))
    cy = (ff.lat - lat0) * KM_PER_DEG_LAT
    phi, dip = math.radians(ff.strike), math.radians(ff.dip)
    h = ff.width_km / 2.0 * math.cos(dip)            # top edge is up-dip of the centre, against the dip direction
    x0, y0 = cx - h * math.cos(phi), cy + h * math.sin(phi)
    out = []
    for t in tracks:
        ue, un, uu = fault_enu(t.east, t.north, x0=x0, y0=y0, strike_deg=ff.strike, dip_deg=ff.dip,
                               rake_deg=ff.rake, top_depth=ff.top_depth_km, length=ff.length_km,
                               width=ff.width_km, slip=1.0)
        out.append(100.0 * (ue * t.vec[:, 0] + un * t.vec[:, 1] + uu * t.vec[:, 2]))
    return out


def _deramp(v: np.ndarray, ramp: np.ndarray) -> np.ndarray:
    return v - ramp @ np.linalg.lstsq(ramp, v, rcond=None)[0]


def scale_fit(obs: np.ndarray, model: np.ndarray, east: np.ndarray, north: np.ndarray) -> dict:
    """k, sigma_k, partial correlation (ramps removed) and verdict of obs ≈ k·model + ramp."""
    ramp = np.column_stack([np.ones_like(model), east, north])
    G = np.column_stack([model, ramp])
    coef, *_ = np.linalg.lstsq(G, obs, rcond=None)
    resid = obs - G @ coef
    dof = max(obs.size - G.shape[1], 1)
    try:
        sk = float(math.sqrt(max((np.linalg.inv(G.T @ G) * float(resid @ resid) / dof)[0, 0], 0.0)))
    except np.linalg.LinAlgError:
        sk = float("nan")
    o, m = _deramp(obs, ramp), _deramp(model, ramp)
    denom = float(np.linalg.norm(o) * np.linalg.norm(m))
    k = float(coef[0])
    if math.isfinite(sk) and sk > 0 and abs(k) / sk > SIGNIFICANCE:
        verdict = "consistent" if k > 0 else "flipped"
    else:
        verdict = "inconclusive"
    return {"k": k, "sigma_k": sk, "partial_r": float(o @ m) / denom if denom > 0 else 0.0, "verdict": verdict}


def sign_check(tracks: list[Track], lat0: float, lon0: float, los_sign: float,
               ff: FiniteFault = USGS_FFM_PANAMA) -> dict:
    """Per-track verdicts and an overall one (unanimous among the conclusive tracks, else 'mixed')."""
    per = {t.name: scale_fit(t.los, m, t.east, t.north) for t, m in zip(tracks, forward(ff, tracks, lat0, lon0))}
    conclusive = {v["verdict"] for v in per.values()} - {"inconclusive"}
    overall = conclusive.pop() if len(conclusive) == 1 else ("inconclusive" if not conclusive else "mixed")
    return {"model": vars(ff), "los_sign_tested": los_sign, "per_track": per, "overall": overall,
            "meaning": "consistent = the current NISAR_LOS_SIGN matches the USGS model; flipped = use the opposite"}
