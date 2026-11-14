"""Builds the four case studies (docs/CASE_CONTRACT.md) from the computed outputs and writes backend/cases/<id>.json.

    python -m science.cases [--results ../results] [--venezuela-event <usgs id>] [--offline] [--dry-run]

Inputs (each optional; what is missing is listed in "placeholders" and the case stays a draft):
- cases/out/panama-2026.json and *_fit.png (science.panama_fault), cases/out/<id>_exposure.json (science.exposure_run);
- results/<id>/findings.json + its figures, rasters and product ids (format: docs/CASE_CONTRACT.md, "Inputs");
- results/gps/gps_none/gps_*.json and results/gps/gps_iono/gps_*.json (validate_gps.py without / with the
  ionospheric correction);
- the NISAR catalog (co-seismic pairs and the products named by the inputs), USGS and ASF for the timeline.

Every case must ship at least one map figure with a layer and a full timeline. A case is written as "final" only
when nothing is missing and every finding has a non-zero uncertainty.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from pydantic import ValidationError

from science import case_layers, usgs
from science.case_models import CaseStudy, Figure, Finding, TemplatedText
from science.case_store import CASES_DIR, FIGURE_NAME

log = logging.getLogger(__name__)
BACKEND = Path(__file__).resolve().parents[1]
RESULTS = BACKEND.parent / "results"
FIG_NAME = re.compile(r"^[A-Za-z0-9._-]{1,120}\.(png|jpg|jpeg|webp|tif|tiff)$")
EVENTS = {"panama-2026": "us6000u18k", "venezuela-2026": None}
QUAKE_LABEL = {"fr": "Séisme (USGS)", "en": "Earthquake (USGS)", "ar": "الزلزال (USGS)"}
FLOOD_LABEL = {"fr": "Crue", "en": "Flood", "ar": "الفيضان"}


class CaseInputError(RuntimeError):
    """An input file exists but does not have the documented format."""


def out_dir() -> Path:
    return CASES_DIR / "out"


def fig_dir() -> Path:
    return CASES_DIR / "figures"


# ---------------------------------------------------------------- small helpers
def _read(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise CaseInputError(f"{path}: invalid JSON ({exc})") from exc


def _tt(template: str, fr: str, en: str, ar: str, params: dict | None = None) -> dict:
    return {"template": template, "params": params or {}, "text": {"fr": fr, "en": en, "ar": ar}}


def _limit(l3: dict) -> dict:
    return {"template": "backend.case_limit", "params": {}, "text": l3}


def _checked_file(folder: Path, name: str) -> Path:
    if not FIG_NAME.match(name):
        raise CaseInputError(f"file name not allowed: {name}")
    path = folder / name
    if not path.is_file():
        raise CaseInputError(f"file not found: {path}")
    return path


def copy_figure(case_id: str, src: Path) -> str:
    """Copies an image figure into cases/figures/<id>/ and returns its /api URL."""
    if not FIGURE_NAME.match(src.name):
        raise CaseInputError(f"figure must be a png/jpg/webp image: {src.name}")
    src = _checked_file(src.parent, src.name)
    dst = fig_dir() / case_id / src.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return f"/api/cases/{case_id}/figures/{src.name}"


def _bbox(products: list) -> list | None:
    if not products:
        return None
    b = np.array([p.bbox for p in products], dtype=float)
    return [float(b[:, 0].min()), float(b[:, 1].min()), float(b[:, 2].max()), float(b[:, 3].max())]


def _catalog_products(ids: list[str]) -> tuple[list, list[str]]:
    """(catalog Products with these ids, placeholders for the ids not found)."""
    if not ids:
        return [], []
    import catalog
    by_id = {p.id: p for p in catalog.load()}
    found = [by_id[i] for i in ids if i in by_id]
    return found, [f"product {i} not in the catalog" for i in ids if i not in by_id]


def _coseismic_pairs(event_id: str | None) -> list:
    if not event_id:
        return []
    import catalog
    ev = usgs.event(event_id)
    origin = datetime.fromtimestamp(ev.time_ms / 1000, tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
    return catalog.straddling(catalog.find(ev.lat, ev.lon, "GUNW"), origin)


def _maps(case_id: str, products: list, lat: float, lon: float) -> tuple[list, list[str]]:
    """Displacement map figures of the products (render errors become placeholders)."""
    figs, missing = [], []
    for p in products:
        try:
            figs.append(case_layers.displacement_figure(case_id, p, lat, lon, fig_dir()))
        except (OSError, ValueError, KeyError) as exc:
            log.error("%s: map of %s failed: %s", case_id, p.id, exc)
            missing.append(f"map of {p.id} failed: {exc}")
    return figs, missing


# ---------------------------------------------------------------- inputs
def results_part(case_id: str, results: Path) -> tuple[dict, list, list, list, list]:
    """(raw file, findings, figures, limits, placeholders) from results/<id>/findings.json."""
    folder = results / case_id
    data = _read(folder / "findings.json")
    if data is None:
        return {}, [], [], [], [f"results/{case_id}/findings.json not available"]
    try:
        findings = [Finding.model_validate(f).model_dump(mode="json") for f in data.get("findings", [])]
        figures = []
        for f in data.get("figures", []):
            caption = TemplatedText.model_validate(f["caption"]).model_dump(mode="json")
            if "raster" in f:
                fig = case_layers.raster_figure(case_id, _checked_file(folder, f["raster"]),
                                                {**f, "caption": caption}, fig_dir())
            else:
                fig = {"id": f["id"], "kind": f["kind"], "title": f["title"], "caption": caption,
                       "url": copy_figure(case_id, folder / f["file"])}
            figures.append(Figure.model_validate(fig).model_dump(mode="json"))
        limits = [_limit(l3) for l3 in data.get("limits", [])]
    except (ValidationError, KeyError, TypeError) as exc:
        raise CaseInputError(f"results/{case_id}/findings.json: {exc}") from exc
    return data, findings, figures, limits, []


def exposure_part(case_id: str) -> tuple[dict | None, list]:
    data = _read(out_dir() / f"{case_id}_exposure.json")
    if data is None:
        return None, [f"exposure: cases/out/{case_id}_exposure.json not available"]
    return data["exposure"], []


def fault_part(case_id: str) -> tuple[list, list, list, list]:
    """(findings, figures, limits, placeholders) from science.panama_fault's output."""
    data = _read(out_dir() / f"{case_id}.json")
    if data is None:
        return [], [], [], [f"fault inversion: cases/out/{case_id}.json not available"]
    limits = [_limit(l3) for l3 in data.get("limits", [])]
    figures = []
    for f in data.get("figures", []):
        figures.append({"id": f["id"], "kind": f.get("kind", "image"), "url": copy_figure(case_id, out_dir() / f["path"]),
                        "title": {"fr": "Données, modèle et résidu", "en": "Data, model and residual",
                                  "ar": "البيانات والنموذج والبواقي"},
                        "caption": _tt("backend.fault_fit_caption",
                                       "Déplacement en ligne de visée observé, modèle de faille d'Okada et résidu.",
                                       "Observed line-of-sight displacement, Okada fault model and residual.",
                                       "الإزاحة المرصودة في خط النظر ونموذج صدع أوكادا والبواقي.")})
    if not data.get("stable"):
        reasons = "; ".join(data.get("unstable_reasons", [])) or "unknown"
        limits.append(_limit({"fr": f"Magnitude non estimée : l'inversion n'est pas stable ({reasons}).",
                              "en": f"Magnitude not estimated: the inversion is not stable ({reasons}).",
                              "ar": f"لم يتم تقدير القدر: الانعكاس غير مستقر ({reasons})."}))
        return [], figures, limits, ["fault inversion not stable: magnitude not estimated"]
    return data["findings"], figures, limits, []


