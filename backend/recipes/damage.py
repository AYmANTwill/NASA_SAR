"""Recipe 'surface_change': coherence loss between a "before" pair and the pair that contains the event.

(Formerly the "damage proxy"; same maths, honest name: a drop in L-band coherence means the surface
scatterers changed (water, mud, rock fall, earthworks, construction, vegetation, damage). It does not say
which, and it is not a measure of damage, flood depth or flood duration.)

coherence(before pair) - coherence(pair across the event), on the same track/frame/CRID and with the
same pair length (coherence decays with the time baseline, so a 24-day pair cannot be compared with a
12-day pair). The result is independent of the LOS sign.

Area: a true 5 km RADIUS circle around the point (clipped at the array edge, and the clipped part counts as
"not covered"), not a 10x10 km square. Every geometry is also measured against two references:
  - baseline: the same loss between the before pair and the pair just before it (no event in it);
  - frame background: the mean loss over the whole frame in the event pair.
A geometry is usable only if the circle is covered by valid data, a baseline pair exists and the area was
coherent before the event. A geometry that is not usable returns "not usable: <reason>" and no change number.

Event mode: the event is an exact instant (earthquake) or a whole UTC day (storm): see catalog.relation.
A pair with an acquisition inside the event day is ambiguous and never used. No event: 'latest' mode
compares the newest pair with the one before it, and says so."""
from __future__ import annotations

import numpy as np

import raster
from catalog import Product, after, ambiguous, before, straddling
from config import POINT_RADIUS_M

CHANGE_THRESHOLD = 0.3          # coherence loss above this counts as a changed pixel
COHERENT_BEFORE_MIN = 0.4       # only pixels that were coherent before the event can show a loss
SPAN_TOLERANCE_DAYS = 1
RADIUS_M = 5_000                # radius of the area around the point
COVERAGE_MIN = 0.9              # >= 90 % of the circle must hold valid data in both pairs
COHERENT_SHARE_MIN = 0.5        # >= 50 % of the valid pixels must have been coherent before the event
BASELINE_UNRELIABLE_DROP = 0.1  # before pair this far below the median of the geometry's other pairs
MIN_OTHER_PAIRS = 3             # other pairs needed to judge the before pair
# Excess = circle mean loss minus frame mean loss. Its no-event spread was measured on 044/17 (adjacent 12-day pairs,
# Jun-Sep 2026, ~24 million circles, sd 0.038): 0.11 is exceeded by 1 % of no-event circles, 0.15 by 0.25 %.
EXCESS_MARGIN = 0.11            # at or above: borderline (just above the no-event level)
EXCESS_STRONG = 0.15            # at or above: local excess
NULL_FALSE_ALARM = 0.01         # share of no-event circles above EXCESS_MARGIN
NULL_FALSE_ALARM_PCT = 1        # the same, as the whole percent shown in the sentences
NULL_LIMITS = ["one viewing geometry (044/17)", "one season (June to September 2026)",
               "circles placed at random anywhere in the frame"]

_NO_NUMBERS = ("loss_at_point", "loss_mean_5km", "changed_km2_5km", "baseline_pair", "baseline_loss_mean",
               "baseline_changed_km2", "frame_loss_mean", "frame_frac_changed", "excess_over_frame", "local_excess",
               "baseline_unreliable", "pair_coherence_mean", "other_pairs_coherence_median", "n_other_pairs",
               "excess_level")


def _candidates(products, event, precision):
    """[(before_pair, window_pair)] on the same geometry, CRID and pair length."""
    out = []
    if event:
        co, pre = straddling(products, event, precision), before(products, event, precision)
    else:                                                    # latest mode: newest pair vs the one just before
        ps = sorted(products, key=lambda p: p.sec)
        co, pre = [], ps
        for key in {p.series_key for p in ps}:
            chain = [p for p in ps if p.series_key == key]
            if chain:
                co.append(chain[-1])
    for c in co:
        same = [p for p in pre if p.series_key == c.series_key and "coherence" in p.files
                and abs(p.span_days - c.span_days) <= SPAN_TOLERANCE_DAYS and p.sec <= c.ref
                and p is not c]
        if same and "coherence" in c.files:
            out.append((max(same, key=lambda p: p.sec), c))        # the most recent comparable earlier pair
    return out


def _baseline_pair(products, b):
    """The pair just before the 'before' pair: same geometry, CRID and length, ending no later than b starts."""
    prev = [p for p in products if p.series_key == b.series_key and "coherence" in p.files and p is not b
            and abs(p.span_days - b.span_days) <= SPAN_TOLERANCE_DAYS and p.sec <= b.ref]
    return max(prev, key=lambda p: p.sec) if prev else None


