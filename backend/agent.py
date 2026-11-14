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
import config as _cfg
from config import ANTHROPIC_API_KEY, GAZETTEER, LLM_MODEL, MIN_RATE_DAYS, SM_UNCERTAINTY
from recipes import backscatter, damage, decompose, displacement, offsets, soil_moisture, timeseries
from uncertainty import confidence

TYPES = ["sudden_motion", "slow_motion", "surface_change", "flood", "deforestation", "soil_moisture",
         "large_displacement"]
# Keywords are matched as WHOLE WORDS (so "tree" does not match "street", "dam" does not match "damage").
# A trailing * allows any word ending: "inond*" matches "inondé", "inondation". Arabic keywords also accept the
# usual one-letter / article prefixes (ال, ب, و, ل...).
KEYWORDS = {
    "surface_change": ["dégât*", "degat*", "endommag*", "détruit*", "detruit*", "effondr*", "crue*",
                       "coulée de boue", "coulee de boue", "éboulement*", "eboulement*", "éboulis",
                       "changé", "changement*", "damage*", "destroy*", "collaps*", "flash flood*",
                       "mudflow*", "mudslide*", "rockfall*", "rock fall*", "changed", "surface change*",
                       "أضرار", "دمار", "تضرر", "سيول", "انهيار*", "تغير*"],
    "sudden_motion": ["séisme*", "seisme*", "tremblement*", "earthquake*", "quake*", "secousse*", "زلزال*", "هزة"],
    "flood": ["inond*", "flood*", "submerg*", "فيضان*", "غمر*"],
    "deforestation": ["forêt*", "foret*", "déforest*", "deforest*", "arbre*", "coupe*", "forest*", "logging",
                      "tree*", "غابة", "أشجار"],
    "soil_moisture": ["humidit*", "humide*", "saturé*", "sature*", "sécheresse*", "secheresse*", "soil moisture",
                      "wet", "drought*", "رطوبة", "جفاف"],
    "large_displacement": ["glacier*", "dune*", "sable", "sand", "كثبان*"],
    "slow_motion": ["barrage*", "dam", "dams", "digue*", "s'enfonce*", "enfonce*", "subsid*", "sink*", "affaiss*",
                    "glisse*", "glissement*", "landslide*", "versant*", "déform*", "deform*", "bouge*", "move*",
                    "mine", "mines", "سد", "هبوط", "انزلاق", "يتحرك"],
}
PRIORITY = ["surface_change", "sudden_motion", "flood", "deforestation", "soil_moisture", "large_displacement",
            "slow_motion"]
# Named events -> (UTC timestamp, precision). "exact": a known instant (USGS origin time). "day": only the
# date is known (a storm lasting all day): the whole UTC day is the event, see catalog.relation.
EVENTS = {"panama": ("20261009T175606", "exact"), "pitaloza": ("20261009T175606", "exact"),
          "venezuela": ("20260624T000000", "day"), "caracas": ("20260624T000000", "day"),
          "haouz": ("20261010T000000", "day"), "al haouz": ("20261010T000000", "day"),
          "الحوز": ("20261010T000000", "day"), "imlil": ("20261010T000000", "day"),
          "إمليل": ("20261010T000000", "day"), "asni": ("20261010T000000", "day"),
          "أسني": ("20261010T000000", "day"), "moulay brahim": ("20261010T000000", "day"),
          "مولاي إبراهيم": ("20261010T000000", "day")}
MONTHS = {"janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
          "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
          "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7, "august": 8,
          "september": 9, "october": 10, "november": 11, "december": 12}

_AR = re.compile(r"[؀-ۿ]")
_AR_PREFIX = r"(?:وال|بال|فال|كال|لل|ال|و|ب|ف|ل|ك)?"


def _kw_re(kw: str):
    """Whole-word regex for a keyword (trailing * = any word ending; Arabic accepts common prefixes)."""
    star = kw.endswith("*")
    stem = kw[:-1] if star else kw
    return re.compile(r"(?<!\w)" + (_AR_PREFIX if _AR.search(stem) else "") + re.escape(stem)
                      + (r"\w*" if star else r"(?!\w)"))


_KW_RE = {t: [_kw_re(k) for k in ks] for t, ks in KEYWORDS.items()}


# ---------------------------------------------------------------------------
# Understanding the question
# ---------------------------------------------------------------------------
def detect_lang(q: str) -> str:
    if re.search(r"[؀-ۿ]", q):
        return "ar"
    fr = len(re.findall(r"\b(le|la|les|des|est|ce|mon|ma|mes|depuis|après|il|elle|se)\b", q.lower()))
    en = len(re.findall(r"\b(the|is|my|since|after|has|did|was|this|are)\b", q.lower()))
    return "fr" if fr >= en else "en"


def classify_rules(q: str) -> tuple[str | None, int]:
    """(type, number of keywords matched). (None, 0) when no keyword matches: we ask, we do not guess."""
    ql = q.lower()
    scores = {t: sum(bool(rx.search(ql)) for rx in _KW_RE[t]) for t in TYPES}
    best = max(PRIORITY, key=lambda t: (scores[t], -PRIORITY.index(t)))
    return (best, scores[best]) if scores[best] else (None, 0)


def classify_llm(q: str) -> str | None:
    if not ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
        msg = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY).messages.create(
            model=LLM_MODEL, max_tokens=50,
            system="Classify a question about the ground surface into exactly one label: " + ", ".join(TYPES)
                   + ". sudden_motion = movement caused by an earthquake or a sudden event; slow_motion = gradual"
                     " deformation (dam, subsidence, landslide, mine); surface_change = the surface changed (flash flood,"
                     " mudflow, rock fall, mine, damaged buildings). Answer with the label only.",
            messages=[{"role": "user", "content": q}])
        label = msg.content[0].text.strip().lower()
        return label if label in TYPES else None
    except Exception:
        return None


