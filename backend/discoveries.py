"""Automatic discovery: scan every downloaded geometry and list the zones that move.  DISABLED BY DEFAULT.

Why it is off (NISAR_DISCOVERIES_ENABLED=1 turns it back on): the first zones on real data were -183 cm over 600 km2,
+98 cm, -179 cm in a single 12-day pair, i.e. 8 to 15 fringes (11.92 cm each). That is not physical for Morocco in
this window; it looks like unwrapping offsets between connected components, atmosphere, or a reference error.
So every zone is an "unvalidated candidate": confidence low, alert at most yellow, never red or orange, and it carries
the checks that expose such artefacts (fringes, connected components, second geometry).

Per track/frame: velocity map if the stack is long enough, else the latest pair's displacement. A zone = connected
pixels beyond 3x the noise floor. Ranked by |motion| x area.

NISAR_DISCOVERIES_MODE=consistent (the safe mode, also off by default): per geometry and CRID, only INDEPENDENT pairs
(no shared time interval) that pass the quality filter, with the default corrections (masked ionosphere). A zone is kept
only if it is above 3 sigma after smoothing in at least 3 of them, with the same sign in each, and no single pair holds
more than half of its total motion. Still an "unvalidated candidate", confidence low, alert yellow at most."""
from __future__ import annotations

import json
import warnings
from collections import defaultdict

import numpy as np
from scipy import ndimage

import catalog
import config
import evidence
import quality
import raster
from config import CACHE_DIR, FRINGE_CM
from recipes import corrections, displacement, timeseries
from uncertainty import robust_sigma

OUT = CACHE_DIR / "discoveries.json"
SCHEMA = 2
LABEL = "unvalidated candidate"
ONE_COMPONENT_MIN = 0.95      # share of the zone's pixels in one connected component to say "one component"
SECOND_GEOMETRY_SIGMA = 3.0   # another geometry "shows" the zone if its smoothed map is beyond this many sigma there


CONSISTENT = "consistent"
MIN_INDEPENDENT_PAIRS = 3     # a consistent zone is seen in at least this many independent pairs
Z_MIN = 3.0                   # ... above this many sigma after smoothing in each of them
MAX_SINGLE_PAIR_SHARE = 0.5   # ... and no single pair holds more than this share of its total motion
Z_OPPOSITE = 2.0              # ... and no pair shows the opposite sign beyond this many sigma


def mode() -> str:
    """'consistent' (safe mode), 'single' (the old mode, NISAR_DISCOVERIES_ENABLED=1) or 'off'."""
    if config.DISCOVERIES_MODE == CONSISTENT:
        return CONSISTENT
    return "single" if config.DISCOVERIES_ENABLED else "off"


def is_enabled() -> bool:
    return mode() != "off"


def disabled() -> dict:
    """What the API returns while discoveries are off: an empty list and the reason."""
    return {"enabled": False, "mode": "off", "label": LABEL, "schema": SCHEMA, "zones": [], "n_geometries": 0,
            "reason": config.DISCOVERIES_OFF_REASON}


def _smooth(arr, size=7):
    """NaN-aware moving average (~0.5 km at 80 m): lowers pixel noise before detection."""
    ok = np.isfinite(arr)
    num = ndimage.uniform_filter(np.where(ok, arr, 0).astype("float64"), size)
    den = ndimage.uniform_filter(ok.astype("float64"), size)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = num / den
    out[den < 0.3] = np.nan
    return out.astype("float32")


