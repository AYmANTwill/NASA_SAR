"""FR / EN / AR texts for the answer's no-data reason and step summaries, so that no English sentence from the agent
ends up inside the French or Arabic text (Adam's API_REQUESTS.md, request 4).

agent.py (Anass) still writes its reasons and step names in English. The known ones are mapped here to a template id
with params plus the three texts; an unknown one gets a generic FR / AR text and keeps its English only in `en`.
When agent.py returns reason codes itself, this table can go.
"""
from __future__ import annotations

import re

# (pattern on the English reason, code, fr, en, ar); {date} / {precision} come from the named groups
REASONS = [
    (r"^a sudden-event question needs the event", "need_event",
     "une question sur un événement soudain demande l'événement : nommez-le ou donnez sa date (AAAA-MM-JJ)",
     "a sudden-event question needs the event: name it or give its date (YYYY-MM-DD)",
     "يتطلب سؤال عن حدث مفاجئ تحديد الحدث: اذكره أو أعط تاريخه (YYYY-MM-DD)"),
    (r"^no NISAR pair straddles the event of (?P<date>\d{8}) \((?P<precision>\w+) precision\)", "no_pair_straddles",
     "aucune paire NISAR n'encadre l'événement du {date}", "no NISAR pair straddles the event of {date}",
     "لا يوجد زوج NISAR يحيط بحدث {date}"),
    (r"^the displacement could not be computed", "displacement_failed",
     "le déplacement n'a pas pu être calculé sur les paires qui encadrent l'événement",
     "the displacement could not be computed on the pairs that straddle the event",
     "تعذر حساب الإزاحة على الأزواج التي تحيط بالحدث"),
    (r"^no location", "no_location", "pas de lieu : cliquez sur la carte ou nommez un lieu connu",
     "no location: click on the map or name a known place", "لا يوجد موقع: انقر على الخريطة أو اذكر مكانا معروفا"),
    (r"^needs two GCOV acquisitions", "needs_two_gcov",
     "il faut deux acquisitions GCOV sur la même trace et le même cadre",
     "needs two GCOV acquisitions on the same track and frame", "يلزم التقاطان GCOV على نفس المسار والإطار"),
    (r"^deforestation needs the HV channel", "needs_hv", "la déforestation demande le canal HV",
     "deforestation needs the HV channel", "تتطلب إزالة الغابات القناة HV"),
    (r"^needs an earlier pair and a pair of the same length", "needs_baseline_pair",
     "il faut une paire antérieure et une paire de même durée sur la même trace, le même cadre et le même CRID",
     "needs an earlier pair and a pair of the same length on the same track, frame and CRID",
     "يلزم زوج سابق وزوج بنفس المدة على نفس المسار والإطار وCRID"),
    (r"^the before and event pairs do not share the same grid", "grid_mismatch",
     "la paire d'avant et celle de l'événement n'ont pas la même grille",
     "the before and event pairs do not share the same grid", "زوج ما قبل الحدث وزوج الحدث ليس لهما نفس الشبكة"),
    (r"^no GOFF product covers this point", "no_goff", "aucun produit GOFF ne couvre ce point",
     "no GOFF product covers this point", "لا يغطي أي منتج GOFF هذه النقطة"),
    (r"^no readable soil-moisture value", "no_soil_value", "aucune valeur d'humidité du sol lisible en ce point",
     "no readable soil-moisture value at this point", "لا توجد قيمة مقروءة لرطوبة التربة في هذه النقطة"),
]
UNKNOWN = ("other", "raison technique (détail dans la version anglaise)", None, "سبب تقني (التفاصيل في النسخة الإنجليزية)")

