"""Al Haouz (Asni, 10 Oct 2026): a candidate surface-change area, NOT a flood map.

Three indicators, each with its σ, all from computed outputs:
- coherence loss and backscatter change (dB) in the 5 km circle, from results/haouz-flood-2026/findings.json (Anass).
  Encoded against the no-event null, without a contract change:
    nisar      = the change measured at the site, with its own measurement uncertainty (standard error with an
                 effective number of looks);
    reference  = the no-event baseline: mean of the 2,000 random circles, uncertainty = their spread (sigma 1);
    reference_source = {name: "No-event baseline: 2,000 random circles, ...", url: the result file or the docs};
    agreement  = recomputed by the usual rule, so "agree" reads "not different from no change".
  The spread of the random circles is never used as the measurement error. A finding without its own uncertainty
  or without the baseline is left out and said in the limits.
- soil-moisture anomaly (m³/m³): results/events/haouz-soil-moisture.json (SME2 anomaly ± the product uncertainty).
results/events/haouz-flood-2026-10-10.json gives the passes, the dates and the CRID.

The three share the same NISAR passes, so they are not independent. No flooded surface (km²) is given: a
`flooded_area` finding or any km² finding in the inputs is dropped.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)
CASE_ID = "haouz-flood-2026"
FLOOD_EVENT = "haouz-flood-2026-10-10"
SOIL_EVENT = "haouz-soil-moisture"
CLEAR_SIGMAS = 2.0                 # soil moisture: a clear change when |anomaly| > 2σ
BASELINE_IDS = ("coherence_loss_excess", "backscatter_change")      # compared with the no-event baseline
BASELINE_UNITS = {"coherence_loss_excess": "coherence", "backscatter_change": "dB"}
LABELS = {
    "coherence_loss_excess": {"fr": "Perte de cohérence (cercle de 5 km), comparée à la référence sans événement",
                              "en": "Coherence loss (5 km circle), compared with the no-event baseline",
                              "ar": "فقدان التماسك (دائرة 5 كم)، مقارنة بخط الأساس دون حدث"},
    "backscatter_change": {"fr": "Changement de rétrodiffusion (cercle de 5 km), comparé à la référence sans événement",
                           "en": "Backscatter change (5 km circle), compared with the no-event baseline",
                           "ar": "تغير الانتثار الخلفي (دائرة 5 كم)، مقارنة بخط الأساس دون حدث"},
    "soil_moisture_anomaly": {"fr": "Anomalie d'humidité du sol", "en": "Soil-moisture anomaly",
                              "ar": "شذوذ رطوبة التربة"},
}
TITLE = {"fr": "Zone candidate de changement de surface près d'Asni (Al Haouz, 10 octobre 2026)",
         "en": "Candidate surface-change area near Asni (Al Haouz, 10 October 2026)",
         "ar": "منطقة مرشحة لتغير السطح قرب أسني (الحوز، 10 أكتوبر 2026)"}


def _limit(fr: str, en: str, ar: str) -> dict:
    return {"template": "backend.case_limit", "params": {}, "text": {"fr": fr, "en": en, "ar": ar}}


def _read(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _finding(fid: str, value: float, sigma: float, unit: str) -> dict:
    return {"id": fid, "label": LABELS[fid], "nisar": {"value": value, "uncertainty": sigma, "unit": unit, "sigma": 1},
            "reference": None, "reference_source": None, "agreement": "no_reference"}


def _not_computed(fid: str, reason: str) -> dict:
    lab = LABELS[fid]
    return _limit(f"{lab['fr']} : non calculé ({reason}).", f"{lab['en']}: not computed ({reason}).",
                  f"{lab['ar']}: لم يُحسب ({reason}).")


def baseline_finding(fid: str, raw: dict | None) -> tuple[dict | None, str | None]:
    """(finding, None) or (None, reason) for a finding compared with the no-event baseline."""
    from science.case_models import Measurement, agreement
    if raw is None:
        return None, f"not in results/{CASE_ID}/findings.json"
    n, r, src = raw.get("nisar") or {}, raw.get("reference"), raw.get("reference_source")
    if n.get("value") is None or not n.get("uncertainty"):
        return None, "no measurement uncertainty at the site (standard error with an effective number of looks)"
    if not r or r.get("value") is None or not r.get("uncertainty") or not src:
        return None, "no no-event baseline (mean and spread of the random circles) with its source"
    unit = BASELINE_UNITS[fid]
    if n.get("unit") != unit or r.get("unit") != unit:
        return None, f"unit must be {unit} for the site and the baseline"
    nisar = {"value": n["value"], "uncertainty": n["uncertainty"], "unit": unit, "sigma": n.get("sigma", 1)}
    reference = {"value": r["value"], "uncertainty": r["uncertainty"], "unit": unit, "sigma": r.get("sigma", 1)}
    return ({"id": fid, "label": LABELS[fid], "nisar": nisar, "reference": reference,
             "reference_source": {"name": src["name"], "url": src["url"]},
             "agreement": agreement(Measurement(**nisar), Measurement(**reference))}, None)


def indicators(results: Path, anass_findings: list[dict]) -> tuple[list[dict], list[dict], dict]:
    """(findings, limits for what is not computed, facts used by the headline and the limits)."""
    findings, missing, info = [], [], {"clear": [], "products": [], "crids": []}
    flood = _read(results / "events" / f"{FLOOD_EVENT}.json")
    f = (flood or {}).get("facts") or {}
    info["flood_facts"] = f
    info["products"] += [p for p in (f.get("pre_pair"), f.get("co_pair")) if p]
    if f.get("crid"):
        info["crids"].append((f["crid"], f.get("maturity", "unknown")))
    by_id = {x.get("id"): x for x in anass_findings}
    for fid in BASELINE_IDS:
        fin, why = baseline_finding(fid, by_id.get(fid))
        if fin is None:
            missing.append(_not_computed(fid, why))
            continue
        findings.append(fin)
        info.setdefault("baseline_sources", []).append(fin["reference_source"]["name"])
        if fin["agreement"] == "disagree":
            info["clear"].append(fid)
    soil = _read(results / "events" / f"{SOIL_EVENT}.json")
    sf = (soil or {}).get("facts") or {}
    if sf.get("anomaly_m3m3") is None or not sf.get("uncertainty_m3m3"):
        missing.append(_not_computed("soil_moisture_anomaly", f"results/events/{SOIL_EVENT}.json not available"
                                     if soil is None else "no anomaly or uncertainty in the SME2 output"))
    else:
        a, u = float(sf["anomaly_m3m3"]), float(sf["uncertainty_m3m3"])
        findings.append(_finding("soil_moisture_anomaly", a, u, "m3/m3"))
        info["soil_date"] = sf.get("latest_date")
        if abs(a) > CLEAR_SIGMAS * u:
            info["clear"].append("soil_moisture_anomaly")
    return findings, missing, info


def headline(findings: list[dict], info: dict) -> dict | None:
    if not findings:
        return None
    n = len(findings)
    if not info["clear"]:
        return {"template": "backend.case_headline_haouz", "params": {"n": n},
                "text": {"fr": f"Zone candidate de changement de surface : pas de changement net ({n} indicateur(s), "
                               "aucun au-delà de son seuil).",
                         "en": f"Candidate surface-change area: no clear change ({n} indicator(s), none beyond its "
                               "threshold).",
                         "ar": f"منطقة مرشحة لتغير السطح: لا تغير واضح ({n} مؤشرات، لا أحد منها يتجاوز عتبته)."}}
    names = {L: ", ".join(LABELS[i][L] for i in info["clear"]) for L in ("fr", "en", "ar")}
    return {"template": "backend.case_headline_haouz", "params": {"n": n},
            "text": {"fr": f"Zone candidate de changement de surface : changement net sur {names['fr']}.",
                     "en": f"Candidate surface-change area: clear change in {names['en']}.",
                     "ar": f"منطقة مرشحة لتغير السطح: تغير واضح في {names['ar']}."}}


def _ymd(s: str) -> date:
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def not_a_flood_map_limits(info: dict) -> list[dict]:
    """Why this case is not a flood map, with the dates of the passes it rests on."""
    out = [_limit("Les trois indicateurs reposent sur les mêmes passages NISAR : ils ne sont pas indépendants et ne "
                  "se confirment pas l'un l'autre.",
                  "The three indicators rest on the same NISAR passes: they are not independent and do not confirm "
                  "each other.",
                  "تعتمد المؤشرات الثلاثة على نفس مرورات NISAR: فهي ليست مستقلة ولا يؤكد بعضها بعضا."),
           _limit("Ce n'est pas une carte d'inondation : la perte de cohérence et le changement de rétrodiffusion viennent "
                  "aussi de la végétation, de l'humidité du sol ou du vent ; aucun masque d'eau n'est dérivé, donc "
                  "aucune surface inondée (km²) n'est donnée.",
                  "This is not a flood map: coherence loss and backscatter change also come from vegetation, soil "
                  "moisture or wind; no water mask is derived, so no flooded surface (km²) is given.",
                  "هذه ليست خريطة فيضان: فقدان التماسك وتغير الانتثار الخلفي ينتجان أيضا عن الغطاء النباتي ورطوبة التربة "
                  "والرياح؛ لم يُستخرج قناع للمياه، لذا لا تُعطى أي مساحة مغمورة (كم²).")]
    f = info.get("flood_facts") or {}
    if f.get("event_day") and f.get("date_after"):
        days = (_ymd(f["date_after"]) - _ymd(f["event_day"])).days
        ev, after = _ymd(f["event_day"]).isoformat(), _ymd(f["date_after"]).isoformat()
        out.append(_limit(f"Premier passage NISAR après la crue : {after}, {days} jours après l'événement ({ev}) ; "
                          "l'eau a pu se retirer avant.",
                          f"First NISAR pass after the flood: {after}, {days} days after the event ({ev}); the water "
                          "may have receded by then.",
                          f"أول مرور لـ NISAR بعد الفيضان: {after}، بعد {days} أيام من الحدث ({ev})؛ ربما انحسرت المياه قبله."))
    for name in sorted(set(info.get("baseline_sources", []))):
        out.append(_limit(f"Référence sans événement : {name}. Son ± est la dispersion des cercles, pas une erreur de "
                          "mesure ; « en accord » signifie « pas différent d'une absence de changement ».",
                          f"No-event baseline: {name}. Its ± is the spread of the circles, not a measurement error; "
                          "'agree' means 'not different from no change'.",
                          f"خط الأساس دون حدث: {name}. قيمة ± هي تشتت الدوائر وليست خطأ قياس؛ "
                          "'متفق' تعني 'لا يختلف عن غياب التغير'."))
    return out


def drop_flood_area(findings: list[dict]) -> list[dict]:
    """Anass's findings without any flooded surface (flooded_area, any km² value) and without the indicators this
    module computes itself."""
    kept = []
    for x in findings:
        if x.get("id") == "flooded_area" or (x.get("nisar") or {}).get("unit") == "km2":
            log.warning("%s: finding %s dropped (no flooded surface in this case)", CASE_ID, x.get("id"))
        elif x.get("id") not in LABELS:
            kept.append(x)
    return kept