def _zones(arr, prof, unit, source, geom, direction, cc=None, coh=None, min_pixels=12, top=15):
    """Returns (zones, info). info = the smoothed map and its noise, kept to ask the other geometries about each zone."""
    raw_finite = np.isfinite(arr)
    arr = _smooth(arr)
    sigma = robust_sigma(arr)
    if not np.isfinite(sigma) or sigma == 0:
        return [], None
    med = float(np.nanmedian(arr))
    info = {"arr": arr, "prof": prof, "sigma": float(sigma), "med": med, "geom": geom, "direction": direction, "unit": unit}
    hot = np.isfinite(arr) & (np.abs(arr - med) > 3 * sigma)
    hot = ndimage.binary_opening(hot, iterations=1)
    lab, n = ndimage.label(hot)
    if n == 0:
        return [], info
    px_km2 = (raster.pixel_size_m(prof) / 1000) ** 2
    idx = np.arange(1, n + 1)
    sizes = ndimage.sum(hot, lab, idx)
    means = ndimage.mean(np.nan_to_num(arr - med), lab, idx)
    peaks = ndimage.maximum(np.abs(np.nan_to_num(arr - med)), lab, idx)
    centers = ndimage.center_of_mass(hot, lab, idx)
    slices = ndimage.find_objects(lab)
    main_cc = None
    if cc is not None and cc.shape == arr.shape:                 # the frame's largest connected component
        counts = np.bincount(cc[raw_finite & (cc > 0)].astype(np.int64))
        main_cc = int(counts.argmax()) if counts.size and counts.max() > 0 else None
    zones = []
    for i, size, mean, peak, (r, c) in zip(idx, sizes, means, peaks, centers):
        if size < min_pixels:
            continue
        lon, lat = raster.to_lonlat(prof, r, c)
        z = {"lat": round(lat, 5), "lon": round(lon, 5), "area_km2": round(float(size * px_km2), 2),
             "mean": round(float(mean), 2), "peak": round(float(peak), 2), "unit": unit,
             "snr": round(float(abs(mean) / sigma), 1), "source": source,
             "track": geom[0], "frame": geom[1], "direction": direction,
             "score": float(abs(mean) / sigma * np.sqrt(size))}
        # (b) is it physical? fringes = |cm| / 11.92 inside ONE pair; and does it sit in one unwrapped component?
        z["fringes"] = round(abs(float(mean)) / FRINGE_CM, 1) if unit == "cm" else None
        z["peak_fringes"] = round(float(peak) / FRINGE_CM, 1) if unit == "cm" else None
        z["coherence_mean"] = None
        if coh is not None and coh.shape == arr.shape:        # unwrapping errors live where the coherence is low
            cz = coh[slices[i - 1]][lab[slices[i - 1]] == i]
            cz = cz[np.isfinite(cz)]
            z["coherence_mean"] = round(float(cz.mean()), 2) if cz.size else None
        z["n_components"] = z["main_component_share"] = z["in_one_component"] = z["in_frame_main_component"] = None
        if cc is not None and cc.shape == arr.shape:
            labels = cc[slices[i - 1]][lab[slices[i - 1]] == i]
            labels = labels[labels > 0]
            if labels.size:
                u, k = np.unique(labels, return_counts=True)
                share = k / labels.size
                z["n_components"] = int((share >= 0.05).sum())
                z["main_component_share"] = round(float(share.max()), 2)
                z["in_one_component"] = bool(share.max() >= ONE_COMPONENT_MIN)
                z["in_frame_main_component"] = None if main_cc is None else bool(share[u == main_cc].sum() >= ONE_COMPONENT_MIN
                                                                                    if (u == main_cc).any() else False)
        zones.append(z)
    return sorted(zones, key=lambda z: -z["score"])[:top], info


def _other_geometries(z, infos):
    """Do the OTHER geometries that cover the zone also show it? (a real movement is seen from several look directions)"""
    shown, covering = [], 0
    for inf in infos:
        if tuple(inf["geom"][:2]) == (z["track"], z["frame"]):
            continue                              # the zone's own geometry is not a second opinion
        w = raster.window(inf["arr"], inf["prof"], z["lat"], z["lon"], 1000)
        if w.size == 0 or not np.isfinite(w).any():
            continue
        covering += 1
        v = float(np.nanmedian(w)) - inf["med"]
        if abs(v) > SECOND_GEOMETRY_SIGMA * inf["sigma"]:
            shown.append({"track": inf["geom"][0], "frame": inf["geom"][1], "direction": inf["direction"],
                          "value": round(v, 2), "unit": inf["unit"]})
    z["n_other_geometries_covering"] = covering
    z["other_geometries_showing"] = shown
    z["second_geometry_shows"] = None if covering == 0 else bool(shown)


def _flags(z):
    f = []
    if z["fringes"] is not None and z["fringes"] >= 1:
        f.append(f"{z['fringes']} fringes in a single pair: not physical for this window")
    if z["in_one_component"] is False:
        f.append("spans several connected components")
    if z["in_frame_main_component"] is False:
        f.append("not in the frame's main connected component (a whole-fringe offset to the reference is possible)")
    if z["second_geometry_shows"] is None:
        f.append("no second geometry covers it")
    elif z["second_geometry_shows"] is False:
        f.append("the other geometries do not show it")
    return f


def independent(pairs) -> list:
    """Greedy set of pairs that share no time interval (sorted by end date): their noise is independent."""
    out, last = [], ""
    for p in sorted(pairs, key=lambda p: (p.sec, p.span_days)):
        if p.ref >= last:
            out.append(p)
            last = p.sec
    return out