def _rms_measure(n: int, rms: float) -> dict:
    """RMS with its standard error RMS / sqrt(2n) (Gaussian residuals)."""
    return {"value": round(rms, 2), "uncertainty": round(rms / math.sqrt(2 * n), 2), "unit": "mm", "sigma": 1}


GPS_NAMES = {"none": ("rms_before", "Écart quadratique NISAR–GPS sans correction", "NISAR–GPS RMS, uncorrected",
                      "جذر متوسط مربع الفرق NISAR–GPS دون تصحيح"),
             "iono": ("rms_after", "Écart quadratique NISAR–GPS avec correction", "NISAR–GPS RMS, corrected",
                      "جذر متوسط مربع الفرق NISAR–GPS بعد التصحيح")}


def gps_part(results: Path) -> dict:
    """findings, limits, placeholders, stations, product ids and latest pair date from the GPS comparisons."""
    out = {"findings": [], "limits": [], "missing": [], "stations": [], "products": [], "last": None}
    for label in ("none", "iono"):
        reps = [r for r in (_read(p) for p in sorted((results / "gps" / f"gps_{label}").glob("gps_*.json"))
                            if p.name != "gps_stations.json") if r]
        if not reps:
            out["missing"].append(f"results/gps/gps_{label}/ not available")
            continue
        pairs = []
        for r in reps:
            out["stations"].append(r.get("station") or {})
            for row in r.get("pairs", []):
                if row.get("gps_los_mm") is not None and row.get("nisar_los_mm") is not None:
                    pairs.append((row["nisar_los_mm"], row["gps_los_mm"]))
                    out["last"] = max(out["last"] or "", row.get("date_after", ""))
                    if row.get("product") and row["product"] not in out["products"]:
                        out["products"].append(row["product"])
        if not pairs:
            out["missing"].append(f"results/gps/gps_{label}/: no NISAR-GPS pair")
            continue
        a = np.array(pairs, dtype=float)
        d = a[:, 0] - a[:, 1]
        fid, fr, en, ar = GPS_NAMES[label]
        out["findings"].append({"id": fid, "label": {"fr": fr, "en": en, "ar": ar},
                                "nisar": _rms_measure(len(d), float(np.sqrt(np.mean(d ** 2)))),
                                "reference": None, "reference_source": None, "agreement": "no_reference"})
        if len(d) >= 3 and a[:, 0].std() > 0 and a[:, 1].std() > 0:
            c = float(np.corrcoef(a[:, 0], a[:, 1])[0, 1])
            if c < 0:
                out["limits"].append(_limit({
                    "fr": f"Corrélation NISAR–GPS négative ({c:.2f}, {label}) : signe à vérifier.",
                    "en": f"Negative NISAR–GPS correlation ({c:.2f}, {label}): check the line-of-sight sign.",
                    "ar": f"ارتباط سلبي بين NISAR وGPS ({c:.2f}، {label}): يجب التحقق من إشارة خط النظر."}))
    return out