def find_place(q: str):
    """Longest alias first, whole words only ("ben guerir mine" before "ben guerir")."""
    ql = q.lower()
    for name in sorted(GAZETTEER, key=len, reverse=True):
        if _kw_re(name).search(ql):
            lat, lon = GAZETTEER[name]
            return lat, lon, name
    return None


def find_event(q: str) -> tuple[str | None, str | None]:
    """(UTC timestamp, precision) of the event named or dated in the question, else (None, None).
    A date alone ("10 octobre 2026", 2026-10-10) is a whole-day event: precision "day"."""
    ql = q.lower()
    for name in sorted(EVENTS, key=len, reverse=True):
        if _kw_re(name).search(ql):
            return EVENTS[name]
    m = re.search(r"(20\d\d)-(\d\d)-(\d\d)", ql)
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}T000000", "day"
    m = re.search(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s*(20\d\d)?", ql)
    if m:
        return f"{m.group(3) or '2026'}{MONTHS[m.group(2)]:02d}{int(m.group(1)):02d}T000000", "day"
    return None, None


def find_event_date(q: str) -> str | None:
    return find_event(q)[0]


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


_MATURITY_RANK = {"validated": 0, "provisional": 1}


def _one_per_direction(ps):
    """One pair per look direction: validated before provisional, then the tightest window, then the newest."""
    best = {}
    for p in sorted(sorted(ps, key=lambda p: p.sec, reverse=True),
                    key=lambda p: (_MATURITY_RANK.get(p.maturity, 2), p.span_days)):
        best.setdefault(p.direction, p)
    return list(best.values())


def run_sudden(lat, lon, event, precision, steps):
    ps = catalog.find(lat, lon, "GUNW")
    steps.append({"step": f"found {len(ps)} interferograms covering the point", "ok": bool(ps), "ms": 0})
    if not event:
        return {"error": "a sudden-event question needs the event: name it or give its date (YYYY-MM-DD)"}, ps
    co = catalog.straddling(ps, event, precision)
    steps.append({"step": f"{len(co)} pair(s) straddle the event ({event[:8]}, {precision} precision)",
                  "ok": bool(co), "ms": 0})
    if not co:                                   # never fall back to pairs that do not straddle the event
        return {"error": f"no NISAR pair straddles the event of {event[:8]} ({precision} precision); other pairs "
                         "were not used", "pairs_before": len(catalog.before(ps, event, precision)),
                "pairs_after": len(catalog.after(ps, event, precision)),
                "ambiguous_pairs": [p.id for p in catalog.ambiguous(ps, event, precision)]}, ps
    picked = _one_per_direction(co)
    res = [steps.run(f"displacement {p.direction} {p.ref[:8]}→{p.sec[:8]}", displacement.analyze, p, lat, lon)
           for p in picked]
    res = [r for r in res if r]
    if not res:
        return {"error": "the displacement could not be computed on the pairs that straddle the event"}, picked
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
               date_after=max(r["date_after"] for r in res), event_day=event[:8], event_precision=precision,
               sign_verified=_cfg.LOS_SIGN_VERIFIED, troposphere_corrected=False,
               iono_screen="subtracted" if main.get("iono_applied") else "not applied",
               reference_same_component=main.get("reference_same_component"),
               reference_share_in_point_component=main.get("reference_share_in_point_component"))
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
    if asc and des and asc["crid"] == des["crid"]:           # a rate needs >= 12 months; CRIDs are never mixed
        pa = next(p for p in ps if p.series_key == (asc["track"], asc["frame"], asc["crid"]))
        pd = next(p for p in ps if p.series_key == (des["track"], des["frame"], des["crid"]))
        out["decomposition_mm_yr"] = steps.run("vertical / east-west split", decompose.combine,
                                               asc["velocity_mm_yr"], pa, des["velocity_mm_yr"], pd)
    main = series[0]
    out.update(velocity_mm_yr=main.get("velocity_mm_yr"), velocity_sigma=main.get("velocity_sigma_mm_yr"),
               total_mm=main.get("total_los_mm"), noise_mm=main.get("noise_mm"), n_pairs=main["n_pairs"],
               first_date=main["first_date"], last_date=main["last_date"], span_days=main["span_days"],
               min_rate_days=main.get("min_rate_days", MIN_RATE_DAYS), crid=main["crid"], maturity=main["maturity"],
               chain_connected=main["chain_connected"], n_components=main["n_components"],
               unmeasured_dates=main["unmeasured_dates"], acceleration=main.get("acceleration_mm_yr2"),
               sign_verified=_cfg.LOS_SIGN_VERIFIED, troposphere_corrected=False, iono_screen=main["iono_screen"],
               reference_same_component=main["reference_same_component"],
               n_pairs_reference_other_component=main["n_pairs_reference_other_component"],
               crosses_data_gap=main["crosses_data_gap"], n_pairs_across_gap=main["n_pairs_across_gap"],
               data_gap_start=(main["data_gaps_crossed"][0][0] if main["data_gaps_crossed"] else None),
               data_gap_end=(main["data_gaps_crossed"][0][1] if main["data_gaps_crossed"] else None))
    # a map of the most recent pair, for context
    latest = max((p for p in ps if p.series_key == (main["track"], main["frame"], main["crid"])), key=lambda p: p.sec)
    lay = steps.run("map of the latest pair", displacement.analyze, latest, lat, lon)
    if lay:
        out["layer"] = lay.get("layer")
        out["profile"] = lay.get("profile")
    return out, ps