def consistent_zone(values_sigma: list, z_min: float = Z_MIN, min_pairs: int = MIN_INDEPENDENT_PAIRS,
                    max_share: float = MAX_SINGLE_PAIR_SHARE) -> dict:
    """Pure rule on one zone: per independent pair (mean value in the zone, noise sigma of that pair's map).
    Kept if >= min_pairs pairs are beyond z_min sigma, all of those with the same sign (and no other pair beyond
    Z_OPPOSITE sigma with the opposite sign), and no pair holds more than max_share of the total |motion|."""
    z = [v / s if s and np.isfinite(v) and np.isfinite(s) else 0.0 for v, s in values_sigma]
    det = [i for i, zi in enumerate(z) if abs(zi) > z_min]
    signs = {float(np.sign(values_sigma[i][0])) for i in det}
    if len(signs) == 1:                          # the same sign in each pair: no other pair clearly opposite
        sg = next(iter(signs))
        signs |= {float(np.sign(zi)) for zi in z if abs(zi) > Z_OPPOSITE and np.sign(zi) != sg}
    mags = [abs(v) for v, _ in values_sigma if np.isfinite(v)]
    share = max(mags) / sum(mags) if mags and sum(mags) > 0 else 1.0
    reasons = []
    if len(det) < min_pairs:
        reasons.append(f"seen in {len(det)} independent pair(s), needs {min_pairs}")
    if len(signs) > 1:
        reasons.append("the sign changes between pairs")
    if share > max_share:
        reasons.append(f"one pair holds {share:.0%} of the motion")
    return {"kept": not reasons, "n_pairs_detected": len(det), "pairs_detected_index": det, "same_sign": len(signs) <= 1,
            "max_single_pair_share": round(float(share), 2), "z": [round(float(x), 1) for x in z], "why_not": reasons}


def _consistent_maps(ps):
    """[(pair, smoothed map minus its median, noise sigma)] of the independent pairs sharing one grid, and the grid."""
    maps, prof, shape = [], None, None
    for p in independent(ps):
        d, _, pr, _ = displacement.los_cm(p)                # default corrections: ionosphere with its uncertainty mask
        if shape is None:
            prof, shape = pr, d.shape
        if d.shape != shape:
            continue
        a = _smooth(d)
        sig = robust_sigma(a)
        if np.isfinite(sig) and sig > 0:
            maps.append((p, a - float(np.nanmedian(a)), sig))
    return maps, prof


def _consistent_zone_dict(m, maps, rule, prof, mean_map, geom, direction):
    r, c = ndimage.center_of_mass(m)
    lon, lat = raster.to_lonlat(prof, r, c)
    vs = [(float(np.nanmean(a[m])), s) for _, a, s in maps]
    det = rule["pairs_detected_index"]
    mean = float(np.mean([vs[k][0] for k in det]))
    sig = float(np.median([maps[k][2] for k in det]))
    return {"lat": round(lat, 5), "lon": round(lon, 5), "area_km2": round(float(m.sum() * (raster.pixel_size_m(prof) / 1000) ** 2), 2),
            "mean": round(mean, 2), "peak": round(float(np.nanmax(np.abs(mean_map[m]))), 2), "unit": "cm",
            "snr": round(abs(mean) / sig, 1), "source": f"{len(det)} of {len(maps)} independent pairs",
            "track": geom[0], "frame": geom[1], "direction": direction,
            "score": float(abs(mean) / sig * np.sqrt(m.sum()) * len(det)),
            "mode": CONSISTENT, "n_independent_pairs": len(maps), "n_pairs_detected": len(det),
            "pairs_detected": [maps[k][0].id for k in det], "per_pair_mean_cm": [round(v, 2) for v, _ in vs],
            "same_sign": rule["same_sign"], "max_single_pair_share": rule["max_single_pair_share"],
            "fringes": round(abs(mean) / FRINGE_CM, 1), "peak_fringes": None, "coherence_mean": None,
            "n_components": None, "main_component_share": None, "in_one_component": None, "in_frame_main_component": None}


def _consistent_geometry(geom, ps, min_pixels=12, top=15):
    """(zones, info for the other-geometry check, number of usable independent pairs) for one geometry and CRID."""
    maps, prof = _consistent_maps(ps)
    if len(maps) < MIN_INDEPENDENT_PAIRS:
        return [], None, len(maps)
    pos = sum(ndimage.binary_opening(np.nan_to_num(a / s) > Z_MIN).astype(int) for _, a, s in maps)
    neg = sum(ndimage.binary_opening(np.nan_to_num(a / s) < -Z_MIN).astype(int) for _, a, s in maps)
    cand = ((pos >= MIN_INDEPENDENT_PAIRS) & (neg == 0)) | ((neg >= MIN_INDEPENDENT_PAIRS) & (pos == 0))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)          # all-NaN pixels stay NaN
        mean_map = np.nanmean(np.stack([a for _, a, _ in maps]), axis=0)
    info = {"arr": mean_map, "prof": prof, "sigma": float(robust_sigma(mean_map)), "med": 0.0, "geom": geom,
            "direction": ps[0].direction, "unit": "cm"}
    lab, n = ndimage.label(cand)
    zones = []
    for i in range(1, n + 1):
        m = lab == i
        if m.sum() < min_pixels:
            continue
        rule = consistent_zone([(float(np.nanmean(a[m])), s) for _, a, s in maps])
        if rule["kept"]:
            zones.append(_consistent_zone_dict(m, maps, rule, prof, mean_map, geom, ps[0].direction))
    return sorted(zones, key=lambda z: -z["score"])[:top], info, len(maps)