# ---------------------------------------------------------------- assembly
def headline(case_id: str, findings: list[dict]) -> dict | None:
    """A headline whose numbers come from the findings (None keeps the draft headline and lists it as missing)."""
    by = {f["id"]: f for f in findings}
    if case_id == "panama-2026" and "mw" in by:
        m = by["mw"]["nisar"]
        return _tt("backend.case_headline_mw", f"NISAR mesure Mw {m['value']:.2f} ± {m['uncertainty']:.2f}.",
                   f"NISAR measures Mw {m['value']:.2f} ± {m['uncertainty']:.2f}.",
                   f"يقيس NISAR قدرا قدره {m['value']:.2f} ± {m['uncertainty']:.2f}.", {"mw": m})
    if case_id == "ionosphere-gps" and {"rms_before", "rms_after"} <= set(by):
        b, a = by["rms_before"]["nisar"], by["rms_after"]["nisar"]
        return _tt("backend.case_headline_iono",
                   f"Écart NISAR–GPS : {b['value']} mm sans correction, {a['value']} mm avec.",
                   f"NISAR–GPS misfit: {b['value']} mm uncorrected, {a['value']} mm corrected.",
                   f"الفرق بين NISAR وGPS: {b['value']} مم دون تصحيح، {a['value']} مم بعده.",
                   {"before": b, "after": a})
    if findings:
        f, m = findings[0], findings[0]["nisar"]
        return _tt("backend.case_headline_first",
                   f"{f['label']['fr']} : {m['value']} ± {m['uncertainty']} {m['unit']}.",
                   f"{f['label']['en']}: {m['value']} ± {m['uncertainty']} {m['unit']}.",
                   f"{f['label']['ar']}: {m['value']} ± {m['uncertainty']} {m['unit']}.", {"value": m})
    return None


