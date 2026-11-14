"""Al Haouz (Asni, 10 Oct 2026): a candidate surface-change area, NOT a flood map.

Three indicators, each with its σ, all from computed outputs:
- coherence-loss excess over the frame within 5 km: results/events/haouz-flood-2026-10-10.json (recipes/damage.py).
  σ from the no-event test of the same recipe: a share `null_false_alarm` (1 %) of random circles exceeds
  `excess_margin` (0.11), so σ = excess_margin / z(1 − null_false_alarm) under a Gaussian assumption (said in limits);
- backscatter change (dB): the `backscatter_change` finding of results/haouz-flood-2026/findings.json (Anass, GCOV);
- soil-moisture anomaly (m³/m³): results/events/haouz-soil-moisture.json (SME2 anomaly ± the product uncertainty).

The three share the same NISAR passes, so they are not independent. No flooded surface (km²) is given: a
`flooded_area` finding or any km² finding in the inputs is dropped.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from statistics import NormalDist

log = logging.getLogger(__name__)
CASE_ID = "haouz-flood-2026"
FLOOD_EVENT = "haouz-flood-2026-10-10"
SOIL_EVENT = "haouz-soil-moisture"
CLEAR_SIGMAS = 2.0                 # an indicator is a clear change when |value| > 2σ (coherence: recipe level "strong")
LABELS = {
    "coherence_loss_excess": {"fr": "Excès de perte de cohérence (5 km, par rapport à la scène)",
                              "en": "Coherence-loss excess (5 km, over the frame)",
                              "ar": "فائض فقدان التماسك (5 كم، مقارنة بالمشهد)"},
    "backscatter_change": {"fr": "Changement de rétrodiffusion", "en": "Backscatter change", "ar": "تغير الانتثار الخلفي"},
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


def coherence_indicator(facts: dict) -> tuple[dict, dict]:
    """(finding, extra facts) from the damage recipe's facts. KeyError / ValueError if a key is missing."""
    excess, margin, nfa = float(facts["excess_over_frame"]), float(facts["excess_margin"]), float(facts["null_false_alarm"])
    z = NormalDist().inv_cdf(1.0 - nfa)
    sigma = round(margin / z, 3)
    if not sigma > 0:
        raise ValueError("no-event level must be > 0")
    return (_finding("coherence_loss_excess", round(excess, 3), sigma, "coherence"),
            {"clear": facts.get("excess_level") == "strong", "margin": margin, "nfa": nfa, "z": round(z, 2)})


def indicators(results: Path, anass_findings: list[dict]) -> tuple[list[dict], list[dict], dict]:
    """(findings, limits for what is not computed, facts used by the headline and the limits)."""
    findings, missing, info = [], [], {"clear": [], "products": [], "crids": []}
    flood = _read(results / "events" / f"{FLOOD_EVENT}.json")
    if flood is None:
        missing.append(_not_computed("coherence_loss_excess", f"results/events/{FLOOD_EVENT}.json not available"))
    else:
        f = flood.get("facts") or {}
        try:
            fin, extra = coherence_indicator(f)
            findings.append(fin)
            info.update(extra_coherence=extra, flood_facts=f)
            if extra["clear"]:
                info["clear"].append("coherence_loss_excess")
            info["products"] += [p for p in (f.get("pre_pair"), f.get("co_pair")) if p]
            if f.get("crid"):
                info["crids"].append((f["crid"], f.get("maturity", "unknown")))
        except (KeyError, TypeError, ValueError) as exc:
            missing.append(_not_computed("coherence_loss_excess", f"missing value in the recipe output: {exc}"))
    bs = next((x for x in anass_findings if x.get("id") == "backscatter_change"), None)
    if bs is None or not (bs.get("nisar") or {}).get("uncertainty"):
        missing.append(_not_computed("backscatter_change", f"not in results/{CASE_ID}/findings.json" if bs is None
                                     else "no uncertainty in results/haouz-flood-2026/findings.json"))
    else:
        m = bs["nisar"]
        findings.append(_finding("backscatter_change", m["value"], m["uncertainty"], "dB"))
        if abs(m["value"]) > CLEAR_SIGMAS * m["uncertainty"]:
            info["clear"].append("backscatter_change")
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
    c = info.get("extra_coherence")
    if c:
        pct = round(100 * c["nfa"], 2)
        out.append(_limit(f"σ de l'excès de cohérence tiré du test sans événement : {pct:g} % des cercles aléatoires "
                          f"dépassent {c['margin']}, σ = {c['margin']} / {c['z']} (hypothèse gaussienne).",
                          f"σ of the coherence-loss excess from the no-event test: {pct:g} % of random circles exceed "
                          f"{c['margin']}, σ = {c['margin']} / {c['z']} (Gaussian assumption).",
                          f"σ لفائض التماسك مأخوذ من اختبار غياب الحدث: {pct:g} % من الدوائر العشوائية تتجاوز "
                          f"{c['margin']}، σ = {c['margin']} / {c['z']} (افتراض غاوسي)."))
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
