"""Recipe 'slow_motion': displacement time series from a stack of GUNW pairs (small-baseline inversion).

Point mode: one series per viewing geometry AND CRID (never mixed), cumulative LOS per date, a rate (mm/yr)
only when the record is at least MIN_RATE_DAYS (12 months) long. The pair graph must be connected: dates
that no valid pair links to the main chain are left out (never bridged silently) and reported.
Map mode: velocity map of a stack (used by discoveries), same two rules."""
from __future__ import annotations

from collections import defaultdict
from datetime import date

import numpy as np

import raster
from catalog import Product
from config import DATA_GAPS, MIN_RATE_DAYS
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


def _components(pairs: list[Product]) -> list[set]:
    """Connected components of the graph whose nodes are acquisition dates and whose edges are the pairs.
    Largest first (ties: earliest date)."""
    parent: dict = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for p in pairs:
        parent[find(p.ref[:8])] = find(p.sec[:8])
    groups = defaultdict(set)
    for d in list(parent):
        groups[find(d)].add(d)
    return sorted(groups.values(), key=lambda g: (-len(g), min(g)))


def _fit(dates: list[str], series: np.ndarray, min_days: int | None = None):
    """Rate (mm/yr) and acceleration, only for a record of at least `min_days` (default 12 months)."""
    min_days = MIN_RATE_DAYS if min_days is None else min_days
    span = (_date(dates[-1]) - _date(dates[0])).days
    out = {"velocity_mm_yr": None, "velocity_sigma_mm_yr": None, "min_rate_days": int(min_days)}
    if span < min_days:
        return out
    t = np.array([(_date(d) - _date(dates[0])).days / 365.25 for d in dates])
    ok = np.isfinite(series)
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
    """One series per (geometry, CRID). Cumulative LOS in mm relative to the first date of the main chain."""
    groups = defaultdict(list)
    for p in products:
        groups[p.series_key].append(p)
    results = []
    for key, pairs in groups.items():
        pairs = sorted(pairs, key=lambda p: p.ref)
        obs, sig, facts = [], [], []
        for p in pairs:
            f = displacement.analyze(p, lat, lon, make_layer=False)
            facts.append(f)
            obs.append(np.nan if f["los_cm"] is None else f["los_cm"] * 10)       # mm
            sig.append(np.nan if f["noise_cm"] is None else f["noise_cm"] * 10)
        ok = np.isfinite(obs)
        if not ok.any():
            continue
        valid = [p for p, g in zip(pairs, ok) if g]
        comps = _components(valid)                       # a date linked by no valid pair is not on any chain
        main = comps[0]
        use = [(p, o, s) for p, o, s, g in zip(pairs, obs, sig, ok) if g and p.ref[:8] in main]
        upairs = [u[0] for u in use]
        ufacts = [f for p, f, g in zip(pairs, facts, ok) if g and p.ref[:8] in main]
        uobs, usig = np.array([u[1] for u in use]), np.array([u[2] for u in use])
        dates, A = _design(upairs)
        if A.shape[1] == 0:
            continue
        fin = np.isfinite(usig) & (usig > 0)
        w = 1 / np.where(fin, usig, np.median(usig[fin]) if fin.any() else 1.0)
        x, *_ = np.linalg.lstsq(A * w[:, None], uobs * w, rcond=None)
        cum = np.concatenate([[0.0], x])
        by_date = dict(zip(dates, cum))
        all_dates = sorted({p.ref[:8] for p in pairs} | {p.sec[:8] for p in pairs})
        dropped = [d for d in all_dates if d not in by_date]
        noise = float(np.median(usig[np.isfinite(usig)])) if np.isfinite(usig).any() else None
        res = {"track": key[0], "frame": key[1], "crid": key[2], "direction": pairs[0].direction,
               "maturity": pairs[0].maturity,
               "n_pairs": len(upairs), "n_dates": len(dates), "n_components": len(comps),
               "chain_connected": len(comps) == 1 and not dropped, "unmeasured_dates": dropped,
               "n_bridge_pairs": sum(1 for p in upairs if p.span_days > 15),     # skips an acquisition (data gap)
               "noise_mm": None if noise is None else round(noise, 1),
               "series": [{"date": d, "los_mm": round(float(by_date[d]), 1) if d in by_date else None}
                          for d in all_dates],
               "total_los_mm": round(float(cum[-1]), 1),
               "first_date": dates[0], "last_date": dates[-1],
               "span_days": (_date(dates[-1]) - _date(dates[0])).days}
        res.update(_fit(dates, cum))
        n_iono = sum(1 for f in ufacts if f.get("iono_applied"))
        flags = [f.get("reference_same_component") for f in ufacts]
        crossed = [[a, b] for a, b in DATA_GAPS if any(p.ref[:8] < a and p.sec[:8] > b for p in upairs)]
        res.update(
            iono_screen="subtracted" if n_iono == len(ufacts) else "not applied" if n_iono == 0 else "partly subtracted",
            iono_applied_pairs=n_iono, troposphere_corrected=False,
            reference_same_component=False if any(x is False for x in flags) else None if any(x is None for x in flags) else True,
            n_pairs_reference_other_component=sum(1 for x in flags if x is False),
            n_pairs_reference_unknown=sum(1 for x in flags if x is None),
            crosses_data_gap=bool(crossed), data_gaps_crossed=crossed,
            n_pairs_across_gap=sum(1 for p in upairs if any(p.ref[:8] < a and p.sec[:8] > b for a, b in crossed)))
        results.append(res)
    return sorted(results, key=lambda r: -r["n_pairs"])


def velocity_map(pairs: list[Product]):
    """Per-pixel inversion for one geometry and one CRID. Returns (velocity mm/yr, prof) or None.
    None when the pairs do not form a chain of at least MIN_RATE_DAYS (no rate from a short record)."""
    pairs = sorted(pairs, key=lambda p: p.ref)
    if not pairs:
        return None
    chain = _components(pairs)[0]                                  # one connected chain only
    pairs = [p for p in pairs if p.ref[:8] in chain]
    if (_date(max(chain)) - _date(min(chain))).days < MIN_RATE_DAYS:
        return None
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