# step names: fixed ones, then patterns with params
STEPS_FIXED = {
    "FIRMS fires": ("Feux FIRMS", "FIRMS fires", "حرائق FIRMS"),
    "map of the latest pair": ("Carte de la dernière paire", "Map of the latest pair", "خريطة آخر زوج"),
    "NISAR soil moisture (SME2)": ("Humidité du sol NISAR (SME2)", "NISAR soil moisture (SME2)", "رطوبة التربة NISAR (SME2)"),
    "pixel offsets": ("Décalages de pixels", "Pixel offsets", "إزاحات البكسل"),
    "rain before the flood": ("Pluie avant la crue", "Rain before the flood", "الأمطار قبل الفيضان"),
    "rain in the 30 days before": ("Pluie des 30 jours précédents", "Rain in the 30 days before", "الأمطار في الثلاثين يوما السابقة"),
    "rain over the change window (context only)": ("Pluie sur la fenêtre du changement (contexte)",
                                                   "Rain over the change window (context only)",
                                                   "الأمطار خلال نافذة التغير (للسياق فقط)"),
    "rain over the period": ("Pluie sur la période", "Rain over the period", "الأمطار خلال الفترة"),
    "surface change (coherence loss)": ("Changement de surface (perte de cohérence)", "Surface change (coherence loss)",
                                        "تغير السطح (فقدان التماسك)"),
    "time series (small-baseline inversion)": ("Série temporelle (inversion à petites lignes de base)",
                                               "Time series (small-baseline inversion)",
                                               "سلسلة زمنية (انعكاس بخطوط أساس قصيرة)"),
    "USGS earthquakes (context only)": ("Séismes USGS (contexte)", "USGS earthquakes (context only)",
                                        "زلازل USGS (للسياق فقط)"),
    "USGS earthquakes between the passes": ("Séismes USGS entre les passages", "USGS earthquakes between the passes",
                                            "زلازل USGS بين المرورين"),
    "vertical / east-west split": ("Séparation verticale / est-ouest", "Vertical / east-west split",
                                   "الفصل العمودي / شرق-غرب"),
    "what is exposed (OpenStreetMap)": ("Ce qui est exposé (OpenStreetMap)", "What is exposed (OpenStreetMap)",
                                        "ما هو معرض (OpenStreetMap)"),
}
STEPS_PATTERN = [
    (r"^found (?P<count>\d+) interferograms covering the point", "found_products",
     "{count} interférogramme(s) couvrent le point", "{count} interferogram(s) cover the point",
     "{count} من التداخلات تغطي النقطة"),
    (r"^(?P<count>\d+) pair\(s\) straddle the event \((?P<date>\d{8})", "straddle",
     "{count} paire(s) encadrent l'événement du {date}", "{count} pair(s) straddle the event of {date}",
     "{count} من الأزواج تحيط بحدث {date}"),
    (r"^(?P<count>\d+) pair\(s\) rejected by the quality filter", "rejected",
     "{count} paire(s) écartée(s) par le filtre de qualité", "{count} pair(s) rejected by the quality filter",
     "{count} من الأزواج استبعدها مرشح الجودة"),
    (r"^no GCOV product covers the point", "no_gcov",
     "Aucun produit GCOV ne couvre le point : question traitée par la perte de cohérence",
     "No GCOV product covers the point: answered with coherence loss",
     "لا يغطي أي منتج GCOV النقطة: أجيب عن السؤال بفقدان التماسك"),
    (r"^displacement (?P<direction>ascending|descending) (?P<date>\d{8})\D(?P<date2>\d{8})", "displacement",
     "Déplacement {direction} {date} → {date2}", "Displacement {direction} {date} → {date2}",
     "الإزاحة {direction} {date} → {date2}"),
    (r"^backscatter change \((?P<qtype>\w+)\)", "backscatter", "Changement de rétrodiffusion",
     "Backscatter change", "تغير الانتثار الخلفي"),
]
DIRECTION = {"ascending": ("ascendant", "ascending", "صاعد"), "descending": ("descendant", "descending", "نازل")}


def _iso(d: str) -> str:
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def _params(m: re.Match) -> tuple[dict, dict]:
    """(template params, text values per language) from the named groups."""
    params, values = {}, {L: {} for L in ("fr", "en", "ar")}
    for k, v in m.groupdict().items():
        if v is None:
            continue
        if k.startswith("date"):
            params[k] = {"date": _iso(v)}
            for L in values:
                values[L][k] = _iso(v)
        elif k == "count":
            params[k] = int(v)
            for L in values:
                values[L][k] = v
        elif k == "direction":
            params[k] = {"term": f"direction.{v}"}
            for i, L in enumerate(("fr", "en", "ar")):
                values[L][k] = DIRECTION[v][i]
        else:
            params[k] = v
            for L in values:
                values[L][k] = v
    return params, values


def reason(text: str | None) -> tuple[str, dict, dict]:
    """(code, template params, {fr, en, ar}) for an English reason of the agent or a recipe."""
    text = (text or "").strip()
    for pattern, code, fr, en, ar in REASONS:
        m = re.match(pattern, text)
        if m:
            params, v = _params(m)
            return code, params, {"fr": fr.format(**v["fr"]), "en": en.format(**v["en"]), "ar": ar.format(**v["ar"])}
    code, fr, _, ar = UNKNOWN
    return code, {}, {"fr": fr, "en": text or "unknown reason", "ar": ar}


def no_data_verdict(qtype: str, error: str | None) -> dict:
    """TemplatedText of an answer without data: the reason in the reader's language, never English in FR / AR."""
    code, params, r = reason(error)
    return {"template": "backend.verdict.no_data", "params": {"reason": {"term": f"reason.{code}"}, **params},
            "text": {"fr": f"Aucune donnée NISAR téléchargée ne permet encore de répondre ici : {r['fr']}.",
                     "en": f"No NISAR data downloaded yet can answer this here: {r['en']}.",
                     "ar": f"لا توجد بعد بيانات NISAR محمّلة تسمح بالإجابة هنا: {r['ar']}."}}


def step_summary(name: str) -> dict:
    """TemplatedText of an agent step name."""
    name = (name or "").strip()
    if name in STEPS_FIXED:
        fr, en, ar = STEPS_FIXED[name]
        key = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        return {"template": f"backend.step.{key}", "params": {}, "text": {"fr": fr, "en": en, "ar": ar}}
    for pattern, code, fr, en, ar in STEPS_PATTERN:
        m = re.match(pattern, name)
        if m:
            params, v = _params(m)
            return {"template": f"backend.step.{code}", "params": params,
                    "text": {"fr": fr.format(**v["fr"]), "en": en.format(**v["en"]), "ar": ar.format(**v["ar"])}}
    return {"template": "backend.step.other", "params": {},
            "text": {"fr": "Étape de calcul", "en": name or "step", "ar": "خطوة حساب"}}


def step_error(error: str | None) -> dict:
    code, params, r = reason(error)
    return {"template": "backend.step.error", "params": {"reason": {"term": f"reason.{code}"}, **params},
            "text": r}