def _other_pairs(products, b, c):
    return [p for p in products if p.series_key == b.series_key and "coherence" in p.files
            and p is not b and p is not c and abs(p.span_days - b.span_days) <= SPAN_TOLERANCE_DAYS]


def _circle_mean_coherence(arr, circ):
    """Mean coherence in the circle, or None if less than half of the circle holds data."""
    v = arr[circ & np.isfinite(arr)]
    return None if v.size < 0.5 * circ.sum() else float(v.mean())


def _blank(b, c):
    g = {"direction": c.direction, "track": c.track, "frame": c.frame, "crid": c.crid,
         "pre_pair": b.id, "co_pair": c.id, "coverage_5km": None, "coherent_before_fraction_5km": None,
         "usable": False, "reason": None}
    g.update({k: None for k in _NO_NUMBERS})
    return g


def _geometry(products, b, c, lat, lon):
    """(geometry facts, private extras) for one before/event pair, or None if the grids differ."""
    cb, _, circ, prof = raster.read_around(b.files["coherence"], lat, lon, RADIUS_M)
    ca, _, _, prof_a = raster.read_around(c.files["coherence"], lat, lon, RADIUS_M)
    if (prof["width"], prof["height"]) != (prof_a["width"], prof_a["height"]):
        return None
    px_km2 = (raster.pixel_size_m(prof) / 1000) ** 2
    n_circle = int(circ.sum())
    valid = circ & np.isfinite(cb) & np.isfinite(ca)
    coverage = float(valid.sum() / n_circle)
    coh_share = float((cb[valid] >= COHERENT_BEFORE_MIN).mean()) if valid.any() else 0.0
    base = _baseline_pair(products, b)
    bl_mean = bl_km2 = None
    if base is not None:                                      # baseline: the before pair against the pair just before it
        cq, _, _, prof_q = raster.read_around(base.files["coherence"], lat, lon, RADIUS_M)
        if (prof_q["width"], prof_q["height"]) == (prof["width"], prof["height"]):
            bl = np.where(cq >= COHERENT_BEFORE_MIN, cq - cb, np.nan)[circ]
            bl = bl[np.isfinite(bl)]
            if bl.size and bl.size >= COHERENT_SHARE_MIN * valid.sum():     # same floor as for the event pair: half of the valid pixels
                bl_mean, bl_km2 = round(float(bl.mean()), 3), round(float((bl > CHANGE_THRESHOLD).sum() * px_km2), 2)
    reasons = []
    if coverage < COVERAGE_MIN:
        reasons.append("the 5 km circle is not covered by valid data")
    if base is None:
        reasons.append("no earlier pair of the same length to use as a baseline")
    elif bl_mean is None:
        reasons.append("the baseline pair cannot be measured (less than half of the circle was coherent in it)")
    if coh_share < COHERENT_SHARE_MIN:
        reasons.append("less than half of the valid pixels were coherent before the event")
    g = _blank(b, c)
    g.update(coverage_5km=round(coverage, 2), coherent_before_fraction_5km=round(coh_share, 2))
    if reasons:
        g["reason"] = "not usable: " + "; ".join(reasons)
        return g, None
    g["usable"] = True
    g.update(baseline_pair=base.id, baseline_loss_mean=bl_mean, baseline_changed_km2=bl_km2)

    # --- the event pair, full frame
    cbf, prof = raster.read(b.files["coherence"])
    caf, _ = raster.read(c.files["coherence"])
    loss = (cbf - caf).astype("float32")
    loss[cbf < COHERENT_BEFORE_MIN] = np.nan                 # only where it was coherent before
    w = raster.window(loss, prof, lat, lon, POINT_RADIUS_M)
    g["loss_at_point"] = None if not np.isfinite(w).any() else round(float(np.nanmedian(w)), 2)
    sub, _, _ = raster.crop_around(loss, prof, lat, lon, RADIUS_M)
    in_circle = sub[circ]
    in_circle = in_circle[np.isfinite(in_circle)]
    g["loss_mean_5km"] = round(float(in_circle.mean()), 3)
    g["changed_km2_5km"] = round(float((in_circle > CHANGE_THRESHOLD).sum() * px_km2), 2)
    frame = loss[np.isfinite(loss)]
    g["frame_loss_mean"] = round(float(frame.mean()), 3)
    g["frame_frac_changed"] = round(float((frame > CHANGE_THRESHOLD).mean()), 4)
    g["excess_over_frame"] = round(g["loss_mean_5km"] - g["frame_loss_mean"], 3)
    g["excess_level"] = ("strong" if g["excess_over_frame"] >= EXCESS_STRONG else
                         "borderline" if g["excess_over_frame"] >= EXCESS_MARGIN else "none")
    g["local_excess"] = g["excess_level"] == "strong"

    # --- is the before pair itself normal for this geometry? (a degraded before pair hides a loss)
    own = _circle_mean_coherence(cb, circ)
    others = []
    for p in _other_pairs(products, b, c):
        arr, _, _, pr = raster.read_around(p.files["coherence"], lat, lon, RADIUS_M)
        m = _circle_mean_coherence(arr, circ)
        if m is not None and (pr["width"], pr["height"]) == (prof["width"], prof["height"]):
            others.append(m)
    g["n_other_pairs"] = len(others)
    if own is not None:
        g["pair_coherence_mean"] = round(own, 2)
    if own is not None and len(others) >= MIN_OTHER_PAIRS:
        med = float(np.median(others))
        g["other_pairs_coherence_median"] = round(med, 2)
        g["baseline_unreliable"] = bool(own < med - BASELINE_UNRELIABLE_DROP)
    else:
        g["baseline_unreliable"] = None                       # not enough other pairs to say
    return g, {"loss": loss, "prof": prof, "b": b, "c": c}