def finalize(base: dict, parts: dict, placeholders: list[str]) -> dict:
    """Merges the computed parts into the draft, decides the status, validates against the contract."""
    case = {**base, **{k: v for k, v in parts.items() if v is not None}}
    placeholders = list(placeholders)
    if parts.get("headline") is None:       # the draft's "[DRAFT]" texts would otherwise survive
        placeholders.append("headline: no finding to report")
    if parts.get("limits") is None:
        placeholders.append("limits: none computed")
    if not any(f.get("layer") for f in parts.get("figures") or []):
        placeholders.append("figures: no map with a layer")
    if not parts.get("timeline"):
        placeholders.append("timeline: empty")
    case["placeholders"] = sorted(set(placeholders))
    has_findings = bool(parts.get("findings"))
    case["status"] = "final" if not case["placeholders"] and has_findings else "draft"
    try:
        return CaseStudy.model_validate(case).model_dump(mode="json")
    except ValidationError as exc:
        raise CaseInputError(f"{base['id']}: the assembled case breaks the contract: {exc}") from exc


def _base(case_id: str) -> dict:
    return json.loads((CASES_DIR / f"{case_id}.json").read_text(encoding="utf-8"))


def build_quake(case_id: str, results: Path, event_id: str | None, offline: bool) -> dict:
    base = _base(case_id)
    missing, ev, pairs = [], None, []
    if not event_id:
        missing.append("USGS event id not set: no date, timeline or map")
    else:
        try:
            ev = usgs.event(event_id)
            pairs = _coseismic_pairs(event_id)
        except usgs.UsgsError as exc:
            log.warning("%s: %s", case_id, exc)
            missing.append(f"USGS event unavailable ({exc})")
    when = case_layers.iso_utc(datetime.fromtimestamp(ev.time_ms / 1000, tz=timezone.utc)) if ev else None
    tl, m1 = case_layers.timeline((QUAKE_LABEL, when) if when else None, pairs, offline)
    maps, m4 = _maps(case_id, pairs, ev.lat, ev.lon) if ev else ([], [])
    if case_id == "panama-2026":
        findings, figures, limits, m2 = fault_part(case_id)
    else:
        _raw, findings, figures, limits, m2 = results_part(case_id, results)
    exposure, m3 = exposure_part(case_id)
    bbox = _bbox(pairs)
    parts = {"findings": findings or None, "figures": maps + figures, "exposure": exposure, "timeline": tl or None,
             "limits": limits or None, "date": when, "headline": headline(case_id, findings),
             "location": {**base["location"], "bbox": bbox} if bbox else None}
    if not bbox:
        missing.append("location.bbox: no co-seismic NISAR pair")
    return finalize(base, parts, missing + m1 + m2 + m3 + m4)


