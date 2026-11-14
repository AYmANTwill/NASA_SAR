"""Uniform-slip rectangular fault from co-seismic NISAR line-of-sight displacement (Okada 1985).

Fixed: strike, dip and rake, from each USGS moment-tensor nodal plane in turn (the lower misfit is kept, both
are reported).
Free:
- the position of the top-edge centre, along strike and across strike, relative to the USGS epicentre (km);
- length, width and top depth (km);
- uniform slip (m);
- a linear ramp a + b·east + c·north per track (cm), with one offset a per connected component.

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
import time
from dataclasses import dataclass, field

import numpy as np
from scipy.linalg import solve_triangular
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
    chol: np.ndarray | None = field(default=None, compare=False)   # L of the noise covariance C = L L^T (cm)
    comp: np.ndarray | None = field(default=None, compare=False)   # connected-component index 0..k-1 per sample


@dataclass
class PlaneFit:
    plane: Plane
    theta: np.ndarray
    rms_cm: float
    variance_reduction: float
    cov: np.ndarray | None
    at_bound: list = field(default_factory=list)
    boot: np.ndarray | None = None     # (n_ok, 6) fault parameters of the bootstrap / Monte-Carlo fits
    boot_failed: int = 0
    boot_method: str = "point_bootstrap"


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
def fault_los(theta6: np.ndarray, tracks: list[Track], plane: Plane) -> list[np.ndarray]:
    """LOS (cm) of the fault alone on each track, no ramp."""
    along, across, length, width, top, slip = theta6[:6]
    phi = math.radians(plane.strike)
    x0 = along * math.sin(phi) + across * math.cos(phi)        # across = horizontal dip direction
    y0 = along * math.cos(phi) - across * math.sin(phi)
    out = []
    for t in tracks:
        ue, un, uu = fault_enu(t.east, t.north, x0=x0, y0=y0, strike_deg=plane.strike, dip_deg=plane.dip,
                               rake_deg=plane.rake, top_depth=top, length=length, width=width, slip=slip)
        out.append(100.0 * (ue * t.vec[:, 0] + un * t.vec[:, 1] + uu * t.vec[:, 2]))
    return out


def ramp_design(east: np.ndarray, north: np.ndarray, comp: np.ndarray | None = None) -> np.ndarray:
    """Columns [offset of each connected component, east, north]: one offset per component absorbs the 2π (one
    fringe) jumps between components; the gradient is shared by the whole track. comp None = one component."""
    if comp is None:
        offsets = np.ones((east.size, 1))
    else:
        offsets = (np.asarray(comp)[:, None] == np.arange(int(np.max(comp)) + 1)[None, :]).astype(float)
    return np.column_stack([offsets, east, north])


def n_ramp(t: Track) -> int:
    return 3 if t.comp is None else int(np.max(t.comp)) + 3


def predict(theta: np.ndarray, tracks: list[Track], plane: Plane) -> list[np.ndarray]:
    """Fault LOS + the ramp of each track: theta[6:] holds, track after track, the ramp_design coefficients."""
    out, k = [], 6
    for t, m in zip(tracks, fault_los(theta, tracks, plane)):
        n = n_ramp(t)
        out.append(m + ramp_design(t.east, t.north, t.comp) @ theta[k:k + n])
        k += n
    return out


def _whiten(t: Track, v: np.ndarray) -> np.ndarray:
    return v if t.chol is None else solve_triangular(t.chol, v, lower=True)


def _ramp_operators(tracks: list[Track]) -> list[tuple[np.ndarray, np.ndarray]]:
    """(Gw, pinv(Gw)) with G = ramp_design, whitened by the track's noise covariance when it has one."""
    ops = []
    for t in tracks:
        Gw = _whiten(t, ramp_design(t.east, t.north, t.comp))
        ops.append((Gw, np.linalg.pinv(Gw)))
    return ops


def _residuals6(theta6, tracks, plane, ops):
    """Variable projection: the per-track ramps are solved linearly for each fault model (generalised least
    squares when the track has a noise covariance)."""
    out = []
    for (Gw, Gp), t, m in zip(ops, tracks, fault_los(theta6, tracks, plane)):
        rw = _whiten(t, t.los - m)
        out.append(Gw @ (Gp @ rw) - rw)
    return np.concatenate(out)


def _ramps(theta6, tracks, plane) -> np.ndarray:
    ops = _ramp_operators(tracks)
    return np.concatenate([Gp @ _whiten(t, t.los - m)
                           for (_, Gp), t, m in zip(ops, tracks, fault_los(theta6, tracks, plane))])


def _solve(theta6_0, tracks, plane):
    ops = _ramp_operators(tracks)
    return least_squares(_residuals6, np.clip(theta6_0[:6], LOWER, UPPER), bounds=(LOWER, UPPER), x_scale="jac",
                         args=(tracks, plane, ops), max_nfev=400)