def analyze(products: list[Product], lat: float, lon: float, event: str | None = None,
            precision: str = "exact") -> dict:
    cands = _candidates(products, event, precision)
    amb = [p.id for p in ambiguous(products, event, precision)] if event else []
    if not cands:
        return {"error": "needs an earlier pair and a pair of the same length on the same track, frame and "
                         "CRID" + (", the second one spanning the event" if event else ""),
                "have_event_pairs": [p.id for p in straddling(products, event, precision)] if event else [],
                "have_pre_pairs": [p.id for p in before(products, event, precision)] if event else [],
                "have_post_pairs": [p.id for p in after(products, event, precision)] if event else [],
                "ambiguous_pairs": amb}
    results = []
    for b, c in cands:
        r = _geometry(products, b, c, lat, lon)
        if r is not None:
            results.append(r)
    if not results:
        return {"error": "the before and event pairs do not share the same grid", "ambiguous_pairs": amb}
    geoms = [g for g, _ in results]
    usable = [(g, ex) for g, ex in results if g["usable"]]
    if not usable:
        best = max(geoms, key=lambda g: g["coverage_5km"])
        return {"error": best["reason"], "n_geometries": len(geoms), "n_usable_geometries": 0,
                "geometries": geoms, "ambiguous_pairs": amb}
    # main geometry: a reliable baseline first, then the best covered and most coherent one; never the largest loss
    main, ex = max(usable, key=lambda t: (t[0]["baseline_unreliable"] is not True, t[0]["coverage_5km"],
                                          t[0]["coherent_before_fraction_5km"]))
    b, c = ex["b"], ex["c"]
    sides = {g["excess_level"] != "none" for g, _ in usable}      # does the geometry reach at least the borderline band?
    layer = raster.render_png(np.where(ex["loss"] > 0.1, ex["loss"], np.nan), ex["prof"], f"sc_{c.id}",
                              "inferno", 0.1, 0.8)
    layer["title"] = f"Surface change (coherence loss), {c.ref[:8]}→{c.sec[:8]}"
    out = {
        "mode": "event" if event else "latest",
        "event_day": event[:8] if event else None, "event_precision": precision if event else None,
        "pre_pair": b.id, "co_pair": c.id, "direction": c.direction, "track": c.track, "frame": c.frame,
        "crid": c.crid, "maturity": c.maturity,
        "pre_date_before": b.ref[:8], "pre_date_after": b.sec[:8],
        "date_before": c.ref[:8], "date_after": c.sec[:8], "window_days": c.span_days,
        "threshold": CHANGE_THRESHOLD, "radius_m": RADIUS_M, "excess_margin": EXCESS_MARGIN, "excess_strong": EXCESS_STRONG,
        "null_false_alarm": NULL_FALSE_ALARM, "null_false_alarm_pct": NULL_FALSE_ALARM_PCT,
        "null_limits": NULL_LIMITS,
        "n_geometries": len(geoms), "n_usable_geometries": len(usable), "geometries": geoms,
        "geometries_agree": None if len(usable) < 2 else len(sides) == 1,
        "changed_km2_range": [min(g["changed_km2_5km"] for g, _ in usable), max(g["changed_km2_5km"] for g, _ in usable)],
        "ambiguous_pairs": amb, "layer": layer,
    }
    for k in ("coverage_5km", "coherent_before_fraction_5km") + _NO_NUMBERS:
        out[k] = main[k]
    return out