def scan_consistent(with_exposure: bool = True, top: int = 20) -> dict:
    groups = defaultdict(list)
    good, rejected = quality.split([p for p in catalog.load() if p.level == "GUNW"])
    for p in good:                              # pairs rejected by the quality filter are never used
        groups[p.series_key].append(p)
    zones, infos, n_ok = [], [], 0
    for geom, ps in groups.items():
        z, info, n_ind = _consistent_geometry(geom, ps)
        n_ok += n_ind >= MIN_INDEPENDENT_PAIRS
        zones += z
        if info:
            infos.append(info)
    zones = _finish(sorted(zones, key=lambda z: -z["score"])[:top], infos, with_exposure)
    out = {"enabled": True, "mode": CONSISTENT, "label": LABEL, "schema": SCHEMA, "zones": zones,
           "n_geometries": len(groups), "n_geometries_with_enough_independent_pairs": n_ok, "rejected_pairs": rejected,
           "rules": {"min_independent_pairs": MIN_INDEPENDENT_PAIRS, "sigma_after_smoothing": Z_MIN, "same_sign": True,
                     "opposite_sign_max_sigma": Z_OPPOSITE,
                     "max_single_pair_share": MAX_SINGLE_PAIR_SHARE, "corrections": list(corrections.active()),
                     "quality_filter": True},
           "note": "Consistent mode: a zone is kept only if it is above 3 sigma after smoothing in at least 3 independent "
                   "pairs of one geometry, with the same sign, and no single pair holds more than half of its motion. "
                   "Every zone is still an unvalidated candidate (confidence low, never an alert above yellow)."}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def _finish(zones, infos, with_exposure):
    for rank, z in enumerate(zones, 1):
        z["rank"] = rank
        _other_geometries(z, infos)
        z["label"] = LABEL
        z["flags"] = _flags(z)
        z["confidence"] = "low"                 # never high: nothing validates these zones
        z["alert_level"] = "yellow"             # never orange or red
        if with_exposure:
            e = evidence.exposure(z["lat"], z["lon"], 1500)
            z["exposure"] = e.get("counts") if e["status"] != "unavailable" else None
            z["exposed"] = e.get("exposed")
        z["id"] = f"zone-{rank}"
    return zones


def scan(with_exposure: bool = True, top: int = 20, force: bool = False) -> dict:
    if not (is_enabled() or force):
        return disabled()
    if mode() == CONSISTENT:
        return scan_consistent(with_exposure, top)
    groups = defaultdict(list)
    good, rejected = quality.split([p for p in catalog.load() if p.level == "GUNW"])
    for p in good:                              # pairs rejected by the quality filter are never scanned
        groups[p.series_key].append(p)          # geometry AND CRID: never mix product versions
    zones, infos = [], []
    for geom, ps in groups.items():
        twelve = [p for p in ps if p.span_days in (12, 24)]
        res = timeseries.velocity_map(twelve) if len(twelve) >= 3 else None
        if res is not None:
            vel, prof = res
            z, info = _zones(vel, prof, "mm/yr", f"velocity from {len(twelve)} pairs", geom, ps[0].direction)
        else:
            latest = max(ps, key=lambda p: p.sec)
            d, coh, prof, _ = displacement.los_cm(latest)
            z, info = _zones(d, prof, "cm", f"pair {latest.ref[:8]}→{latest.sec[:8]}", geom, latest.direction,
                             cc=displacement._components_raster(latest), coh=coh)
        zones += z
        if info:
            infos.append(info)
    zones = _finish(sorted(zones, key=lambda z: -z["score"])[:top], infos, with_exposure)
    out = {"enabled": True, "mode": "single", "label": LABEL, "schema": SCHEMA, "zones": zones, "n_geometries": len(groups),
           "rejected_pairs": rejected, "note":
           "Every zone is an unvalidated candidate (confidence low, never an alert above yellow). Velocity maps need a record "
           "of at least 12 months; with less, the latest single pair is used, in cm, and a zone of one fringe (11.92 cm) or "
           "more in one pair is not physical."}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def cached() -> dict:
    if not is_enabled():
        return disabled()                       # never serve an old cache while the feature is off
    if OUT.exists():
        c = json.loads(OUT.read_text(encoding="utf-8"))
        if c.get("schema") == SCHEMA and c.get("mode", "single") == mode():
            return c
    return scan(with_exposure=False)