# ---------------------------------------------------------------- fit + uncertainty
def fit_plane(tracks: list[Track], plane: Plane, starts=STARTS) -> PlaneFit:
    """Multi-start least squares for one nodal plane; covariance of the 6 fault parameters from the Jacobian
    (ramps projected out) scaled by the residual variance."""
    best = None
    for length, width, top in starts:
        res = _solve(np.array([0.0, 0.0, length, width, top, 1.0]), tracks, plane)
        if best is None or res.cost < best.cost:
            best = res
    rw = best.fun                                   # whitened when the tracks carry a noise covariance
    n, p = rw.size, 6 + sum(n_ramp(t) for t in tracks)
    s2 = float(rw @ rw) / max(n - p, 1)
    whitened = all(t.chol is not None for t in tracks)
    try:
        # with a noise model, s2 ~ 1 when the model is right; never let a small s2 shrink the model's uncertainty
        cov = np.linalg.inv(best.jac.T @ best.jac) * (max(s2, 1.0) if whitened else s2)
    except np.linalg.LinAlgError:
        cov = None
    span = UPPER - LOWER
    at_bound = [FAULT_NAMES[i] for i in range(6) if min(best.x[i] - LOWER[i], UPPER[i] - best.x[i]) < 0.01 * span[i]]
    theta = np.concatenate([best.x, _ramps(best.x, tracks, plane)])
    r = np.concatenate([t.los - m for t, m in zip(tracks, predict(theta, tracks, plane))])   # cm, not whitened
    data = np.concatenate([t.los - np.median(t.los) for t in tracks])
    vr = 1.0 - float(r @ r) / float(data @ data) if data @ data > 0 else 0.0
    return PlaneFit(plane, theta, math.sqrt(float(r @ r) / r.size), vr, cov, at_bound)


def _relabel(comp: np.ndarray) -> np.ndarray:
    """Component labels 0..k-1 again after resampling (a component may have no point left)."""
    return np.unique(comp, return_inverse=True)[1]


def bootstrap(fit: PlaneFit, tracks: list[Track], n_runs: int = N_BOOT, seed: int = 0) -> PlaneFit:
    """Uncertainty by refitting n_runs perturbed data sets, warm-started at the best fit.
    - every track has a noise covariance: Monte Carlo, best model + correlated noise L z (spatial correlation in);
    - otherwise: points resampled with replacement inside each track (assumes independent points: a lower bound)."""
    rng = np.random.default_rng(seed)
    params, failed = [], 0
    monte_carlo = all(t.chol is not None for t in tracks)
    best_model = predict(fit.theta, tracks, fit.plane) if monte_carlo else None
    fit.boot_method = "monte_carlo_correlated_noise" if monte_carlo else "point_bootstrap"
    for _ in range(n_runs):
        sample = []
        for i, t in enumerate(tracks):
            if monte_carlo:
                noisy = best_model[i] + t.chol @ rng.standard_normal(t.los.size)
                sample.append(Track(t.name, t.east, t.north, noisy, t.vec, chol=t.chol, comp=t.comp))
            else:
                k = rng.integers(0, t.los.size, t.los.size)
                sample.append(Track(t.name, t.east[k], t.north[k], t.los[k], t.vec[k],
                                    comp=None if t.comp is None else _relabel(t.comp[k])))
        res = _solve(fit.theta[:6], sample, fit.plane)
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
    mw_cov = mw_sigma_from_cov(th[:6], fit.cov)
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
            "bootstrap_runs": int(len(boot)), "bootstrap_failed": fit.boot_failed,
            "uncertainty_method": fit.boot_method}


def per_track_vr(fit: PlaneFit, tracks: list[Track]) -> dict[str, float]:
    """1 - sum(residual²) / sum((data - median)²) for each track: with NISAR_LOS_SIGN wrong it collapses."""
    out = {}
    for t, p in zip(tracks, predict(fit.theta, tracks, fit.plane)):
        d = t.los - np.median(t.los)
        r = t.los - p
        out[t.name] = float(1.0 - (r @ r) / (d @ d)) if d @ d > 0 else 0.0
    return out


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
    fits, timing = [], []
    for p in planes:
        t0 = time.perf_counter()
        fit = fit_plane(tracks, p)
        t1 = time.perf_counter()
        fits.append(bootstrap(fit, tracks, n_boot, seed))
        t2 = time.perf_counter()
        timing.append({"fit_s": round(t1 - t0, 2), "bootstrap_s": round(t2 - t1, 2),
                       "per_bootstrap_run_s": round((t2 - t1) / n_boot, 3) if n_boot else None})
    summaries = [{**summarize(f), "variance_reduction_per_track": per_track_vr(f, tracks), "timing": tm}
                 for f, tm in zip(fits, timing)]
    best = int(np.argmin([s["rms_cm"] for s in summaries]))
    reasons = stability(summaries[best], n_boot)
    result = {"planes": summaries, "best_plane": best, "stable": not reasons, "unstable_reasons": reasons,
              "n_points": {t.name: int(t.los.size) for t in tracks},
              "track_notes": {t.name: list(t.notes) for t in tracks}}
    return result, fits
