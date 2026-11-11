"""Recipe 'slow_motion': displacement time series from a stack of GUNW pairs (small-baseline inversion).

Point mode: one series per viewing geometry (track/frame), velocity in mm/yr, acceleration.
Map mode: velocity map of a whole stack (used by discoveries)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date

import numpy as np

import raster
from catalog import Product
from recipes import displacement


def _date(s: str) -> date:
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def _design(pairs: list[Product]):
    dates = sorted({p.ref[:8] for p in pairs} | {p.sec[:8] for p in pairs})
    idx = {d: i for i, d in enumerate(dates)}
    A = np.zeros((len(pairs), len(dates) - 1))
    for k, p in enumerate(pairs):            # unknowns = displacement at each date, first date = 0
        i, j = idx[p.ref[:8]], idx[p.sec[:8]]
        if j > 0:
            A[k, j - 1] += 1
        if i > 0:
            A[k, i - 1] -= 1
    return dates, A


def _fit(dates: list[str], series: np.ndarray, sig: np.ndarray):
    t = np.array([(_date(d) - _date(dates[0])).days / 365.25 for d in dates])
    ok = np.isfinite(series)
    out = {}
    if ok.sum() >= 2:
        c, cov = np.polyfit(t[ok], series[ok], 1, cov=ok.sum() > 3)
        out["velocity_mm_yr"] = round(float(c[0]), 1)
        out["velocity_sigma_mm_yr"] = round(float(np.sqrt(cov[0, 0])), 1) if ok.sum() > 3 else None
    if ok.sum() >= 6:                       # report acceleration only when it is significant
        q, qcov = np.polyfit(t[ok], series[ok], 2, cov=True)
        a, sa = 2 * q[0], 2 * np.sqrt(qcov[0, 0])
        if abs(a) > 2 * sa:
            out["acceleration_mm_yr2"] = round(float(a), 1)
            out["acceleration_sigma_mm_yr2"] = round(float(sa), 1)
    return out


def point_series(products: list[Product], lat: float, lon: float) -> list[dict]:
    """One series per geometry. Needs pairs that connect (12- and 24-day pairs)."""
    groups = defaultdict(list)
    for p in products:
        groups[p.geometry].append(p)
    results = []
    for geom, pairs in groups.items():
        pairs = sorted(pairs, key=lambda p: p.ref)
        obs, sig = [], []
        for p in pairs:
            f = displacement.analyze(p, lat, lon, make_layer=False)
            obs.append(np.nan if f["los_cm"] is None else f["los_cm"] * 10)       # mm
            sig.append(np.nan if f["noise_cm"] is None else f["noise_cm"] * 10)
        obs, sig = np.array(obs), np.array(sig)
        ok = np.isfinite(obs)
        dates, A = _design(pairs)
        if ok.sum() == 0 or A.shape[1] == 0:
            continue
        w = 1 / np.where(np.isfinite(sig) & (sig > 0), sig, np.nanmedian(sig[np.isfinite(sig)]) if np.isfinite(sig).any() else 1)
        x, *_ = np.linalg.lstsq(A[ok] * w[ok, None], obs[ok] * w[ok], rcond=None)
        cum = np.concatenate([[0.0], x])
        # dates not connected by any valid pair are unknown
        connected = np.zeros(len(dates), bool)
        connected[0] = True
        for p, good in zip(pairs, ok):
            if good:
                connected[dates.index(p.ref[:8])] = connected[dates.index(p.sec[:8])] = True
        cum = np.where(connected, cum, np.nan)
        noise = float(np.nanmedian(sig)) if np.isfinite(sig).any() else None
        res = {"track": geom[0], "frame": geom[1], "direction": pairs[0].direction,
               "n_pairs": int(ok.sum()), "n_dates": len(dates), "noise_mm": None if noise is None else round(noise, 1),
               "series": [{"date": d, "los_mm": None if not np.isfinite(v) else round(float(v), 1)}
                          for d, v in zip(dates, cum)],
               "total_los_mm": None if not np.isfinite(cum[-1]) else round(float(cum[-1]), 1),
               "first_date": dates[0], "last_date": dates[-1]}
        res.update(_fit(dates, cum, sig))
        results.append(res)
    return sorted(results, key=lambda r: -r["n_pairs"])


def velocity_map(pairs: list[Product]):
    """Per-pixel inversion for one geometry. Returns (velocity mm/yr, prof) or None."""
    pairs = sorted(pairs, key=lambda p: p.ref)
    maps, prof = [], None
    for p in pairs:
        d, coh, pr, _ = displacement.los_cm(p)
        if prof is None:
            prof, shape = pr, d.shape
        if d.shape != shape:
            continue
        maps.append((p, d - np.nanmedian(d)))
    if len(maps) < 2:
        return None
    use = [m[0] for m in maps]
    dates, A = _design(use)
    stack = (np.stack([m[1] for m in maps]).reshape(len(maps), -1) * 10).astype("float32")   # mm
    valid = np.isfinite(stack).all(axis=0)
    t = np.array([(_date(d) - _date(dates[0])).days / 365.25 for d in dates])
    vel = np.full(stack.shape[1], np.nan, dtype="float32")
    if valid.any():
        P = np.linalg.pinv(A).astype("float32")
        tc = (t - t.mean()).astype("float32")
        idx = np.flatnonzero(valid)
        for k in range(0, idx.size, 500_000):                                     # chunks: bounded memory
            sl = idx[k:k + 500_000]
            x = P @ stack[:, sl]                                                  # cumulative at dates 1..n
            cum = np.vstack([np.zeros((1, x.shape[1]), "float32"), x])
            vel[sl] = (tc @ (cum - cum.mean(axis=0))) / (tc @ tc)
    return vel.reshape(prof["height"], prof["width"]), prof
