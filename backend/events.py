"""Event library: questions answered in advance (fast and offline-safe for the demo)."""
from __future__ import annotations

import json

import agent
from config import CACHE_DIR

DIR = CACHE_DIR / "events"
DIR.mkdir(parents=True, exist_ok=True)

EVENTS = [
    {"id": "panama-2026", "title": "Séisme M7.7 du Panama, 9 octobre 2026", "lat": 7.59, "lon": -80.77,
     "question": "Où le sol a-t-il bougé après le séisme du 9 octobre 2026 au Panama ?", "date": "2026-10-09",
     "lang": "fr"},
    {"id": "venezuela-2026", "title": "Séismes du Venezuela, 24 juin 2026", "lat": 10.60, "lon": -66.93,
     "question": "Le sol a-t-il bougé après le séisme du 24 juin 2026 au Venezuela ?", "date": "2026-06-24",
     "lang": "fr"},
    {"id": "al-wahda", "title": "Barrage Al Wahda", "lat": 34.64, "lon": -5.17,
     "question": "Le barrage Al Wahda se déforme-t-il depuis juin ?", "date": None, "lang": "fr"},
    {"id": "ben-guerir-mine", "title": "Mine de phosphate de Ben Guerir", "lat": 32.27, "lon": -7.93,
     "question": "Le terrain de la mine de Ben Guerir bouge-t-il ?", "date": None, "lang": "fr"},
    {"id": "gharb-soil", "title": "Humidité du sol, plaine du Gharb", "lat": 34.50, "lon": -6.00,
     "question": "Quelle est l'humidité du sol dans le Gharb ?", "date": None, "lang": "fr"},
]


def compute(ev: dict) -> dict:
    res = agent.investigate(ev["question"], ev["lat"], ev["lon"], ev["lang"], ev.get("date"))
    res["event"] = {k: ev[k] for k in ("id", "title")}
    (DIR / f"{ev['id']}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return res


def get(eid: str, refresh: bool = False) -> dict | None:
    ev = next((e for e in EVENTS if e["id"] == eid), None)
    if not ev:
        return None
    f = DIR / f"{eid}.json"
    if f.exists() and not refresh:
        return json.loads(f.read_text(encoding="utf-8"))
    return compute(ev)


def listing() -> list[dict]:
    out = []
    for e in EVENTS:
        f = DIR / f"{e['id']}.json"
        r = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
        out.append({"id": e["id"], "title": e["title"], "lat": e["lat"], "lon": e["lon"],
                    "computed": r is not None, "verdict": r.get("verdict") if r else None,
                    "confidence": r.get("confidence") if r else None,
                    "alert_level": r.get("alert_level") if r else None})
    return out
