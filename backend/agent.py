"""The investigator: question -> type -> recipe -> independent evidence -> verdict.

Numbers come only from the recipes. The language model (optional) only helps classify the
question and rephrase the template sentence; any number it writes that is not in the facts
makes us fall back to the template."""
from __future__ import annotations

import json
import re
import time

import numpy as np

import catalog
import evidence
from config import ANTHROPIC_API_KEY, GAZETTEER, LLM_MODEL
from recipes import backscatter, damage, decompose, displacement, offsets, soil_moisture, timeseries
from uncertainty import confidence

TYPES = ["sudden_motion", "slow_motion", "damage", "flood", "deforestation", "soil_moisture",
         "large_displacement"]
KEYWORDS = {
    "damage": ["dégât", "degat", "endommag", "détruit", "detruit", "effondr", "damage", "destroy", "collaps",
               "أضرار", "دمار", "تضرر"],
    "sudden_motion": ["séisme", "seisme", "tremblement", "earthquake", "quake", "secousse", "زلزال", "هزة"],
    "flood": ["inond", "flood", "submerg", "crue", "فيضان", "غمر"],
    "deforestation": ["forêt", "foret", "déforest", "deforest", "arbre", "coupe", "forest", "logging", "tree",
                      "غابة", "أشجار"],
    "soil_moisture": ["humidit", "humide", "saturé", "sature", "sécheresse", "secheresse", "soil moisture",
                      "wet", "drought", "رطوبة", "جفاف"],
    "large_displacement": ["glacier", "dune", "sable", "sand", "كثبان"],
    "slow_motion": ["barrage", "dam", "digue", "s'enfonce", "enfonce", "subsid", "sink", "affaiss", "glisse",
                    "glissement", "landslide", "versant", "déform", "deform", "bouge", "move", "mine",
                    "سد", "هبوط", "انزلاق", "يتحرك"],
}
PRIORITY = ["damage", "sudden_motion", "flood", "deforestation", "soil_moisture", "large_displacement",
            "slow_motion"]
EVENTS = {"panama": "20261009T175606", "pitaloza": "20261009T175606", "venezuela": "20260624T000000",
          "caracas": "20260624T000000"}
MONTHS = {"janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
          "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
          "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7, "august": 8,
          "september": 9, "october": 10, "november": 11, "december": 12}


# ---------------------------------------------------------------------------
# Understanding the question
# ---------------------------------------------------------------------------
def detect_lang(q: str) -> str:
    if re.search(r"[؀-ۿ]", q):
        return "ar"
    fr = len(re.findall(r"\b(le|la|les|des|est|ce|mon|ma|mes|depuis|après|il|elle|se)\b", q.lower()))
    en = len(re.findall(r"\b(the|is|my|since|after|has|did|was|this|are)\b", q.lower()))
    return "fr" if fr >= en else "en"


def classify_rules(q: str) -> tuple[str, int]:
    ql = q.lower()
    scores = {t: sum(k in ql for k in KEYWORDS[t]) for t in TYPES}
    best = max(PRIORITY, key=lambda t: (scores[t], -PRIORITY.index(t)))
    return best, scores[best]


def classify_llm(q: str) -> str | None:
    if not ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
        msg = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY).messages.create(
            model=LLM_MODEL, max_tokens=50,
            system="Classify a question about the ground surface into exactly one label: " + ", ".join(TYPES)
                   + ". sudden_motion = movement caused by an earthquake or a sudden event; slow_motion = gradual"
                     " deformation (dam, subsidence, landslide, mine); damage = buildings damaged. Answer with the label only.",
            messages=[{"role": "user", "content": q}])
        label = msg.content[0].text.strip().lower()
        return label if label in TYPES else None
    except Exception:
        return None


def find_place(q: str):
    ql = q.lower()
    for name, (lat, lon) in GAZETTEER.items():
        if name in ql:
            return lat, lon, name
    return None


