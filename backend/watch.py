"""'Watch this place': saved questions re-run at every new NISAR pass, with alerts on level change."""
from __future__ import annotations

import json
import time
import uuid
from datetime import date, timedelta

import requests

import agent
import catalog
from config import CACHE_DIR, OFFLINE

STORE = CACHE_DIR / "watches.json"
SEARCH_URL = "https://api.daac.asf.alaska.edu/services/search/param"
REPEAT_DAYS = 12
LEVELS = ["none", "yellow", "orange", "red"]
LEVEL_WORDS = {"fr": {"none": "aucune", "yellow": "jaune", "orange": "orange", "red": "rouge"},
               "en": {"none": "none", "yellow": "yellow", "orange": "orange", "red": "red"},
               "ar": {"none": "لا شيء", "yellow": "أصفر", "orange": "برتقالي", "red": "أحمر"}}


def _load() -> list[dict]:
    return json.loads(STORE.read_text(encoding="utf-8")) if STORE.exists() else []


def _save(ws):
    STORE.write_text(json.dumps(ws, indent=1, ensure_ascii=False), encoding="utf-8")


def next_passes(lat, lon) -> list[dict]:
    """Next expected pass per geometry = last acquisition seen + 12 days (repeated until in the future)."""
    last = {}
    for p in catalog.load():
        if p.covers(lat, lon):
            last[(p.track, p.frame, p.direction)] = max(last.get((p.track, p.frame, p.direction), ""), p.sec[:8])
    today = date.today()
    out = []
    for (t, f, d), s in last.items():
        nxt = date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        while nxt <= today:
            nxt += timedelta(days=REPEAT_DAYS)
        out.append({"track": t, "frame": f, "direction": d, "next_pass": nxt.isoformat()})
    return sorted(out, key=lambda x: x["next_pass"])


def notification(w, old, new, lang):
    words = LEVEL_WORDS.get(lang, LEVEL_WORDS["fr"])
    if lang == "ar":
        return f"تنبيه NISAR Pulse: تغير المستوى من {words[old]} إلى {words[new]}. {w['last_verdict']}"
    if lang == "en":
        return f"NISAR Pulse alert: level changed from {words[old]} to {words[new]}. {w['last_verdict']}"
    return f"Alerte NISAR Pulse : le niveau passe de {words[old]} à {words[new]}. {w['last_verdict']}"


def add(lat, lon, question, lang="fr", label=None) -> dict:
    res = agent.investigate(question, lat, lon, lang)
    w = {"id": uuid.uuid4().hex[:8], "lat": lat, "lon": lon, "question": question, "lang": lang,
         "label": label, "created": time.strftime("%Y-%m-%d %H:%M"),
         "level": res.get("alert_level", "none"), "last_verdict": res.get("verdict"),
         "last_checked": time.strftime("%Y-%m-%d %H:%M"), "seen_products": res.get("data_used", []),
         "next_passes": next_passes(lat, lon), "notifications": []}
    ws = _load()
    ws.append(w)
    _save(ws)
    return w


def remove(wid) -> bool:
    ws = _load()
    keep = [w for w in ws if w["id"] != wid]
    _save(keep)
    return len(keep) < len(ws)


def new_granules_on_asf(lat, lon, since: str) -> list[str]:
    """Granules published on ASF after `since` (YYYY-MM-DD) that cover the point."""
    if OFFLINE:
        return []
    try:
        r = requests.get(SEARCH_URL, timeout=60, params=dict(platform="NISAR", processingLevel="GUNW",
                         intersectsWith=f"POINT({lon} {lat})", start=since, output="geojson", maxResults=200))
        r.raise_for_status()
        return [f["properties"].get("fileID") or f["properties"].get("sceneName") for f in r.json()["features"]]
    except Exception:
        return []


def check_all() -> list[dict]:
    """Re-run every watch. Call it daily (cron / Windows Task Scheduler) or from POST /watch/check."""
    catalog.refresh()
    ws, events = _load(), []
    for w in ws:
        since = (date.today() - timedelta(days=30)).isoformat()
        on_asf = new_granules_on_asf(w["lat"], w["lon"], since)
        res = agent.investigate(w["question"], w["lat"], w["lon"], w["lang"])
        used = set(res.get("data_used", []))
        new_local = sorted(used - set(w["seen_products"]))
        old, new = w["level"], res.get("alert_level", "none")
        w.update(last_checked=time.strftime("%Y-%m-%d %H:%M"), last_verdict=res.get("verdict"),
                 seen_products=sorted(used), next_passes=next_passes(w["lat"], w["lon"]),
                 asf_recent=len(on_asf))
        if new != old:
            msg = notification(w, old, new, w["lang"])
            w["notifications"].append({"at": w["last_checked"], "from": old, "to": new, "message": msg})
            w["level"] = new
            events.append({"watch": w["id"], "message": msg, "level": new})
        w["new_products_since_last_check"] = new_local
    _save(ws)
    return events


def all_watches() -> list[dict]:
    return _load()
