"""Map figures (with a RasterLayer) and full timelines for the case studies.

Map: a PNG rendered with the frontend palettes (raster.render_png), copied to cases/figures/<id>/, plus the layer
description the frontend contract needs (bounds, unit, range, palette, sign convention, period, source).
Timeline:
- the event;
- every NISAR acquisition time of the products used (from the GUNW / GCOV names);
- the ASF publication date (processingDate) of each product.
"""
from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests

import raster
from config import CACHE_DIR, LOS_SIGN

log = logging.getLogger(__name__)
ASF_SEARCH = "https://api.daac.asf.alaska.edu/services/search/param"
USER_AGENT = "nisar-pulse/1.0 (NASA Space Apps 2026)"
MAX_ACQUISITIONS = 12        # a method case can use dozens of pairs: keep the latest ones on the timeline
PALETTE_CMAP = {"diverging_displacement": "RdBu_r", "sequential_coherence": "magma",
                "sequential_coherence_loss": "inferno", "sequential_moisture": "YlGnBu"}


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp_iso(stamp: str) -> str:
    """'YYYYMMDDTHHMMSS' (or 'YYYYMMDD') -> ISO UTC."""
    if len(stamp) >= 15:
        return iso_utc(datetime.strptime(stamp[:15], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc))
    return iso_utc(datetime.strptime(stamp[:8], "%Y%m%d").replace(tzinfo=timezone.utc))


def _date(stamp: str) -> str:
    return f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}"


def _l3(fr: str, en: str, ar: str) -> dict:
    return {"fr": fr, "en": en, "ar": ar}


# ---------------------------------------------------------------- ASF publication date
def asf_processing_date(granule: str, offline: bool) -> str | None:
    """ASF 'processingDate' of a granule (cached in <cache>/asf/), as ISO UTC; None when unknown."""
    path = CACHE_DIR / "asf" / f"{granule}.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8")).get("processingDate")
    if offline:
        return None
    try:
        r = requests.get(ASF_SEARCH, params={"granule_list": granule, "output": "geojson"}, timeout=60,
                         headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        feats = r.json().get("features", [])
    except (requests.RequestException, ValueError) as exc:
        log.warning("ASF search failed for %s: %s", granule, exc)
        return None
    raw = feats[0]["properties"].get("processingDate") if feats else None
    value = iso_utc(datetime.fromisoformat(raw.replace("Z", "+00:00"))) if raw else None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"granule": granule, "processingDate": value}), encoding="utf-8")
    return value


# ---------------------------------------------------------------- timeline
def timeline(event: tuple[dict, str] | None, products: list, offline: bool) -> tuple[list[dict], list[str]]:
    """(items sorted by time, placeholders). event = (label {fr,en,ar}, ISO UTC) or None."""
    items, missing = [], []
    if event:
        items.append({"label": event[0], "at": event[1]})
    acq = {}
    for p in products:
        tag = f"T{p.track} {p.direction[:3]}."
        for stamp in (p.ref, p.sec):
            acq.setdefault(stamp, tag)
    for stamp, tag in sorted(acq.items())[-MAX_ACQUISITIONS:]:
        items.append({"label": _l3(f"Acquisition NISAR ({tag})", f"NISAR acquisition ({tag})", f"التقاط NISAR ({tag})"),
                      "at": stamp_iso(stamp)})
    for p in products:
        published = asf_processing_date(p.name, offline)
        if published:
            items.append({"label": _l3(f"Publié par l'ASF (T{p.track})", f"Published by ASF (T{p.track})",
                                       f"نشر من طرف ASF (T{p.track})"), "at": published})
        else:
            missing.append(f"timeline: ASF processingDate of {p.name}")
    if not products:
        missing.append("timeline: no NISAR product")
    return sorted(items, key=lambda i: i["at"]), missing


# ---------------------------------------------------------------- map figures
def _publish_png(case_id: str, src: Path, fig_dir: Path) -> str:
    dst = fig_dir / case_id / src.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return f"/api/cases/{case_id}/figures/{src.name}"


def map_figure(case_id: str, arr: np.ndarray, prof: dict, *, fig_dir: Path, fig_id: str, kind: str, unit: str,
               palette: str, vmin: float, vmax: float, title: dict, caption: dict, source: str,
               period: dict | None, sign_convention: str | None) -> dict:
    """A 'map' Figure with its RasterLayer, rendered with the frontend palette."""
    name = f"case_{case_id}_{fig_id}"
    info = raster.render_png(arr, prof, name, PALETTE_CMAP[palette], vmin, vmax)
    url = _publish_png(case_id, CACHE_DIR / "layers" / f"{name}.png", fig_dir)
    (s, w), (n, e) = info["bounds"]
    layer = {"id": name, "kind": kind, "url": url, "bounds": [w, s, e, n], "unit": unit, "min": float(vmin),
             "max": float(vmax), "palette": palette, "sign_convention": sign_convention, "period": period,
             "source": source}
    return {"id": fig_id, "kind": "map", "title": title, "url": url, "caption": caption, "layer": layer}


def displacement_figure(case_id: str, p, lat: float, lon: float, fig_dir: Path) -> dict:
    """LOS displacement map of one GUNW pair (referenced far from the point, corrections as configured)."""
    from recipes import displacement
    d, _coh, prof, sigma, notes = displacement.referenced(p, lat, lon)
    finite = np.abs(d[np.isfinite(d)])
    lim = max(float(np.percentile(finite, 98)) if finite.size else 1.0, 1e-3)
    note = "; ".join(notes) or "no correction applied"
    period = f"{_date(p.ref)} → {_date(p.sec)}"
    cap = {"template": "backend.case_map_caption", "params": {},
           "text": _l3(f"Déplacement en ligne de visée (cm), {p.direction}, {period}. Bruit ±{sigma:.1f} cm. {note}.",
                       f"Line-of-sight displacement (cm), {p.direction}, {period}. Noise ±{sigma:.1f} cm. {note}.",
                       f"الإزاحة في خط النظر (سم)، {p.direction}، {period}. الضجيج ±{sigma:.1f} سم. {note}.")}
    return map_figure(case_id, d, prof, fig_dir=fig_dir, fig_id=f"los_T{p.track}_{p.ref[:8]}_{p.sec[:8]}",
                      kind="displacement", unit="cm", palette="diverging_displacement", vmin=-lim, vmax=lim,
                      title=_l3(f"Déplacement NISAR, trace {p.track}", f"NISAR displacement, track {p.track}",
                                f"إزاحة NISAR، المسار {p.track}"),
                      caption=cap, source=p.id, period={"start": _date(p.ref), "end": _date(p.sec)},
                      sign_convention="positive_toward_satellite" if LOS_SIGN > 0 else "positive_away_from_satellite")


def raster_figure(case_id: str, tif: Path, spec: dict, fig_dir: Path) -> dict:
    """Map figure from a GeoTIFF named in results/<id>/findings.json:
    {"id", "title", "caption", "raster": "file.tif", "layer": {kind, unit, palette, min, max, period?, source?}}."""
    arr, prof = raster.read(tif)
    lay = spec["layer"]
    return map_figure(case_id, arr, prof, fig_dir=fig_dir, fig_id=spec["id"], kind=lay["kind"], unit=lay["unit"],
                      palette=lay["palette"], vmin=float(lay["min"]), vmax=float(lay["max"]), title=spec["title"],
                      caption=spec["caption"], source=lay.get("source", tif.name), period=lay.get("period"),
                      sign_convention=lay.get("sign_convention"))
