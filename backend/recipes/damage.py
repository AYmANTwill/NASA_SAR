"""Recipe 'surface_change': coherence loss between a "before" pair and the pair that contains the event.

(Formerly the "damage proxy"; same maths, honest name: a drop in L-band coherence means the surface
scatterers changed (water, mud, rock fall, earthworks, construction, vegetation, damage). It does not say
which, and it is not a measure of damage, flood depth or flood duration.)

coherence(before pair) - coherence(pair across the event), on the same track/frame/CRID and with the
same pair length (coherence decays with the time baseline, so a 24-day pair cannot be compared with a
12-day pair). The result is independent of the LOS sign.

Event mode: the event is an exact instant (earthquake) or a whole UTC day (storm): see catalog.relation.
A pair with an acquisition inside the event day is ambiguous and never used. No event: 'latest' mode
compares the newest pair with the one before it, and says so."""
from __future__ import annotations

import numpy as np

import raster
from catalog import Product, after, ambiguous, before, straddling
from config import POINT_RADIUS_M

CHANGE_THRESHOLD = 0.3       # coherence loss above this counts as a changed pixel
COHERENT_BEFORE_MIN = 0.4    # only pixels that were coherent before the event can show a loss
SPAN_TOLERANCE_DAYS = 1
USABLE_COHERENT_MIN = 0.5    # a geometry counts only if >= half of the 5 km area was coherent before


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
        cb, prof = raster.read(b.files["coherence"])
        ca, _ = raster.read(c.files["coherence"])
        if ca.shape != cb.shape:
            continue
        loss = (cb - ca).astype("float32")
        loss[cb < COHERENT_BEFORE_MIN] = np.nan                # only where it was coherent before
        w = raster.window(loss, prof, lat, lon, POINT_RADIUS_M)
        big = raster.window(loss, prof, lat, lon, 5_000)
        px_km2 = (raster.pixel_size_m(prof) / 1000) ** 2
        results.append({
            "b": b, "c": c, "loss": loss, "prof": prof,
            "loss_at_point": None if not np.isfinite(w).any() else round(float(np.nanmedian(w)), 2),
            "changed_km2_5km": round(float(np.nansum(big > CHANGE_THRESHOLD) * px_km2), 2),
            "coherent_before_fraction_5km": round(float(np.mean(np.isfinite(big))), 2) if big.size else 0.0})
    if not results:
        return {"error": "the before and event pairs do not share the same grid", "ambiguous_pairs": amb}
    # main geometry: the one with the most usable (coherent-before) area, never the largest loss
    main = max(results, key=lambda r: r["coherent_before_fraction_5km"])
    b, c = main["b"], main["c"]
    usable = [r for r in results if r["loss_at_point"] is not None
              and r["coherent_before_fraction_5km"] >= USABLE_COHERENT_MIN]
    geoms = [{"direction": r["c"].direction, "track": r["c"].track, "frame": r["c"].frame,
              "loss_at_point": r["loss_at_point"], "changed_km2_5km": r["changed_km2_5km"],
              "coherent_before_fraction_5km": r["coherent_before_fraction_5km"], "usable": r in usable}
             for r in results]
    sides = {r["loss_at_point"] > CHANGE_THRESHOLD for r in usable}     # frames that barely cover the point do not vote
    layer = raster.render_png(np.where(main["loss"] > 0.1, main["loss"], np.nan), main["prof"], f"sc_{c.id}",
                              "inferno", 0.1, 0.8)
    layer["title"] = f"Surface change (coherence loss), {c.ref[:8]}→{c.sec[:8]}"
    return {
        "mode": "event" if event else "latest",
        "event_day": event[:8] if event else None, "event_precision": precision if event else None,
        "pre_pair": b.id, "co_pair": c.id, "direction": c.direction, "track": c.track, "frame": c.frame,
        "crid": c.crid, "maturity": c.maturity,
        "pre_date_before": b.ref[:8], "pre_date_after": b.sec[:8],
        "date_before": c.ref[:8], "date_after": c.sec[:8], "window_days": c.span_days,
        "loss_at_point": main["loss_at_point"], "changed_km2_5km": main["changed_km2_5km"],
        "coherent_before_fraction_5km": main["coherent_before_fraction_5km"],
        "threshold": CHANGE_THRESHOLD,
        "n_geometries": len(results), "n_usable_geometries": len(usable), "geometries": geoms,
        "geometries_agree": None if len(usable) < 2 else len(sides) == 1,
        "changed_km2_range": [min(r["changed_km2_5km"] for r in usable), max(r["changed_km2_5km"] for r in usable)]
        if usable else None,
        "ambiguous_pairs": amb, "layer": layer,
    }
