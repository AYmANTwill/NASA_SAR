"""Uniform-slip rectangular fault from co-seismic NISAR line-of-sight displacement (Okada 1985).

Fixed: strike, dip and rake, from each USGS moment-tensor nodal plane in turn (the lower misfit is kept, both
are reported).
Free:
- the position of the top-edge centre, along strike and across strike, relative to the USGS epicentre (km);
- length, width and top depth (km);
- uniform slip (m);
- a linear ramp a + b·east + c·north per track (cm).

Model in LOS: d_los = u · ê, with ê the ground-to-satellite unit vector, so positive = toward the satellite
(LOS_SIGN = 1).

Uncertainty, two estimates:
- covariance from the Jacobian, scaled by the residual variance;
- a bootstrap over points (>= 50 runs).
The reported sigma is the larger of the two. Both ignore the spatial correlation of InSAR noise, so they are lower
bounds; science/panama_fault.py states this in the limits.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import least_squares

from science.okada import fault_enu
from science.usgs import Plane

MU_PA = 30e9                 # shear modulus for M0 = mu L W s
N_BOOT = 50
MW_SIGMA_MAX = 0.15          # above this bootstrap sigma the magnitude is "not estimated"
MIN_VARIANCE_REDUCTION = 0.5
FAULT_NAMES = ("along_km", "across_km", "length_km", "width_km", "top_depth_km", "slip_m")
LOWER = np.array([-100.0, -100.0, 5.0, 3.0, 0.0, 0.01])
UPPER = np.array([100.0, 100.0, 400.0, 80.0, 40.0, 20.0])
RAMP_BOUND = np.array([1e3, 10.0, 10.0])   # offset cm, gradients cm/km
STARTS = [(L, W, top) for (L, W) in ((30.0, 15.0), (80.0, 25.0), (150.0, 35.0)) for top in (1.0, 8.0)]


@dataclass(frozen=True)
class Track:
    name: str
    east: np.ndarray          # km, local tangent plane around the USGS epicentre
    north: np.ndarray
    los: np.ndarray           # cm, positive toward the satellite
    vec: np.ndarray           # (N, 3) ground-to-satellite unit vectors (east, north, up)
    notes: tuple = ()


@dataclass
class PlaneFit:
    plane: Plane
    theta: np.ndarray
    rms_cm: float
    variance_reduction: float
    cov: np.ndarray | None
    at_bound: list = field(default_factory=list)
    boot: np.ndarray | None = None     # (n_ok, 6) fault parameters of the bootstrap fits
    boot_failed: int = 0


def moment_mw(length_km: float, width_km: float, slip_m: float) -> tuple[float, float]:
    """(M0 in N·m, Mw) with M0 = mu L W s and Mw = 2/3 (log10 M0 - 9.1)."""
    m0 = MU_PA * length_km * 1e3 * width_km * 1e3 * slip_m
    return m0, (2.0 / 3.0) * (math.log10(m0) - 9.1)


def mw_sigma_from_cov(theta: np.ndarray, cov: np.ndarray | None) -> float | None:
    """First-order propagation: dMw = 2/(3 ln10) (dL/L + dW/W + ds/s)."""
    if cov is None:
        return None
    k = 2.0 / (3.0 * math.log(10.0))
    g = np.zeros(len(theta))
    g[2], g[3], g[5] = k / theta[2], k / theta[3], k / theta[5]
    var = float(g @ cov @ g)
    return math.sqrt(var) if var >= 0 else None


# ---------------------------------------------------------------- forward model
def predict(theta: np.ndarray, tracks: list[Track], plane: Plane) -> list[np.ndarray]:
    along, across, length, width, top, slip = theta[:6]
    phi = math.radians(plane.strike)
    x0 = along * math.sin(phi) + across * math.cos(phi)        # across = horizontal dip direction
    y0 = along * math.cos(phi) - across * math.sin(phi)
    out = []
    for i, t in enumerate(tracks):
        ue, un, uu = fault_enu(t.east, t.north, x0=x0, y0=y0, strike_deg=plane.strike, dip_deg=plane.dip,
                               rake_deg=plane.rake, top_depth=top, length=length, width=width, slip=slip)
        a, b, c = theta[6 + 3 * i: 9 + 3 * i]
        los = 100.0 * (ue * t.vec[:, 0] + un * t.vec[:, 1] + uu * t.vec[:, 2])
        out.append(los + a + b * t.east + c * t.north)
    return out


def _residuals(theta, tracks, plane):
    return np.concatenate([p - t.los for p, t in zip(predict(theta, tracks, plane), tracks)])


def _bounds(n_tracks: int) -> tuple[np.ndarray, np.ndarray]:
    return (np.concatenate([LOWER, np.tile(-RAMP_BOUND, n_tracks)]),
            np.concatenate([UPPER, np.tile(RAMP_BOUND, n_tracks)]))


def _solve(theta0, tracks, plane):
    lo, hi = _bounds(len(tracks))
    return least_squares(_residuals, np.clip(theta0, lo, hi), bounds=(lo, hi), x_scale="jac", args=(tracks, plane),
                         max_nfev=400)


# ---------------------------------------------------------------- fit + uncertainty
def fit_plane(tracks: list[Track], plane: Plane) -> PlaneFit:
    """Multi-start least squares for one nodal plane; covariance from the Jacobian scaled by residual variance."""
    best = None
    for length, width, top in STARTS:
        theta0 = np.concatenate([[0.0, 0.0, length, width, top, 1.0], np.zeros(3 * len(tracks))])
        res = _solve(theta0, tracks, plane)
        if best is None or res.cost < best.cost:
            best = res
    r = best.fun
    n, p = r.size, best.x.size
    data = np.concatenate([t.los - np.median(t.los) for t in tracks])
    vr = 1.0 - float(r @ r) / float(data @ data) if data @ data > 0 else 0.0
    s2 = float(r @ r) / max(n - p, 1)
    try:
        cov = np.linalg.inv(best.jac.T @ best.jac) * s2
    except np.linalg.LinAlgError:
        cov = None
    lo, hi = _bounds(len(tracks))
    span = hi[:6] - lo[:6]
    at_bound = [FAULT_NAMES[i] for i in range(6) if min(best.x[i] - lo[i], hi[i] - best.x[i]) < 0.01 * span[i]]
    return PlaneFit(plane, best.x, math.sqrt(float(r @ r) / n), vr, cov, at_bound)


def bootstrap(fit: PlaneFit, tracks: list[Track], n_runs: int = N_BOOT, seed: int = 0) -> PlaneFit:
    """Refits on point sets resampled with replacement inside each track, warm-started at the best fit."""
    rng = np.random.default_rng(seed)
    params, failed = [], 0
    for _ in range(n_runs):
        sample = []
        for t in tracks:
            k = rng.integers(0, t.los.size, t.los.size)
            sample.append(Track(t.name, t.east[k], t.north[k], t.los[k], t.vec[k]))
        res = _solve(fit.theta, sample, fit.plane)
        if res.success:
            params.append(res.x[:6])
        else:
            failed += 1
    fit.boot = np.array(params) if params else np.zeros((0, 6))
    fit.boot_failed = failed
    return fit


def _num(v) -> float | None:
    return float(v) if v is not None and np.isfinite(v) else None


def summarize(fit: PlaneFit) -> dict:
    """Parameters, Mw and their 1-sigma (the larger of the Jacobian and bootstrap estimates)."""
    th = fit.theta
    m0, mw = moment_mw(th[2], th[3], th[5])
    sd_cov = np.sqrt(np.clip(np.diag(fit.cov)[:6], 0, None)) if fit.cov is not None else np.full(6, np.nan)
    boot = fit.boot if fit.boot is not None else np.zeros((0, 6))
    sd_boot = boot.std(axis=0, ddof=1) if len(boot) > 1 else np.full(6, np.nan)
    boot_mw = np.array([moment_mw(b[2], b[3], b[5])[1] for b in boot])
    mw_cov = mw_sigma_from_cov(th, fit.cov)
    mw_boot = float(boot_mw.std(ddof=1)) if boot_mw.size > 1 else None
    sig = [s for s in (mw_cov, mw_boot) if s is not None and math.isfinite(s)]
    params = {}
    for i, name in enumerate(FAULT_NAMES):
        both = [s for s in (sd_cov[i], sd_boot[i]) if np.isfinite(s)]
        params[name] = {"value": float(th[i]), "sigma_jacobian": _num(sd_cov[i]),
                        "sigma_bootstrap": _num(sd_boot[i]), "sigma": max(both) if both else None}
    return {"plane": vars(fit.plane), "params": params, "m0_nm": m0,
            "mw": {"value": mw, "sigma_jacobian": mw_cov, "sigma_bootstrap": mw_boot,
                   "sigma": max(sig) if sig else None},
            "rms_cm": fit.rms_cm, "variance_reduction": fit.variance_reduction, "at_bound": fit.at_bound,
            "bootstrap_runs": int(len(boot)), "bootstrap_failed": fit.boot_failed}


def stability(summary: dict, n_boot: int) -> list[str]:
    """Reasons why the magnitude must not be reported (empty list = stable)."""
    reasons = []
    s = summary["mw"]["sigma_bootstrap"]
    if s is None or s > MW_SIGMA_MAX:
        reasons.append(f"bootstrap sigma of Mw ({'n/a' if s is None else round(s, 3)}) > {MW_SIGMA_MAX}")
    if summary["at_bound"]:
        reasons.append(f"parameters at a search bound: {', '.join(summary['at_bound'])}")
    if summary["bootstrap_runs"] < 0.8 * n_boot:
        reasons.append(f"only {summary['bootstrap_runs']}/{n_boot} bootstrap fits converged")
    if summary["variance_reduction"] < MIN_VARIANCE_REDUCTION:
        reasons.append(f"variance reduction {summary['variance_reduction']:.2f} < {MIN_VARIANCE_REDUCTION}")
    return reasons


def invert(tracks: list[Track], planes: tuple[Plane, ...], n_boot: int = N_BOOT,
           seed: int = 0) -> tuple[dict, list[PlaneFit]]:
    """Fits and bootstraps every plane, keeps the lower RMS. Returns (JSON-ready summary, the fits)."""
    if not tracks:
        raise ValueError("no track to invert")
    fits = [bootstrap(fit_plane(tracks, p), tracks, n_boot, seed) for p in planes]
    summaries = [summarize(f) for f in fits]
    best = int(np.argmin([s["rms_cm"] for s in summaries]))
    reasons = stability(summaries[best], n_boot)
    result = {"planes": summaries, "best_plane": best, "stable": not reasons, "unstable_reasons": reasons,
              "n_points": {t.name: int(t.los.size) for t in tracks},
              "track_notes": {t.name: list(t.notes) for t in tracks}}
    return result, fits