UNCLEAR = {
    "fr": "Je n'ai pas compris quel type de question poser au radar. Reformulez avec : un mouvement lent (barrage, "
          "versant, mine), un séisme, un changement de surface (crue, coulée de boue, éboulement), l'humidité du sol, "
          "une inondation ou une déforestation.",
    "en": "I could not tell which kind of question to ask the radar. Please rephrase with: slow motion (dam, slope, "
          "mine), an earthquake, a surface change (flash flood, mudflow, rock fall), soil moisture, a flood or "
          "deforestation.",
    "ar": "لم أفهم نوع السؤال الذي يمكن طرحه على الرادار. أعد الصياغة بذكر: حركة بطيئة (سد، منحدر، منجم)، زلزال، "
          "تغيّر في السطح (سيول، انهيار)، رطوبة التربة، فيضان أو إزالة غابات.",
}


def investigate(question: str, lat: float | None = None, lon: float | None = None,
                lang: str | None = None, date: str | None = None) -> dict:
    steps = Steps()
    lang = lang or detect_lang(question)
    qtype, score = classify_rules(question)
    if score == 0:
        qtype = classify_llm(question)
    steps.append({"step": f"question type: {qtype or 'unclear'}", "ok": qtype is not None, "ms": 0})
    if qtype is None:                                    # unknown question: ask, never guess a type
        return {"question": question, "lang": lang, "type": "unknown", "verdict": UNCLEAR[lang if lang in UNCLEAR else "fr"],
                "confidence": "low", "alert_level": "none", "facts": {}, "cannot_say": "", "evidence": [],
                "layers": [], "data_used": [], "steps": steps}
    place_name = None
    if lat is None or lon is None:
        found = find_place(question)
        if not found:
            return {"error": "no location: click on the map or name a known place", "type": qtype,
                    "known_places": sorted(set(GAZETTEER))}
        lat, lon, place_name = found
    if date:
        event, precision = date.replace("-", "") + "T000000", "day"
    else:
        event, precision = find_event(question)
    routed = None
    if qtype == "flood" and not catalog.find(lat, lon, "GCOV"):
        routed, qtype = "flood", "surface_change"        # no backscatter data here: coherence loss is the honest answer
        steps.append({"step": "no GCOV product covers the point: flood question answered with coherence loss "
                              "(surface change)", "ok": True, "ms": 0})
    facts, used, ev, layers = None, [], [], []

    if qtype == "sudden_motion":
        facts, used = run_sudden(lat, lon, event, precision, steps)
        if facts and "error" not in facts:
            ev.append(steps.run("USGS earthquakes between the passes", evidence.earthquakes, lat, lon,
                                facts["date_before"], facts["date_after"]))
            layers = [r["layer"] for r in facts["pairs"] if r.get("layer")]
    elif qtype == "slow_motion":
        facts, used = run_slow(lat, lon, steps)
        if facts and "error" not in facts:
            ev.append(steps.run("rain over the period", evidence.rainfall, lat, lon, facts["first_date"],
                                facts["last_date"]))
            layers = [facts["layer"]] if facts.get("layer") else []
    elif qtype == "surface_change":
        ps = catalog.find(lat, lon, "GUNW")
        steps.append({"step": f"found {len(ps)} interferograms covering the point", "ok": bool(ps), "ms": 0})
        used = ps
        facts = steps.run("surface change (coherence loss)", damage.analyze, ps, lat, lon, event, precision)
        if facts and "error" not in facts:
            facts["routed_from"] = routed
            layers = [facts["layer"]]
            # Rain and earthquakes are CONTEXT here: they co-occur with a coherence loss, they do not test it.
            ctx = [steps.run("rain over the change window (context only)", evidence.rainfall, lat, lon,
                             facts["date_before"], facts["date_after"])]
            if precision == "exact" and event:
                ctx.append(steps.run("USGS earthquakes (context only)", evidence.earthquakes, lat, lon,
                                     facts["date_before"], facts["date_after"]))
            ev += [{**e, "status": "context" if e.get("status") == "agrees" else e.get("status")} for e in ctx if e]
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

    expo = steps.run("what is exposed (OpenStreetMap)", evidence.exposure, lat, lon) if facts and "error" not in facts else None
    if expo:
        ev.append(expo)
    ev = [e for e in ev if e]
    resp = {"question": question, "lang": lang, "type": qtype,
            "place": {"lat": lat, "lon": lon, "name": place_name},
            "event_time": {"utc": event, "precision": precision} if event else None,
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
def _motion_reasons(f, qtype):
    """Reasons that apply to a signed line-of-sight answer, and whether they cap the confidence at low."""
    why, cap = [], False
    iono = f.get("iono_screen")
    why.append("ionosphere: " + ("the product's phase screen is subtracted, not validated" if iono == "subtracted" else
                                 "screen subtracted on only some pairs, not validated" if iono == "partly subtracted" else
                                 "not corrected") + "; troposphere: not corrected")
    if f.get("reference_same_component") is False:
        cap = True
        why.append("the reference area is not in the point's connected component: the unwrapping can differ by whole fringes")
    elif f.get("reference_same_component"):
        why.append("the reference area shares the point's connected component")
    if qtype == "slow_motion" and f.get("crosses_data_gap"):
        why.append(f"the chain crosses the data gap {f['data_gap_start']} to {f['data_gap_end']}: "
                   f"{f['n_pairs_across_gap']} pair(s) bridge it")
    return why, cap


def assess(qtype, f, ev):
    agrees = any(e.get("status") == "agrees" and e.get("source") != "OpenStreetMap" for e in ev)
    exposed = any(e.get("source") == "OpenStreetMap" and e.get("exposed") for e in ev)
    changed = True
    if qtype == "sudden_motion":
        conf, why = confidence(f["value_cm"] if f["value_cm"] is not None else np.nan,
                               f["noise_cm"] or np.nan, f["coherence"] or 0, f["masked"], agrees)
    elif qtype == "slow_motion":
        v, s = f.get("velocity_mm_yr"), f.get("velocity_sigma") or f.get("noise_mm")
        if v is not None:
            conf, why = confidence(v, s or np.nan, 0.5, 0, agrees)
        else:                                    # record shorter than 12 months: judge the cumulative motion only
            noise = f.get("noise_mm")
            sigma_total = noise * np.sqrt(f["n_pairs"]) if noise else np.nan       # rough: pair errors add up
            total = f.get("total_mm")
            conf, why = confidence(total if total is not None else np.nan, sigma_total, 0.5, 0, False)
            why = why + [f"record of {f['span_days']} days, shorter than {f['min_rate_days']}: no rate, "
                         "confidence capped at medium"]
            if conf == "high":
                conf = "medium"
        if f["n_pairs"] < 4:
            conf, why = "low", why + [f"only {f['n_pairs']} pair(s): a trend needs more passes"]
        if f.get("chain_connected") is False:
            conf, why = "low", why + [f"the pair chain is cut into {f['n_components']} pieces; only the longest is used"]
    elif qtype == "surface_change":
        lvl = f.get("excess_level")
        changed = lvl in ("strong", "borderline")
        conf = "medium" if lvl == "strong" else "low"           # borderline or nothing: low; never "high"
        why = [f"mean coherence loss within 5 km {f['loss_mean_5km']} against {f['frame_loss_mean']} for the whole frame "
               f"(excess {f['excess_over_frame']}; borderline from {f['excess_margin']}, local excess from {f['excess_strong']})",
               f"{f['coverage_5km']:.0%} of the 5 km circle holds valid data, {f['coherent_before_fraction_5km']:.0%} of it was "
               f"coherent before the event",
               f"{f['changed_km2_5km']} km² above the {f['threshold']} loss, {f['baseline_changed_km2']} km² in the previous pair"]
        if lvl == "borderline":
            why.append(f"just above the level that {f['null_false_alarm']:.0%} of no-event circles exceed: not a detection")
        if f.get("baseline_unreliable"):
            conf, why = "low", why + ["the before pair is weaker than usual for this geometry: the baseline is unreliable"]
        if f.get("geometries_agree") is False:
            conf, why = "low", why + ["the viewing geometries disagree"]
        elif f.get("geometries_agree"):
            why.append("every usable viewing geometry reaches the borderline band")
        rng = f.get("changed_km2_range")
        if rng and rng[1] - rng[0] > max(1.0, 2 * rng[0]):
            why.append(f"the viewing geometries differ in changed area ({rng[0]}–{rng[1]} km²)")
        if f.get("mode") == "latest":
            why.append("no event date: the two latest passes are compared")
        why.append("the no-event reference is " + ", ".join(f["null_limits"]) + ": its level is approximate")
        # never "high": rain or an earthquake nearby only co-occur, no independent source tests a coherence loss
        why.append("coherence loss says the surface changed, not why; no independent source tests it")
    elif qtype in ("flood", "deforestation"):
        area = f.get("open_water_ha", 0) + f.get("flooded_vegetation_ha", 0) + f.get("vegetation_loss_ha", 0)
        conf = "high" if area > 5 and agrees else "medium" if area > 1 else "low"
        why = [f"{area:.1f} ha changed around the point"] + (["independent source agrees"] if agrees else [])
    elif qtype == "soil_moisture":
        unc = f.get("uncertainty_m3m3", SM_UNCERTAINTY)
        within = f.get("within_uncertainty", abs(f["anomaly_m3m3"]) < unc)
        if within:                               # a change smaller than the retrieval uncertainty is not a change
            conf = "low"
            why = [f"the change from the mean of the passes ({f['anomaly_m3m3']} m³/m³) is within the product's uncertainty ({unc})"]
        else:
            conf = "medium"
            why = [f"the change from the mean of the passes ({f['anomaly_m3m3']} m³/m³) is larger than the uncertainty ({unc})"]
        why += ["NISAR Level-3 product, provisional calibration: never above medium",
                "the baseline is the mean of passes from several tracks and dates, not one geometry",
                "the retrieval quality flag is not used"]
    else:
        conf, why = "medium", ["NISAR Level-3 product (provisional calibration)"]
    if qtype in ("sudden_motion", "slow_motion"):
        extra, cap = _motion_reasons(f, qtype)
        why = why + extra
        if cap:
            conf = "low"
    level = "none"
    if conf == "low" and qtype not in ("soil_moisture",):
        level = "yellow"
    if conf in ("medium", "high") and qtype != "soil_moisture":
        level = "orange"
    if conf == "high" and exposed:
        level = "red"
    if qtype == "surface_change" and lvl == "none":
        level = "none"                           # nothing detected: no alert (borderline stays yellow, strong orange)
    if qtype in ("sudden_motion", "slow_motion") and not f.get("sign_verified"):
        # STATUS H4: the LOS sign has not been checked on real data, so no signed displacement may raise a level
        conf, level = "low", "none"
        why = why + ["LOS sign unverified (STATUS H4): the direction of the motion is not established; "
                     "shown as an uncorrected line-of-sight change"]
    return conf, why, level


def _n(x, d=1):
    return "—" if x is None else f"{x:.{d}f}"


_CORR = {
    "fr": {"subtracted": "Ionosphère : écran du produit soustrait (non validé) ; troposphère : non corrigée.",
           "not applied": "Ionosphère et troposphère : non corrigées.",
           "partly subtracted": "Ionosphère : écran du produit soustrait sur une partie des paires seulement (non validé) ; "
                                "troposphère : non corrigée."},
    "en": {"subtracted": "Ionosphere: the product's screen is subtracted (not validated); troposphere: not corrected.",
           "not applied": "Ionosphere and troposphere: not corrected.",
           "partly subtracted": "Ionosphere: the product's screen is subtracted on only some pairs (not validated); "
                                "troposphere: not corrected."},
    "ar": {"subtracted": "الأيونوسفير: خُصمت شاشة المنتج (دون تحقق)؛ التروبوسفير: غير مصحَّح.",
           "not applied": "الأيونوسفير والتروبوسفير: غير مصحَّحين.",
           "partly subtracted": "الأيونوسفير: خُصمت شاشة المنتج على بعض الأزواج فقط (دون تحقق)؛ التروبوسفير: غير مصحَّح."},
}


def _motion_tail(f, lang, slow):
    """Ionosphere/troposphere, data gap and reference component: said in every signed line-of-sight answer."""
    s = " " + _CORR[lang].get(f.get("iono_screen") or "not applied", _CORR[lang]["not applied"])
    if slow and f.get("crosses_data_gap"):
        a, b = _dt(f["data_gap_start"], lang), _dt(f["data_gap_end"], lang)
        k = f["n_pairs_across_gap"]
        s += {"fr": f" La série traverse la lacune de données du {a} au {b} ({k} paire l'enjambe)." if k == 1 else
                    f" La série traverse la lacune de données du {a} au {b} ({k} paires l'enjambent).",
              "en": f" The chain crosses the data gap of {a} to {b} ({k} pair bridges it)." if k == 1 else
                    f" The chain crosses the data gap of {a} to {b} ({k} pairs bridge it).",
              "ar": f" تمتد السلسلة عبر فجوة البيانات من {a} إلى {b} (زوج واحد يعبرها)." if k == 1 else
                    f" تمتد السلسلة عبر فجوة البيانات من {a} إلى {b} ({k} أزواج تعبرها)."}[lang]
    ref = f.get("reference_same_component")
    if ref is False:
        s += {"fr": " La zone de référence n'est pas dans la même composante connexe que le point : un décalage d'un nombre "
                    "entier de franges est possible.",
              "en": " The reference area is not in the same connected component as the point: an offset of whole fringes "
                    "is possible.",
              "ar": " منطقة المرجع ليست في المركّبة المتصلة نفسها للنقطة؛ ويُحتمل وجود إزاحة بعدد صحيح من الأهداب."}[lang]
    elif ref:
        s += {"fr": " La zone de référence est dans la même composante connexe que le point.",
              "en": " The reference area is in the same connected component as the point.",
              "ar": " منطقة المرجع في المركّبة المتصلة نفسها للنقطة."}[lang]
    return s


_UNVERIFIED = {"fr": "Variation de ligne de visée non corrigée, signe non vérifié : ",
               "en": "Uncorrected line-of-sight change, sign unverified: ",
               "ar": "تغيّر غير مصحَّح على خط الرؤية، والإشارة غير متحقَّق منها: "}


def _sc(f):
    """Formatted numbers of the surface-change sentences: every one comes from the recipe facts."""
    return dict(mean=_n(f["loss_mean_5km"], 2), frame=_n(f["frame_loss_mean"], 2), exc=_n(f["excess_over_frame"], 2),
                km2=_n(f["changed_km2_5km"], 2), bkm2=_n(f["baseline_changed_km2"], 2), thr=_n(f["threshold"], 1),
                margin=_n(f["excess_margin"], 2), strong=_n(f["excess_strong"], 2),
                pct=f"{f['null_false_alarm_pct']:d}", own=_n(f.get("pair_coherence_mean"), 2),
                med=_n(f.get("other_pairs_coherence_median"), 2))


def _dt(s, lang):
    s = str(s)[:8]
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if lang == "en" else f"{s[6:8]}/{s[4:6]}/{s[:4]}"


def template_ar(qtype, f):
    d = lambda k: _dt(f[k], "ar")
    prov = " (منتج NISAR مؤقت)" if f.get("maturity") == "provisional" else ""
    if qtype == "sudden_motion":
        if f.get("sign_verified"):
            s = (f"بين {d('date_before')} و{d('date_after')}، تحرك سطح الأرض بمقدار {_n(f['value_cm'])} سم على طول "
                 f"خط رؤية القمر الصناعي (هامش الضجيج ± {_n(f['noise_cm'])} سم).")
        else:
            s = (_UNVERIFIED["ar"] + f"بين {d('date_before')} و{d('date_after')}، {_n(f['value_cm'])} سم على طول خط رؤية "
                 f"القمر الصناعي (هامش الضجيج ± {_n(f['noise_cm'])} سم).")
        dec = f.get("decomposition_cm")
        if dec:
            s += f" أي {_n(dec['up'])} سم عموديًا و{_n(dec['east'])} سم نحو الشرق."
        return s + _motion_tail(f, "ar", False)
    if qtype == "slow_motion":
        if f.get("velocity_mm_yr") is None:
            s = ((f"من {d('first_date')} إلى {d('last_date')} ({f['n_pairs']} أزواج، {f['span_days']} يومًا){prov}، "
                  f"تحركت النقطة بمقدار {_n(f['total_mm'])} ملم تراكميًا على طول خط الرؤية (ضجيج كل زوج ± {_n(f['noise_mm'])} ملم). "
                  if f.get("sign_verified") else
                  _UNVERIFIED["ar"] + f"من {d('first_date')} إلى {d('last_date')} ({f['n_pairs']} أزواج، {f['span_days']} يومًا){prov}، "
                  f"{_n(f['total_mm'])} ملم تراكميًا عند النقطة (ضجيج كل زوج ± {_n(f['noise_mm'])} ملم). ") +
                 f"السلسلة قصيرة جدًا لحساب سرعة بالملم/سنة؛ يلزم {f['min_rate_days']} يومًا على الأقل.")
        else:
            s = ((_UNVERIFIED["ar"] if not f.get("sign_verified") else "") +
                 f"من {d('first_date')} إلى {d('last_date')} ({f['n_pairs']} أزواج){prov}، تحركت النقطة بمقدار "
                 f"{_n(f['total_mm'])} ملم، أي {_n(f['velocity_mm_yr'])} ملم/سنة على طول خط الرؤية.")
            dec = f.get("decomposition_mm_yr")
            if dec:
                s += f" الحركة العمودية: {_n(dec['up'])} ملم/سنة."
            if f.get("acceleration") is not None:
                s += f" التسارع: {_n(f['acceleration'])} ملم/سنة²."
        if f.get("chain_connected") is False:
            s += f" سلسلة الأزواج منقطعة (عدد الأجزاء: {f['n_components']})؛ يُستخدم أطولها فقط."
        return s + _motion_tail(f, "ar", True)
    if qtype == "surface_change":
        pre = "" if not f.get("routed_from") else "لا تتوفر بيانات التشتت الخلفي (GCOV) هنا؛ الإجابة مبنية على فقدان التماسك. "
        n = _sc(f)
        if f.get("mode") == "latest":
            s = (f"{pre}دون تاريخ حدث، مقارنة آخر مرور ({d('date_before')} ← {d('date_after')}، {f['window_days']} يومًا){prov} "
                 f"بالمرور الذي سبقه: ")
        else:
            s = f"{pre}بين {d('date_before')} و{d('date_after')} ({f['window_days']} يومًا، نافذة تتضمن حدث {d('event_day')}){prov}: "
        if f["excess_level"] == "strong":
            s += (f"انخفض التماسك الراداري ضمن 5 كم بمعدل {n['mean']} في المتوسط، أي {n['exc']} أكثر من متوسط المشهد كله ({n['frame']}): "
                  f"فائض يفوق {n['strong']}، وهو مستوى نادرًا ما تبلغه الأزواج بلا حدث؛ و{n['km2']} كم² فقدت أكثر من {n['thr']} "
                  f"({n['bkm2']} كم² في الزوج السابق). فائض محلي: تغيّر سطح الأرض حول النقطة؛ لا يحدد الرادار السبب ولا الأضرار ولا عمق المياه.")
        elif f["excess_level"] == "borderline":
            s += (f"انخفض التماسك الراداري ضمن 5 كم بمعدل {n['mean']} في المتوسط، أي {n['exc']} أكثر من متوسط المشهد كله ({n['frame']}): "
                  f"حالة حدّية، هذا الفائض فوق المستوى {n['margin']} الذي تتجاوزه {n['pct']}% من الدوائر بلا حدث بقليل، لكنه دون {n['strong']}؛ "
                  f"و{n['km2']} كم² فقدت أكثر من {n['thr']} ({n['bkm2']} كم² في الزوج السابق). لا يكفي ذلك للقول إن السطح تغيّر، ولا يمكن تحديد سبب.")
        else:
            s += (f"متوسط فقدان التماسك الراداري ضمن 5 كم هو {n['mean']}، مقابل {n['frame']} للمشهد كله: فائض قدره {n['exc']}، "
                  f"دون المستوى {n['margin']} الذي تتجاوزه {n['pct']}% من الدوائر بلا حدث؛ و{n['km2']} كم² فقدت أكثر من {n['thr']} "
                  f"({n['bkm2']} كم² في الزوج السابق). لا تغيّر محلي واضح.")
        s += " المرجع «بلا حدث» مأخوذ من هندسة رؤية واحدة وفصل واحد ودوائر موزعة عشوائيًا في المشهد."
        if f.get("baseline_unreliable"):
            s += f" زوج «قبل» أضعف من المعتاد لهذه الهندسة (التماسك {n['own']} مقابل {n['med']})؛ المرجع غير موثوق والإجابة غير حاسمة."
        return s
    if qtype == "flood":
        return (f"بين {d('before')} و{d('after')}: {_n(f['open_water_ha'])} هكتار من المياه المكشوفة و"
                f"{_n(f['flooded_vegetation_ha'])} هكتار من النباتات المغمورة حول النقطة.")
    if qtype == "deforestation":
        return f"بين {d('before')} و{d('after')}: فُقد {_n(f['vegetation_loss_ha'])} هكتار من الغطاء النباتي حول النقطة."
    if qtype == "soil_moisture":
        sign = "+" if f["anomaly_m3m3"] >= 0 else ""
        s = (f"رطوبة التربة في {d('latest_date')}: {_n(f['latest_m3m3'],3)} م³/م³ ({sign}{_n(f['anomaly_m3m3'],3)} "
             f"مقارنة بمتوسط {f['n_passes']} عمليات مرور).")
        if f.get("within_uncertainty"):
            s += f" هذا التغيّر ضمن عدم اليقين في المنتج ({_n(f['uncertainty_m3m3'], 3)})، ولا يدل على تغيّر حقيقي."
        return s
    return f"الإزاحة المقاسة: {_n(f['magnitude_m'],2)} م بين {d('date_before')} و{d('date_after')}."


def template(qtype, f, lang):
    if lang == "ar":
        return template_ar(qtype, f)
    f = {**f}
    for k in ("date_before", "date_after", "first_date", "last_date", "before", "after", "latest_date", "event_day"):
        if f.get(k):
            f[k] = _dt(f[k], lang)
    fr = lang != "en"
    prov = (" (produit NISAR provisoire)" if fr else " (provisional NISAR product)") if f.get("maturity") == "provisional" else ""
    if qtype == "sudden_motion":
        dec = f.get("decomposition_cm")
        if f.get("sign_verified"):
            s = (f"Entre le {f['date_before']} et le {f['date_after']}, le sol a bougé de {_n(f['value_cm'])} cm le long "
                 f"de la ligne de visée du satellite (bruit ± {_n(f['noise_cm'])} cm)." if fr else
                 f"Between {f['date_before']} and {f['date_after']}, the ground moved {_n(f['value_cm'])} cm along the "
                 f"satellite line of sight (noise ± {_n(f['noise_cm'])} cm).")
        else:
            s = _UNVERIFIED["fr" if fr else "en"] + (
                f"entre le {f['date_before']} et le {f['date_after']}, {_n(f['value_cm'])} cm le long de la ligne de visée "
                f"du satellite (bruit ± {_n(f['noise_cm'])} cm)." if fr else
                f"between {f['date_before']} and {f['date_after']}, {_n(f['value_cm'])} cm along the satellite line of sight "
                f"(noise ± {_n(f['noise_cm'])} cm).")
        if dec:
            s += (f" Soit {_n(dec['up'])} cm à la verticale et {_n(dec['east'])} cm vers l'est." if fr else
                  f" That is {_n(dec['up'])} cm vertical and {_n(dec['east'])} cm eastward.")
        return s + _motion_tail(f, "fr" if fr else "en", False)
    if qtype == "slow_motion":
        if f.get("velocity_mm_yr") is None:
            if f.get("sign_verified"):
                s = (f"Du {f['first_date']} au {f['last_date']} ({f['n_pairs']} paires, {f['span_days']} jours){prov}, le point a "
                     f"bougé de {_n(f['total_mm'])} mm cumulés le long de la ligne de visée (bruit par paire ± {_n(f['noise_mm'])} mm). "
                     if fr else
                     f"From {f['first_date']} to {f['last_date']} ({f['n_pairs']} pairs, {f['span_days']} days){prov}, the point "
                     f"moved {_n(f['total_mm'])} mm cumulative along the line of sight (noise per pair ± {_n(f['noise_mm'])} mm). ")
            else:
                s = _UNVERIFIED["fr" if fr else "en"] + (
                    f"du {f['first_date']} au {f['last_date']} ({f['n_pairs']} paires, {f['span_days']} jours){prov}, "
                    f"{_n(f['total_mm'])} mm cumulés au point (bruit par paire ± {_n(f['noise_mm'])} mm). " if fr else
                    f"from {f['first_date']} to {f['last_date']} ({f['n_pairs']} pairs, {f['span_days']} days){prov}, "
                    f"{_n(f['total_mm'])} mm cumulative at the point (noise per pair ± {_n(f['noise_mm'])} mm). ")
            s += (f"Série trop courte pour donner une vitesse en mm/an : il faut au moins {f['min_rate_days']} jours." if fr else
                  f"The record is too short for a rate in mm/yr: at least {f['min_rate_days']} days are needed.")
        else:
            dec = f.get("decomposition_mm_yr")
            s = (f"Du {f['first_date']} au {f['last_date']} ({f['n_pairs']} paires){prov}, le point a bougé de {_n(f['total_mm'])} mm, "
                 f"soit {_n(f['velocity_mm_yr'])} mm/an le long de la ligne de visée." if fr else
                 f"From {f['first_date']} to {f['last_date']} ({f['n_pairs']} pairs){prov}, the point moved {_n(f['total_mm'])} mm, "
                 f"i.e. {_n(f['velocity_mm_yr'])} mm/yr along the line of sight.")
            if not f.get("sign_verified"):
                s = _UNVERIFIED["fr" if fr else "en"] + s
            if dec:
                s += (f" Vertical : {_n(dec['up'])} mm/an." if fr else f" Vertical: {_n(dec['up'])} mm/yr.")
            if f.get("acceleration") is not None:
                s += (f" Accélération : {_n(f['acceleration'])} mm/an²." if fr else f" Acceleration: {_n(f['acceleration'])} mm/yr².")
        if f.get("chain_connected") is False:
            s += (f" La chaîne de paires est coupée en {f['n_components']} morceaux : seul le plus long est utilisé." if fr else
                  f" The pair chain is cut into {f['n_components']} pieces: only the longest is used.")
        return s + _motion_tail(f, "fr" if fr else "en", True)
    if qtype == "surface_change":
        pre = ("" if not f.get("routed_from") else
               ("Pas de données de rétrodiffusion (GCOV) ici : réponse par la perte de cohérence. " if fr else
                "No backscatter (GCOV) data here: answered with coherence loss. "))
        n = _sc(f)
        if f.get("mode") == "latest":
            s = (f"{pre}Sans date d'événement, comparaison du dernier passage ({f['date_before']} → {f['date_after']}, "
                 f"{f['window_days']} jours){prov} au précédent : " if fr else
                 f"{pre}With no event date, the latest pass ({f['date_before']} → {f['date_after']}, "
                 f"{f['window_days']} days){prov} is compared with the one before: ")
        else:
            s = (f"{pre}Entre le {f['date_before']} et le {f['date_after']} ({f['window_days']} jours, fenêtre qui contient "
                 f"l'événement du {f['event_day']}){prov} : " if fr else
                 f"{pre}Between {f['date_before']} and {f['date_after']} ({f['window_days']} days, a window that contains "
                 f"the event of {f['event_day']}){prov}: ")
        if f["excess_level"] == "strong":
            s += (f"la cohérence radar dans un rayon de 5 km a baissé de {n['mean']} en moyenne, soit {n['exc']} de plus que la moyenne "
                  f"de toute la scène ({n['frame']}) : un excès supérieur à {n['strong']}, niveau que les paires sans événement n'atteignent "
                  f"presque jamais ; {n['km2']} km² ont perdu plus de {n['thr']} ({n['bkm2']} km² dans la paire précédente). Excès local : la "
                  f"surface a changé autour du point ; le radar n'en dit ni la cause, ni les dégâts, ni la hauteur d'eau." if fr else
                  f"radar coherence within 5 km fell by {n['mean']} on average, {n['exc']} more than the whole-frame average "
                  f"({n['frame']}): an excess above {n['strong']}, a level that no-event pairs almost never reach; {n['km2']} km² lost more "
                  f"than {n['thr']} ({n['bkm2']} km² in the previous pair). Local excess: the surface changed around the point; the "
                  f"radar does not say why, nor the damage or the water depth.")
        elif f["excess_level"] == "borderline":
            s += (f"la cohérence radar dans un rayon de 5 km a baissé de {n['mean']} en moyenne, soit {n['exc']} de plus que la moyenne "
                  f"de toute la scène ({n['frame']}) : cas limite, cet excès est juste au-dessus du niveau {n['margin']} que {n['pct']} % "
                  f"des cercles sans événement dépassent, mais sous {n['strong']} ; {n['km2']} km² ont perdu plus de {n['thr']} ({n['bkm2']} km² "
                  f"dans la paire précédente). Cela ne suffit pas pour dire que la surface a changé, et aucune cause ne peut être "
                  f"donnée." if fr else
                  f"radar coherence within 5 km fell by {n['mean']} on average, {n['exc']} more than the whole-frame average "
                  f"({n['frame']}): borderline, this excess is just above the {n['margin']} level that {n['pct']} % of no-event circles "
                  f"exceed, but below {n['strong']}; {n['km2']} km² lost more than {n['thr']} ({n['bkm2']} km² in the previous pair). This is "
                  f"not enough to say the surface changed, and no cause can be given.")
        else:
            s += (f"la perte de cohérence radar moyenne dans un rayon de 5 km est de {n['mean']}, contre {n['frame']} pour toute la "
                  f"scène : un excès de {n['exc']}, sous le niveau {n['margin']} que {n['pct']} % des cercles sans événement dépassent ; "
                  f"{n['km2']} km² ont perdu plus de {n['thr']} ({n['bkm2']} km² dans la paire précédente). Pas de changement local "
                  f"net." if fr else
                  f"the mean radar coherence loss within 5 km is {n['mean']}, against {n['frame']} for the whole frame: an excess of "
                  f"{n['exc']}, below the {n['margin']} level that {n['pct']} % of no-event circles exceed; {n['km2']} km² lost more "
                  f"than {n['thr']} ({n['bkm2']} km² in the previous pair). No clear local change.")
        s += (" La référence « sans événement » vient d'une seule géométrie de visée, d'une seule saison et de cercles placés au "
              "hasard dans la scène." if fr else
              " The no-event reference comes from one viewing geometry, one season and circles placed at random in the frame.")
        if f.get("baseline_unreliable"):
            s += (f" La paire « avant » est plus faible que d'habitude pour cette géométrie (cohérence {n['own']} contre {n['med']}) : "
                  f"la référence n'est pas fiable et la réponse n'est pas concluante." if fr else
                  f" The before pair is weaker than usual for this geometry (coherence {n['own']} against {n['med']}): the baseline "
                  f"is unreliable and this answer is not conclusive.")
        return s
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
        s = (f"Humidité du sol le {f['latest_date']} : {_n(f['latest_m3m3'],3)} m³/m³ "
             f"({'+' if f['anomaly_m3m3'] >= 0 else ''}{_n(f['anomaly_m3m3'],3)} par rapport à la moyenne de "
             f"{f['n_passes']} passages)." if fr else
             f"Soil moisture on {f['latest_date']}: {_n(f['latest_m3m3'],3)} m³/m³ "
             f"({'+' if f['anomaly_m3m3'] >= 0 else ''}{_n(f['anomaly_m3m3'],3)} vs the mean of {f['n_passes']} passes).")
        if f.get("within_uncertainty"):
            s += (f" Cet écart est dans l'incertitude du produit ({_n(f['uncertainty_m3m3'], 3)}) : il ne montre pas de "
                  f"changement réel." if fr else
                  f" This change is within the product's uncertainty ({_n(f['uncertainty_m3m3'], 3)}): it does not show a "
                  f"real change.")
        return s
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
    "slow_motion": "لا يكفي اتجاه بضعة أشهر لتحديد موعد انهيار؛ ولا يُعد حكمًا على سلامة سد؛ يبقى الفحص الميداني ضروريًا.",
    "surface_change": "يدل فقدان التماسك على أن السطح تغيّر، لا على السبب: ماء أو وحل أو انهيار أو أشغال أو نباتات. وهو ليس "
                      "قياسًا للأضرار ولا لعمق الفيضان أو مدته، والنافذة تمتد عدة أيام.",
    "flood": "يرى الرادار المياه لحظة المرور فقط، لا ذروة الفيضان بين مرورين.",
    "deforestation": "قد ينتج انخفاض إشارة HV أيضًا عن الحصاد أو حريق.",
    "soil_moisture": "قيمة متوسطة لبضعة سنتيمترات علوية من التربة على خلية بمئات الأمتار.",
    "large_displacement": "لا تكشف إزاحات البكسل عن تحركات ببضعة سنتيمترات.",
}

CANNOT_SAY = {
    "sudden_motion": {"fr": "Le radar mesure le mouvement le long de sa ligne de visée ; il ne dit pas ce qui va se passer ensuite.",
                      "en": "The radar measures motion along its line of sight; it cannot tell what will happen next."},
    "slow_motion": {"fr": "Une tendance sur quelques mois ne permet pas de dater une rupture et n'est pas un verdict sur la sûreté "
                          "d'un barrage ; une inspection sur place reste nécessaire.",
                    "en": "A trend over a few months cannot date a failure and is not a dam-safety verdict; an on-site "
                          "inspection is still needed."},
    "surface_change": {"fr": "Une perte de cohérence montre que la surface a changé, pas pourquoi : eau, boue, éboulement, travaux "
                             "ou végétation. Ce n'est ni une mesure de dégâts, ni de hauteur ou de durée d'inondation ; la fenêtre "
                             "dure plusieurs jours.",
                       "en": "Coherence loss shows that the surface changed, not why: water, mud, rock fall, earthworks or "
                             "vegetation. It is not a measure of damage, flood depth or flood duration, and the window lasts "
                             "several days."},
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