def build_flood(case_id: str, results: Path, offline: bool) -> dict:
    base = _base(case_id)
    raw, findings, figures, limits, missing = results_part(case_id, results)
    exposure, m3 = exposure_part(case_id)
    products, m5 = _catalog_products(raw.get("products", []))
    if raw and "date" not in raw:
        missing.append(f"results/{case_id}/findings.json: 'date' not given")
    if raw and not raw.get("products"):
        missing.append(f"results/{case_id}/findings.json: 'products' not given (needed for the timeline)")
    tl, m1 = case_layers.timeline((FLOOD_LABEL, raw["date"]) if raw.get("date") else None, products, offline)
    bbox = raw.get("bbox") or _bbox(products)
    if raw and not bbox:
        missing.append(f"results/{case_id}/findings.json: no 'bbox' and no product to derive it")
    parts = {"findings": findings or None, "figures": figures, "exposure": exposure, "limits": limits or None,
             "date": raw.get("date"), "timeline": tl or None, "headline": headline(case_id, findings),
             "location": {**base["location"], "bbox": bbox} if bbox else None}
    return finalize(base, parts, missing + m1 + m3 + m5)


def build_iono(results: Path, offline: bool) -> dict:
    base = _base("ionosphere-gps")
    g = gps_part(results)
    missing = list(g["missing"])
    products, m5 = _catalog_products(g["products"])
    pts = np.array([(s["lon"], s["lat"]) for s in g["stations"] if "lat" in s and "lon" in s], dtype=float)
    loc = None
    if pts.size:
        bbox = [float(pts[:, 0].min() - 0.1), float(pts[:, 1].min() - 0.1),
                float(pts[:, 0].max() + 0.1), float(pts[:, 1].max() + 0.1)]
        loc = {**base["location"], "bbox": bbox, "lat": float(pts[:, 1].mean()), "lon": float(pts[:, 0].mean())}
    else:
        missing.append("location: no GPS station report")
    last = g["last"]
    date = f"{last[:4]}-{last[4:6]}-{last[6:8]}T00:00:00Z" if last and len(last) >= 8 else None
    if date is None:
        missing.append("date: no NISAR-GPS pair")
    tl, m1 = case_layers.timeline(None, products, offline)
    latest = sorted(products, key=lambda p: p.sec)[-1:]
    maps, m4 = _maps("ionosphere-gps", latest, loc["lat"], loc["lon"]) if loc and latest else ([], [])
    method = _limit({"fr": "Écart quadratique groupé sur toutes les stations ; incertitude = RMS/√(2n).",
                     "en": "RMS pooled over all stations; uncertainty = RMS/√(2n).",
                     "ar": "جذر متوسط المربعات مجمّع على كل المحطات؛ الشك = RMS/√(2n)."})
    parts = {"findings": g["findings"] or None, "limits": [method, *g["limits"]], "location": loc, "date": date,
             "headline": headline("ionosphere-gps", g["findings"]), "figures": maps, "timeline": tl or None}
    return finalize(base, parts, missing + m1 + m4 + m5)


def build_all(results: Path = RESULTS, venezuela_event: str | None = None, offline: bool = False,
              write: bool = True) -> dict[str, dict]:
    built = {"panama-2026": build_quake("panama-2026", results, EVENTS["panama-2026"], offline),
             "venezuela-2026": build_quake("venezuela-2026", results, venezuela_event, offline),
             "haouz-flood-2026": build_flood("haouz-flood-2026", results, offline),
             "ionosphere-gps": build_iono(results, offline)}
    if write:
        for cid, case in built.items():
            (CASES_DIR / f"{cid}.json").write_text(json.dumps(case, ensure_ascii=False, indent=1), encoding="utf-8")
    return built


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", type=Path, default=RESULTS)
    ap.add_argument("--venezuela-event", help="USGS id of the 24 June 2026 Venezuela mainshock")
    ap.add_argument("--offline", action="store_true", help="no ASF lookup")
    ap.add_argument("--dry-run", action="store_true", help="build and validate, write nothing")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    for cid, case in build_all(a.results, a.venezuela_event, a.offline, not a.dry_run).items():
        print(f"{cid}: {case['status']}" + (f"  missing: {case['placeholders']}" if case["placeholders"] else ""))


if __name__ == "__main__":
    main()
