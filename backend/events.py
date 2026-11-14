"""Event library: questions answered in advance (fast and offline-safe for the demo)."""
from __future__ import annotations

import json

import agent
from config import CACHE_DIR

DIR = CACHE_DIR / "events"
DIR.mkdir(parents=True, exist_ok=True)

# The Moroccan demo library (docs/claude/MOROCCO_PLAN.md §5, sites and frames: docs/claude/morocco_inventory.md).
# Al Haouz is represented by Asni (covered by frames 44/17 ascending and 23/73 descending).
EVENTS = [
    {"id": "haouz-flood-2026-10-10", "title": "Crue éclair d'Al Haouz, 10 octobre 2026 (Asni)",
     "title_en": "Al Haouz flash flood, 10 October 2026 (Asni)", "title_ar": "سيول الحوز، 10 أكتوبر 2026 (أسني)",
     "lat": 31.250, "lon": -7.983, "date": "2026-10-10", "lang": "fr",
     "question": "Le sol a-t-il changé à Asni lors de la crue éclair du 10 octobre 2026 ?"},
    {"id": "haouz-soil-moisture", "title": "Humidité du sol à Asni (Al Haouz)",
     "title_en": "Soil moisture at Asni (Al Haouz)", "title_ar": "رطوبة التربة في أسني (الحوز)",
     "lat": 31.250, "lon": -7.983, "date": None, "lang": "fr",
     "question": "Quelle est l'humidité du sol à Asni ?"},
    {"id": "gharb-soil-moisture", "title": "Humidité du sol, plaine du Gharb",
     "title_en": "Soil moisture, Gharb plain", "title_ar": "رطوبة التربة في سهل الغرب",
     "lat": 34.50, "lon": -6.00, "date": None, "lang": "fr",
     "question": "Quelle est l'humidité du sol dans le Gharb ?"},
    {"id": "ben-guerir-mine", "title": "Mine de phosphate de Ben Guerir (non validé : pas de polygone)",
     "title_en": "Ben Guerir phosphate mine (not validated: no polygon)",
     "title_ar": "منجم الفوسفاط بابن جرير (غير مؤكد: دون مضلع)",
     "status": "not validated",
     "status_note": "The point is the mine centroid. No quarry polygon was checked, so the answer is not validated.",
     "lat": 32.25825, "lon": -7.82355, "date": None, "lang": "fr",
     "question": "Où la surface de la mine de Ben Guerir a-t-elle changé ?"},
    {"id": "al-wahda-surroundings", "title": "Alentours du barrage Al Wahda",
     "title_en": "Surroundings of the Al Wahda dam", "title_ar": "محيط سد الوحدة",
     "lat": 34.598, "lon": -5.198, "date": None, "lang": "fr",
     "question": "Le terrain autour du barrage Al Wahda bouge-t-il ?"},
]

# VALIDATION events: outside the Morocco scope, used to check the method on a large, unambiguous signal. Never part of
# the Moroccan demo; listed only with /events?include_validation=true. Panama is our sign check (STATUS H4).
# No "date": the question names the event, so the exact USGS origin time is used (a whole-day window would make the
# descending pairs acquired at 23:53 UTC that day "ambiguous" and drop them).
VALIDATION_EVENTS = [
    {"id": "panama-2026", "kind": "validation", "scope": "global validation, outside the Morocco scope",
     "title": "Validation (hors Maroc) : séisme M7.7 du Panama, 9 octobre 2026",
     "title_en": "Validation (outside Morocco): Panama M7.7 earthquake, 9 October 2026",
     "title_ar": "تحقق (خارج المغرب): زلزال بنما بقوة 7.7، 9 أكتوبر 2026",
     "status": "validation",
     "status_note": "Global validation event, outside the Morocco scope: the only large, unambiguous NISAR signal we "
                    "have, used to check the line-of-sight sign. Not a Moroccan answer.",
     "usgs_id": "us6000u18k", "magnitude": 7.7, "origin_utc": "2026-10-09T17:56:06Z",
     "usgs_url": "https://earthquake.usgs.gov/earthquakes/eventpage/us6000u18k",
     "lat": 7.59, "lon": -80.77, "date": None, "lang": "fr",
     "question": "Où le sol a-t-il bougé après le séisme du Panama ?"},
]

# Synthetic test fixture (Venezuela): resolvable by id for the tests, never listed or precomputed.
FIXTURES = [
    {"id": "venezuela-2026", "title": "Séismes du Venezuela, 24 juin 2026", "lat": 10.60, "lon": -66.93,
     "question": "Le sol a-t-il bougé après le séisme du 24 juin 2026 au Venezuela ?", "date": "2026-06-24",
     "lang": "fr"},
]
VALIDATION_KEYS = ("kind", "scope", "usgs_id", "magnitude", "origin_utc", "usgs_url")


def compute(ev: dict) -> dict:
    res = agent.investigate(ev["question"], ev["lat"], ev["lon"], ev["lang"], ev.get("date"))
    res["event"] = {k: ev[k] for k in ("id", "title")}
    res["status"] = ev.get("status", "ready")
    res["kind"] = ev.get("kind", "morocco")
    for k in VALIDATION_KEYS[1:]:
        if ev.get(k) is not None:
            res["event"][k] = ev[k]
    if ev.get("status_note"):
        res["status_note"] = ev["status_note"]
    (DIR / f"{ev['id']}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return res


def get(eid: str, refresh: bool = False) -> dict | None:
    ev = next((e for e in EVENTS + VALIDATION_EVENTS + FIXTURES if e["id"] == eid), None)
    if not ev:
        return None
    f = DIR / f"{eid}.json"
    if f.exists() and not refresh:
        return json.loads(f.read_text(encoding="utf-8"))
    return compute(ev)


def listing(include_validation: bool = False) -> list[dict]:
    """The Moroccan library; with include_validation, the validation events (outside Morocco) come after it."""
    out = []
    for e in EVENTS + (VALIDATION_EVENTS if include_validation else []):
        f = DIR / f"{e['id']}.json"
        r = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
        out.append({"id": e["id"], "title": e["title"], "title_en": e.get("title_en"), "title_ar": e.get("title_ar"),
                    "lat": e["lat"], "lon": e["lon"], "status": e.get("status", "ready"),
                    "status_note": e.get("status_note"), "kind": e.get("kind", "morocco"),
                    "computed": r is not None, "verdict": r.get("verdict") if r else None,
                    "confidence": r.get("confidence") if r else None,
                    "alert_level": r.get("alert_level") if r else None})
    return out