def find_event_date(q: str) -> str | None:
    ql = q.lower()
    for name, ts in EVENTS.items():
        if name in ql:
            return ts
    m = re.search(r"(20\d\d)-(\d\d)-(\d\d)", ql)
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}T000000"
    m = re.search(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s*(20\d\d)?", ql)
    if m:
        return f"{m.group(3) or '2026'}{MONTHS[m.group(2)]:02d}{int(m.group(1)):02d}T000000"
    return None


# ---------------------------------------------------------------------------
# Running the recipes
# ---------------------------------------------------------------------------
class Steps(list):
    def run(self, name, fn, *a, **k):
        t = time.time()
        try:
            out = fn(*a, **k)
            self.append({"step": name, "ok": True, "ms": int((time.time() - t) * 1000)})
            return out
        except Exception as e:
            self.append({"step": name, "ok": False, "error": str(e), "ms": int((time.time() - t) * 1000)})
            return None


def _one_per_direction(ps):
    best = {}
    for p in ps:
        best.setdefault(p.direction, p)
    return list(best.values())


def run_sudden(lat, lon, event, steps):
    ps = catalog.find(lat, lon, "GUNW")
    steps.append({"step": f"found {len(ps)} interferograms covering the point", "ok": bool(ps), "ms": 0})
    if event:
        ps = catalog.straddling(ps, event) or ps
    picked = _one_per_direction(ps)
    if not picked:
        return None, []
    res = [steps.run(f"displacement {p.direction} {p.ref[:8]}→{p.sec[:8]}", displacement.analyze, p, lat, lon)
           for p in picked]
    res = [r for r in res if r]
    out = {"pairs": res}
    asc = next((r for r in res if r["direction"] == "ascending" and r["los_cm"] is not None), None)
    des = next((r for r in res if r["direction"] == "descending" and r["los_cm"] is not None), None)
    if asc and des:
        pa, pd = catalog.by_id(asc["product"]), catalog.by_id(des["product"])
        out["decomposition_cm"] = steps.run("vertical / east-west split", decompose.combine,
                                            asc["los_cm"], pa, des["los_cm"], pd)
    main = max(res, key=lambda r: abs(r["los_cm"] or 0))
    out.update(value_cm=main["los_cm"], noise_cm=main["noise_cm"], coherence=main["coherence"],
               masked=main["masked_fraction_10km"], date_before=min(r["date_before"] for r in res),
               date_after=max(r["date_after"] for r in res))
    return out, picked


def run_slow(lat, lon, steps):
    ps = catalog.find(lat, lon, "GUNW")
    steps.append({"step": f"found {len(ps)} interferograms covering the point", "ok": bool(ps), "ms": 0})
    if not ps:
        return None, []
    series = steps.run("time series (small-baseline inversion)", timeseries.point_series, ps, lat, lon) or []
    if not series:
        return None, ps
    out = {"series": series}
    asc = next((s for s in series if s["direction"] == "ascending" and s.get("velocity_mm_yr") is not None), None)
    des = next((s for s in series if s["direction"] == "descending" and s.get("velocity_mm_yr") is not None), None)
    if asc and des:
        pa = next(p for p in ps if p.geometry == (asc["track"], asc["frame"]))
        pd = next(p for p in ps if p.geometry == (des["track"], des["frame"]))
        out["decomposition_mm_yr"] = steps.run("vertical / east-west split", decompose.combine,
                                               asc["velocity_mm_yr"], pa, des["velocity_mm_yr"], pd)
    main = series[0]
    out.update(velocity_mm_yr=main.get("velocity_mm_yr"), velocity_sigma=main.get("velocity_sigma_mm_yr"),
               total_mm=main.get("total_los_mm"), noise_mm=main.get("noise_mm"), n_pairs=main["n_pairs"],
               first_date=main["first_date"], last_date=main["last_date"],
               acceleration=main.get("acceleration_mm_yr2"))
    # a map of the most recent pair, for context
    latest = max((p for p in ps if p.geometry == (main["track"], main["frame"])), key=lambda p: p.sec)
    lay = steps.run("map of the latest pair", displacement.analyze, latest, lat, lon)
    if lay:
        out["layer"] = lay.get("layer")
        out["profile"] = lay.get("profile")
    return out, ps


def investigate(question: str, lat: float | None = None, lon: float | None = None,
                lang: str | None = None, date: str | None = None) -> dict:
    steps = Steps()
    lang = lang or detect_lang(question)
    qtype, score = classify_rules(question)
    if score == 0:
        llm = classify_llm(question)
        if llm:
            qtype = llm
    steps.append({"step": f"question type: {qtype}", "ok": True, "ms": 0})
    place_name = None
    if lat is None or lon is None:
        found = find_place(question)
        if not found:
            return {"error": "no location: click on the map or name a known place", "type": qtype,
                    "known_places": sorted(set(GAZETTEER))}
        lat, lon, place_name = found
    event = (date.replace("-", "") + "T000000") if date else find_event_date(question)
    facts, used, ev, layers = None, [], [], []

    if qtype == "sudden_motion":
        facts, used = run_sudden(lat, lon, event, steps)
        if facts:
            ev.append(steps.run("USGS earthquakes between the passes", evidence.earthquakes, lat, lon,
                                facts["date_before"], facts["date_after"]))
            layers = [r["layer"] for r in facts["pairs"] if r.get("layer")]
    elif qtype == "slow_motion":
        facts, used = run_slow(lat, lon, steps)
        if facts:
            ev.append(steps.run("rain over the period", evidence.rainfall, lat, lon, facts["first_date"],
                                facts["last_date"]))
            layers = [facts["layer"]] if facts.get("layer") else []
    elif qtype == "damage":
        ps = catalog.find(lat, lon, "GUNW")
        facts = steps.run("coherence-loss damage proxy", damage.analyze, ps, lat, lon, event or "99999999")
        used = ps
        if facts and "error" not in facts:
            layers = [facts["layer"]]
            co = catalog.by_id(facts["co_pair"])
            ev.append(steps.run("USGS earthquakes", evidence.earthquakes, lat, lon, co.ref, co.sec))
    elif qtype in ("flood", "deforestation"):
        ps = catalog.find(lat, lon, "GCOV")
        used = ps
        facts = steps.run(f"backscatter change ({qtype})", backscatter.analyze, ps, lat, lon, qtype,
                          event[:8] if event else None)
        if facts and "error" not in facts:
            layers = [facts["layer"]]
            if qtype == "flood":
                ev.append(steps.run("rain before the flood", evidence.rainfall, lat, lon, facts["before"], facts["after"]))
            else:
                ev.append(steps.run("FIRMS fires", evidence.fires, lat, lon, facts["after"], 10))
    elif qtype == "soil_moisture":
        ps = catalog.find(lat, lon, "SME2")
        used = ps
        facts = steps.run("NISAR soil moisture (SME2)", soil_moisture.analyze, ps, lat, lon)
        if facts and "error" not in facts:
            layers = [facts["layer"]]
            last = facts["latest_date"]
            from datetime import date as _date, timedelta
            start = (_date(int(last[:4]), int(last[4:6]), int(last[6:8])) - timedelta(days=30)).strftime("%Y%m%d")
            ev.append(steps.run("rain in the 30 days before", evidence.rainfall, lat, lon, start, last))
    elif qtype == "large_displacement":
        ps = catalog.find(lat, lon, "GOFF")
        used = ps
        facts = steps.run("pixel offsets", offsets.analyze, ps, lat, lon)
        if facts and "error" not in facts:
            layers = [facts["layer"]]

    expo = steps.run("what is exposed (OpenStreetMap)", evidence.exposure, lat, lon) if facts else None
    if expo:
        ev.append(expo)
    ev = [e for e in ev if e]
    resp = {"question": question, "lang": lang, "type": qtype,
            "place": {"lat": lat, "lon": lon, "name": place_name},
            "data_used": [p.id for p in used][:30], "layers": layers, "evidence": ev, "steps": steps}
    if not facts or "error" in (facts or {}):
        resp.update(verdict=no_data_sentence(qtype, lang, facts), confidence="low", alert_level="none",
                    facts=facts or {}, cannot_say=cannot_say(qtype, lang))
        return resp

    conf, reasons, level = assess(qtype, facts, ev)
    sentence = template(qtype, facts, lang)
    sentence = rephrase(sentence, facts, lang) or sentence
    resp.update(verdict=sentence, confidence=conf, confidence_reasons=reasons, alert_level=level,
                facts=_clean(facts), cannot_say=cannot_say(qtype, lang),
                series=facts.get("series"), profile=facts.get("profile") or
                (facts["pairs"][0].get("profile") if facts.get("pairs") else None))
    return resp


# ---------------------------------------------------------------------------
# Confidence, alert level, sentences
# ---------------------------------------------------------------------------
def assess(qtype, f, ev):
    agrees = any(e.get("status") == "agrees" and e.get("source") != "OpenStreetMap" for e in ev)
    exposed = any(e.get("source") == "OpenStreetMap" and e.get("exposed") for e in ev)
    if qtype == "sudden_motion":
        conf, why = confidence(f["value_cm"] if f["value_cm"] is not None else np.nan,
                               f["noise_cm"] or np.nan, f["coherence"] or 0, f["masked"], agrees)
    elif qtype == "slow_motion":
        v, s = f.get("velocity_mm_yr"), f.get("velocity_sigma") or f.get("noise_mm")
        conf, why = confidence(v if v is not None else np.nan, s or np.nan, 0.5, 0, agrees)
        if f["n_pairs"] < 4:
            conf, why = "low", why + [f"only {f['n_pairs']} pair(s): a trend needs more passes"]
    elif qtype == "damage":
        loss = f.get("loss_at_point") or 0
        conf = "high" if loss > 0.4 and agrees else "medium" if loss > 0.3 else "low"
        why = [f"coherence loss {loss}"] + (["an earthquake was recorded"] if agrees else [])
    elif qtype in ("flood", "deforestation"):
        area = f.get("open_water_ha", 0) + f.get("flooded_vegetation_ha", 0) + f.get("vegetation_loss_ha", 0)
        conf = "high" if area > 5 and agrees else "medium" if area > 1 else "low"
        why = [f"{area:.1f} ha changed around the point"] + (["independent source agrees"] if agrees else [])
    else:
        conf, why = "medium", ["NISAR Level-3 product (provisional calibration)"]
    level = "none"
    if conf == "low" and qtype not in ("soil_moisture",):
        level = "yellow"
    if conf in ("medium", "high") and qtype != "soil_moisture":
        level = "orange"
    if conf == "high" and exposed:
        level = "red"
    return conf, why, level


def _n(x, d=1):
    return "—" if x is None else f"{x:.{d}f}"


def _dt(s, lang):
    s = str(s)[:8]
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if lang == "en" else f"{s[6:8]}/{s[4:6]}/{s[:4]}"


def template_ar(qtype, f):
    d = lambda k: _dt(f[k], "ar")
    if qtype == "sudden_motion":
        s = (f"بين {d('date_before')} و{d('date_after')}، تحرك سطح الأرض بمقدار {_n(f['value_cm'])} سم على طول "
             f"خط رؤية القمر الصناعي (هامش الضجيج ± {_n(f['noise_cm'])} سم).")
        dec = f.get("decomposition_cm")
        if dec:
            s += f" أي {_n(dec['up'])} سم عموديًا و{_n(dec['east'])} سم نحو الشرق."
        return s
    if qtype == "slow_motion":
        s = (f"من {d('first_date')} إلى {d('last_date')} ({f['n_pairs']} أزواج)، تحركت النقطة بمقدار {_n(f['total_mm'])} ملم، "
             f"أي {_n(f['velocity_mm_yr'])} ملم/سنة على طول خط الرؤية.")
        dec = f.get("decomposition_mm_yr")
        if dec:
            s += f" الحركة العمودية: {_n(dec['up'])} ملم/سنة."
        if f.get("acceleration") is not None:
            s += f" التسارع: {_n(f['acceleration'])} ملم/سنة²."
        return s
    if qtype == "damage":
        return (f"انخفاض في التماسك بمقدار {_n(f['loss_at_point'],2)} عند النقطة؛ {_n(f['damaged_km2_5km'],2)} كم² "
                f"يُرجَّح أنها متضررة في دائرة نصف قطرها 5 كم.")
    if qtype == "flood":
        return (f"بين {d('before')} و{d('after')}: {_n(f['open_water_ha'])} هكتار من المياه المكشوفة و"
                f"{_n(f['flooded_vegetation_ha'])} هكتار من النباتات المغمورة حول النقطة.")
    if qtype == "deforestation":
        return f"بين {d('before')} و{d('after')}: فُقد {_n(f['vegetation_loss_ha'])} هكتار من الغطاء النباتي حول النقطة."
    if qtype == "soil_moisture":
        sign = "+" if f["anomaly_m3m3"] >= 0 else ""
        return (f"رطوبة التربة في {d('latest_date')}: {_n(f['latest_m3m3'],3)} م³/م³ ({sign}{_n(f['anomaly_m3m3'],3)} "
                f"مقارنة بمتوسط {f['n_passes']} عمليات مرور).")
    return f"الإزاحة المقاسة: {_n(f['magnitude_m'],2)} م بين {d('date_before')} و{d('date_after')}."


def template(qtype, f, lang):
    if lang == "ar":
        return template_ar(qtype, f)
    f = {**f}
    for k in ("date_before", "date_after", "first_date", "last_date", "before", "after", "latest_date"):
        if f.get(k):
            f[k] = _dt(f[k], lang)
    fr = lang != "en"
    if qtype == "sudden_motion":
        dec = f.get("decomposition_cm")
        s = (f"Entre le {f['date_before']} et le {f['date_after']}, le sol a bougé de {_n(f['value_cm'])} cm le long "
             f"de la ligne de visée du satellite (bruit ± {_n(f['noise_cm'])} cm)." if fr else
             f"Between {f['date_before']} and {f['date_after']}, the ground moved {_n(f['value_cm'])} cm along the "
             f"satellite line of sight (noise ± {_n(f['noise_cm'])} cm).")
        if dec:
            s += (f" Soit {_n(dec['up'])} cm à la verticale et {_n(dec['east'])} cm vers l'est." if fr else
                  f" That is {_n(dec['up'])} cm vertical and {_n(dec['east'])} cm eastward.")
        return s
    if qtype == "slow_motion":
        dec = f.get("decomposition_mm_yr")
        s = (f"Du {f['first_date']} au {f['last_date']} ({f['n_pairs']} paires), le point a bougé de {_n(f['total_mm'])} mm, "
             f"soit {_n(f['velocity_mm_yr'])} mm/an le long de la ligne de visée." if fr else
             f"From {f['first_date']} to {f['last_date']} ({f['n_pairs']} pairs), the point moved {_n(f['total_mm'])} mm, "
             f"i.e. {_n(f['velocity_mm_yr'])} mm/yr along the line of sight.")
        if dec:
            s += (f" Vertical : {_n(dec['up'])} mm/an." if fr else f" Vertical: {_n(dec['up'])} mm/yr.")
        if f.get("acceleration") is not None:
            s += (f" Accélération : {_n(f['acceleration'])} mm/an²." if fr else f" Acceleration: {_n(f['acceleration'])} mm/yr².")
        return s
    if qtype == "damage":
        return (f"Perte de cohérence de {_n(f['loss_at_point'],2)} au point ; {_n(f['damaged_km2_5km'],2)} km² "
                f"probablement endommagés dans un rayon de 5 km." if fr else
                f"Coherence loss of {_n(f['loss_at_point'],2)} at the point; {_n(f['damaged_km2_5km'],2)} km² "
                f"likely damaged within 5 km.")
    if qtype == "flood":
        return (f"Entre le {f['before']} et le {f['after']} : {_n(f['open_water_ha'])} ha d'eau libre et "
                f"{_n(f['flooded_vegetation_ha'])} ha de végétation inondée autour du point." if fr else
                f"Between {f['before']} and {f['after']}: {_n(f['open_water_ha'])} ha of open water and "
                f"{_n(f['flooded_vegetation_ha'])} ha of flooded vegetation around the point.")
    if qtype == "deforestation":
        return (f"Entre le {f['before']} et le {f['after']} : {_n(f['vegetation_loss_ha'])} ha de végétation perdue "
                f"autour du point." if fr else
                f"Between {f['before']} and {f['after']}: {_n(f['vegetation_loss_ha'])} ha of vegetation lost around the point.")
    if qtype == "soil_moisture":
        return (f"Humidité du sol le {f['latest_date']} : {_n(f['latest_m3m3'],3)} m³/m³ "
                f"({'+' if f['anomaly_m3m3'] >= 0 else ''}{_n(f['anomaly_m3m3'],3)} par rapport à la moyenne de "
                f"{f['n_passes']} passages)." if fr else
                f"Soil moisture on {f['latest_date']}: {_n(f['latest_m3m3'],3)} m³/m³ "
                f"({'+' if f['anomaly_m3m3'] >= 0 else ''}{_n(f['anomaly_m3m3'],3)} vs the mean of {f['n_passes']} passes).")
    return (f"Déplacement mesuré : {_n(f['magnitude_m'],2)} m entre le {f['date_before']} et le {f['date_after']}." if fr else
            f"Measured displacement: {_n(f['magnitude_m'],2)} m between {f['date_before']} and {f['date_after']}.")


def cannot_say(qtype, lang):
    return CANNOT_SAY_AR[qtype] if lang == "ar" else CANNOT_SAY[qtype]["en" if lang == "en" else "fr"]


def no_data_sentence(qtype, lang, facts):
    err = (facts or {}).get("error", "")
    if lang == "ar":
        return f"لا توجد بعد بيانات NISAR محمّلة تسمح بالإجابة هنا. {err}".strip()
    if lang == "en":
        return f"No NISAR data downloaded yet can answer this here. {err}".strip()
    return f"Aucune donnée NISAR téléchargée ne permet encore de répondre ici. {err}".strip()


CANNOT_SAY_AR = {
    "sudden_motion": "يقيس الرادار الحركة على طول خط رؤيته؛ ولا يمكنه التنبؤ بما سيحدث لاحقًا.",
    "slow_motion": "لا يكفي اتجاه بضعة أشهر لتحديد موعد انهيار؛ يبقى الفحص الميداني ضروريًا.",
    "damage": "قد ينتج انخفاض التماسك أيضًا عن أشغال بناء أو نباتات؛ يجب التأكد ميدانيًا.",
    "flood": "يرى الرادار المياه لحظة المرور فقط، لا ذروة الفيضان بين مرورين.",
    "deforestation": "قد ينتج انخفاض إشارة HV أيضًا عن الحصاد أو حريق.",
    "soil_moisture": "قيمة متوسطة لبضعة سنتيمترات علوية من التربة على خلية بمئات الأمتار.",
    "large_displacement": "لا تكشف إزاحات البكسل عن تحركات ببضعة سنتيمترات.",
}

CANNOT_SAY = {
    "sudden_motion": {"fr": "Le radar mesure le mouvement le long de sa ligne de visée ; il ne dit pas ce qui va se passer ensuite.",
                      "en": "The radar measures motion along its line of sight; it cannot tell what will happen next."},
    "slow_motion": {"fr": "Une tendance sur quelques mois ne permet pas de dater une rupture ; une inspection sur place reste nécessaire.",
                    "en": "A trend over a few months cannot date a failure; an on-site inspection is still needed."},
    "damage": {"fr": "Une perte de cohérence peut aussi venir de travaux ou de végétation ; à confirmer sur le terrain.",
               "en": "Coherence loss can also come from construction or vegetation; confirm on the ground."},
    "flood": {"fr": "Le radar voit l'eau au moment du passage, pas le pic de la crue entre deux passages.",
              "en": "The radar sees water at pass time, not the flood peak between passes."},
    "deforestation": {"fr": "Une baisse du signal HV peut aussi venir d'une récolte ou d'un incendie.",
                      "en": "An HV drop can also come from a harvest or a fire."},
    "soil_moisture": {"fr": "Valeur moyenne des premiers centimètres du sol sur une maille de plusieurs centaines de mètres.",
                      "en": "Average of the top few centimetres of soil over a cell of several hundred metres."},
    "large_displacement": {"fr": "Les décalages de pixels ne détectent pas les mouvements de quelques centimètres.",
                           "en": "Pixel offsets cannot detect movements of a few centimetres."},
}


def rephrase(sentence: str, facts: dict, lang: str) -> str | None:
    """Optional: the LLM rewrites the sentence (e.g. into Arabic). Rejected if it invents a number."""
    if not ANTHROPIC_API_KEY or lang not in ("ar",):
        return None
    try:
        import anthropic
        target = {"ar": "Modern Standard Arabic"}[lang]
        msg = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY).messages.create(
            model=LLM_MODEL, max_tokens=300,
            system=f"Translate into {target} for a non-expert. Keep every number exactly as written. Add nothing.",
            messages=[{"role": "user", "content": sentence}])
        out = msg.content[0].text.strip()
        nums = lambda s: set(re.findall(r"-?\d+(?:[.,]\d+)?", s.replace("٫", ".")))
        return out if nums(out) <= nums(sentence) | nums(json.dumps(_clean(facts))) else None
    except Exception:
        return None


def _clean(f):
    if isinstance(f, dict):
        return {k: _clean(v) for k, v in f.items() if k not in ("profile",)}
    if isinstance(f, list):
        return [_clean(v) for v in f]
    if isinstance(f, float) and not np.isfinite(f):
        return None
    return f
