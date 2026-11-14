"""Automatic discovery: scan every downloaded geometry and list the zones that move.  DISABLED BY DEFAULT.

Why it is off (NISAR_DISCOVERIES_ENABLED=1 turns it back on): the first zones on real data were -183 cm over 600 km2,
+98 cm, -179 cm in a single 12-day pair, i.e. 8 to 15 fringes (11.92 cm each). That is not physical for Morocco in
this window; it looks like unwrapping offsets between connected components, atmosphere, or a reference error.
So every zone is an "unvalidated candidate": confidence low, alert at most yellow, never red or orange, and it carries
the checks that expose such artefacts (fringes, connected components, second geometry).

Per track/frame: velocity map if the stack is long enough, else the latest pair's displacement. A zone = connected
pixels beyond 3x the noise floor. Ranked by |motion| x area."""
from __future__ import annotations

import json
from collections import defaultdict

import numpy as np
from scipy import ndimage

import catalog
import config
import evidence
import quality
import raster
from config import CACHE_DIR, FRINGE_CM
from recipes import displacement, timeseries
from uncertainty import robust_sigma

OUT = CACHE_DIR / "discoveries.json"
SCHEMA = 2
LABEL = "unvalidated candidate"
ONE_COMPONENT_MIN = 0.95      # share of the zone's pixels in one connected component to say "one component"
SECOND_GEOMETRY_SIGMA = 3.0   # another geometry "shows" the zone if its smoothed map is beyond this many sigma there


def disabled() -> dict:
    """What the API returns while discoveries are off: an empty list and the reason."""
    return {"enabled": False, "label": LABEL, "schema": SCHEMA, "zones": [], "n_geometries": 0,
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


def scan(with_exposure: bool = True, top: int = 20, force: bool = False) -> dict:
    if not (config.DISCOVERIES_ENABLED or force):
        return disabled()
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
    zones = sorted(zones, key=lambda z: -z["score"])[:top]
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
    out = {"enabled": True, "label": LABEL, "schema": SCHEMA, "zones": zones, "n_geometries": len(groups),
           "rejected_pairs": rejected, "note":
           "Every zone is an unvalidated candidate (confidence low, never an alert above yellow). Velocity maps need a record "
           "of at least 12 months; with less, the latest single pair is used, in cm, and a zone of one fringe (11.92 cm) or "
           "more in one pair is not physical."}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def cached() -> dict:
    if not config.DISCOVERIES_ENABLED:
        return disabled()                       # never serve an old cache while the feature is off
    if OUT.exists():
        c = json.loads(OUT.read_text(encoding="utf-8"))
        if c.get("schema") == SCHEMA:
            return c
    return scan(with_exposure=False)
