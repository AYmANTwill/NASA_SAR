"""Adapter for the frontend (houssam-bough/nasa-the-sar-front-end), mounted under /api.

The frontend validates every response against its own zod contract (src/api/contract.ts) and rejects
anything that does not match. This module translates the agent's answers into that contract WITHOUT
changing any analysis rule: numbers, confidence and alert levels come from the backend unchanged.
Prose is sent as TemplatedText: a frontend template when one fits, otherwise a backend template id with
the text in French, English and Arabic as fallback (the frontend shows the fallback for unknown ids).

The original endpoints (/ask, /events, ...) are untouched."""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

import agent
import catalog
import discoveries
import events
import watch
from config import CACHE_DIR, LOS_SIGN
from science import case_store

router = APIRouter(prefix="/api")
STORE = CACHE_DIR / "answers_v2"
STORE.mkdir(parents=True, exist_ok=True)
WATCHES = CACHE_DIR / "watches_v2.json"
NOTES = CACHE_DIR / "notifications_v2.json"
_lock = threading.Lock()
LANGS = ("fr", "en", "ar")

# The frontend's Recipe enum has no "surface_change": Anass renamed "damage" to "surface_change" on purpose.
# Until the frontend adds it, surface change is shown under the "damage" recipe (ask Houssam to add it).
RECIPE = {"surface_change": "damage", "sudden_motion": "sudden_motion", "slow_motion": "slow_motion",
          "flood": "flood", "deforestation": "deforestation", "soil_moisture": "soil_moisture",
          "large_displacement": "large_displacement", "damage": "damage"}
PRODUCT = {"soil_moisture": "SME2", "flood": "GCOV", "deforestation": "GCOV", "large_displacement": "GOFF"}
EVIDENCE_SOURCE = {"USGS": "usgs", "Open-Meteo": "open_meteo", "FIRMS": "firms", "OpenStreetMap": "osm"}
AGREEMENT = {"agrees": "agrees", "disagrees": "disagrees", "none": "inconclusive", "context": "inconclusive",
             "unavailable": "unavailable"}


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def iso(d) -> str | None:
    """'20261009' / '20261009T175606' / '2026-10-09' -> '2026-10-09'."""
    if not d:
        return None
    s = str(d).replace("-", "")[:8]
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 and s.isdigit() else None


def tt(template: str, params: dict | None = None, fr: str | None = None, en: str | None = None,
       ar: str | None = None) -> dict:
    """TemplatedText. Frontend templates take params; backend.* ids carry the text in 3 languages."""
    out = {"template": template, "params": params or {}}
    text = {k: v for k, v in (("fr", fr), ("en", en), ("ar", ar)) if v}
    if text:
        out["text"] = text
    return out


def same3(template: str, s: str) -> dict:
    return tt(template, {}, s, s, s)


def meas(value, uncertainty, unit: str, sigma: float = 1) -> dict | None:
    try:
        v = float(value)
        u = abs(float(uncertainty)) if uncertainty is not None else 0.0
    except (TypeError, ValueError):
        return None
    if v != v or u != u:              # NaN
        return None
    return {"value": round(v, 6), "uncertainty": round(u, 6), "unit": unit, "sigma": sigma}


def _fid(products_ids):
    return [p for p in (catalog.by_id(i) for i in products_ids) if p]


def api_error(code: str, status: int, fr: str, en: str, ar: str) -> JSONResponse:
    return JSONResponse({"code": code, "message": tt(f"backend.error.{code}", {}, fr, en, ar)}, status_code=status)


# ---------------------------------------------------------------------------
# building an Answer from the agent's response
# ---------------------------------------------------------------------------
def _verdicts(qtype: str, facts: dict, ok: bool) -> dict:
    out = {}
    for L in LANGS:
        try:
            out[L] = agent.template(qtype, facts, L) if ok else agent.no_data_sentence(qtype, L, facts)
        except Exception:
            out[L] = None
    return out


def _stable(qtype: str, f: dict) -> bool:
    if qtype == "sudden_motion":
        v, n = f.get("value_cm"), f.get("noise_cm")
        return v is None or (n is not None and abs(v) < 3 * n)
    if qtype == "slow_motion":
        v, s = f.get("velocity_mm_yr"), f.get("velocity_sigma")
        if v is not None and s:
            return abs(v) < 3 * s
        t, n = f.get("total_mm"), f.get("noise_mm")
        return t is None or (n is not None and abs(t) < 3 * n)
    if qtype == "surface_change":
        return f.get("excess_level") in (None, "none")
    if qtype == "soil_moisture":
        return bool(f.get("within_uncertainty"))
    return False


def _metrics(qtype: str, f: dict) -> list[dict]:
    m = []
    add = lambda mid, x: m.append({"id": mid, "measurement": x}) if x else None
    if qtype == "sudden_motion":
        add("los_displacement_max", meas(f.get("value_cm"), f.get("noise_cm"), "cm"))
        dec = f.get("decomposition_cm") or {}
        if dec:
            u = (f.get("noise_cm") or 0) * 1.5      # propagated through the 2x2 asc/desc system (approximate)
            add("vertical_displacement", meas(dec.get("up"), u, "cm"))
            add("east_west_displacement", meas(dec.get("east"), u, "cm"))
        add("noise_floor", meas(f.get("noise_cm"), 0, "cm"))
    elif qtype == "slow_motion":
        if f.get("velocity_mm_yr") is not None:
            add("velocity", meas(f["velocity_mm_yr"], f.get("velocity_sigma") or 0, "mm/yr"))
            dec = f.get("decomposition_mm_yr") or {}
            if dec:
                u = (f.get("velocity_sigma") or 0) * 1.5
                add("vertical_velocity", meas(dec.get("up"), u, "mm/yr"))
                add("east_west_velocity", meas(dec.get("east"), u, "mm/yr"))
            if f.get("acceleration") is not None:
                add("acceleration", meas(f["acceleration"], f.get("acceleration_sigma") or 0, "mm/yr2"))
        else:                                       # under 12 months: cumulative change only, never a rate
            add("los_displacement_max", meas(f.get("total_mm"), f.get("noise_mm"), "mm"))
        add("noise_floor", meas(f.get("noise_mm"), 0, "mm"))
    elif qtype == "surface_change":
        rng = f.get("changed_km2_range") or []
        u = (rng[1] - rng[0]) / 2 if len(rng) == 2 and None not in rng else 0
        add("coherence_loss_area", meas(f.get("changed_km2_5km"), u, "km2"))
    elif qtype == "soil_moisture":
        add("soil_moisture", meas(f.get("latest_m3m3"), f.get("uncertainty_m3m3"), "m3/m3"))
        add("soil_moisture_anomaly", meas(f.get("anomaly_m3m3"), f.get("uncertainty_m3m3"), "m3/m3"))
    elif qtype == "flood":
        area = (f.get("open_water_ha") or 0) + (f.get("flooded_vegetation_ha") or 0)
        add("flooded_area", meas(area, 0.2 * area, "ha"))           # +-20 %: classification heuristic
    elif qtype == "deforestation":
        a = f.get("vegetation_loss_ha")
        add("forest_loss", meas(a, 0.2 * (a or 0), "ha"))
    elif qtype == "large_displacement":
        add("offset_max", meas(f.get("magnitude_m"), 0.1, "m"))
    return m


def _series(qtype: str, f: dict) -> list[dict]:
    out = []
    if qtype == "slow_motion" and f.get("series"):
        s = f["series"][0]
        n = s.get("noise_mm") or f.get("noise_mm") or 0
        pts = [{"date": iso(p["date"]), "value": p["los_mm"], "lo": p["los_mm"] - n, "hi": p["los_mm"] + n}
               for p in s.get("series", []) if p.get("los_mm") is not None and iso(p.get("date"))]
        if pts:
            out.append({"id": "los", "unit": "mm", "points": pts, "sigma": 1, "noise_floor": n})
    if qtype == "soil_moisture" and f.get("series"):
        u = f.get("uncertainty_m3m3") or 0
        pts = [{"date": iso(p["date"]), "value": p["value"], "lo": p["value"] - u, "hi": p["value"] + u}
               for p in f["series"] if p.get("value") is not None and iso(p.get("date"))]
        if pts:
            out.append({"id": "soil_moisture", "unit": "m3/m3", "points": pts, "sigma": 1, "noise_floor": u})
    return out


def _checks(qtype: str, f: dict) -> list[dict]:
    phase = qtype in ("sudden_motion", "slow_motion")
    na = lambda cid: {"id": cid, "status": "not_applicable", "measurement": None, "detail": None}
    checks = []
    # noise floor
    noise = f.get("noise_cm") if qtype == "sudden_motion" else f.get("noise_mm") if qtype == "slow_motion" else None
    unit = "cm" if qtype == "sudden_motion" else "mm"
    if phase and noise is not None:
        x = meas(noise, 0, unit)
        checks.append({"id": "noise_floor", "status": "pass", "measurement": x,
                       "detail": tt("check.noise_floor", {"noise": x})})
    elif qtype == "soil_moisture" and f.get("uncertainty_m3m3") is not None:
        x = meas(f["uncertainty_m3m3"], 0, "m3/m3")
        checks.append({"id": "noise_floor", "status": "warn" if f.get("within_uncertainty") else "pass",
                       "measurement": x, "detail": tt("check.noise_floor", {"noise": x})})
    else:
        checks.append(na("noise_floor"))
    # coherence mask
    masked = f.get("masked") if qtype == "sudden_motion" else (1 - f["coverage_5km"]) if f.get("coverage_5km") is not None else None
    if masked is not None:
        pct = meas(100 * masked, 0, "percent")
        checks.append({"id": "coherence_mask", "status": "pass" if masked < 0.3 else "warn" if masked < 0.6 else "fail",
                       "measurement": pct, "detail": tt("check.coherence_mask", {"fraction": pct, "threshold": 0.3})})
    else:
        checks.append(na("coherence_mask"))
    # ionosphere
    if phase:
        state = str(f.get("iono_screen") or "")
        applied = bool(f.get("iono_applied")) or ("applied" in state and "not applied" not in state) or "subtract" in state
        if applied:
            checks.append({"id": "ionosphere", "status": "pass", "measurement": None, "detail": tt("check.ionosphere.applied")})
        else:
            checks.append({"id": "ionosphere", "status": "warn", "measurement": None, "detail": tt(
                "backend.check.ionosphere.not_applied", {},
                f"Écran ionosphérique non appliqué ({state or 'inconnu'}).",
                f"Ionospheric screen not applied ({state or 'unknown'}).",
                f"لم تُطبَّق شاشة الأيونوسفير ({state or 'غير معروف'}).")})
    else:
        checks.append(na("ionosphere"))
    # unwrapping
    same = f.get("reference_same_component")
    if phase and same is not None:
        checks.append({"id": "unwrapping", "status": "pass" if same else "warn", "measurement": None,
                       "detail": tt("check.unwrapping.ok") if same else tt(
                           "backend.check.unwrapping.other_component", {},
                           "La zone de référence est dans une autre composante connexe : saut de phase possible.",
                           "The reference area is in another connected component: a phase jump is possible.",
                           "منطقة المرجع في مكوّن متصل آخر: قفزة طور محتملة.")})
    else:
        checks.append(na("unwrapping"))
    return checks


def _evidence(ev_list: list[dict]) -> tuple[list[dict], list[dict]]:
    out, quakes = [], []
    for e in ev_list or []:
        src = EVIDENCE_SOURCE.get(e.get("source"))
        if not src:
            continue
        status = AGREEMENT.get(e.get("status"), "inconclusive")
        summary = e.get("summary") or ""
        url = None
        if status == "unavailable":
            s = tt("backend.evidence.unavailable", {}, f"Source indisponible : {summary}",
                   f"Source unavailable: {summary}", f"المصدر غير متاح: {summary}")
        elif src == "usgs":
            items = e.get("items") or []
            if items:
                top = items[0]
                s = tt("evidence.usgs.mainshock", {"mag": top["magnitude"],
                                                   "date": {"date": datetime.fromtimestamp(top["time_ms"] / 1000, timezone.utc).date().isoformat()},
                                                   "count": max(len(items) - 1, 0)})
                url = top.get("url")
                for i, q in enumerate(items):
                    quakes.append({"id": (q.get("url") or f"usgs-{i}").rstrip("/").split("/")[-1], "lat": q["lat"],
                                   "lon": q["lon"], "depth_km": q.get("depth_km"),
                                   "magnitude": {"value": q["magnitude"], "uncertainty": None, "type": "M"},
                                   "time": datetime.fromtimestamp(q["time_ms"] / 1000, timezone.utc).replace(microsecond=0).isoformat(),
                                   "role": "mainshock" if i == 0 else "aftershock", "url": q.get("url")})
            else:
                s = tt("evidence.usgs.none", {"radius": 150})
        elif src == "open_meteo" and e.get("total_mm") is not None:
            s = tt("evidence.open_meteo.rain", {"rain": meas(e["total_mm"], 0, "mm"), "days": len(e.get("items") or [])})
        else:
            s = same3(f"backend.evidence.{src}", summary)
        out.append({"source": src, "agreement": status, "summary": s, "url": url, "retrieved_at": now_iso()})
    return out, quakes


LAYER_KIND = [("disp_", "displacement", "cm", "diverging_displacement"),
              ("sc_", "coherence_loss", "coherence", "sequential_coherence_loss"),
              ("dpm_", "coherence_loss", "coherence", "sequential_coherence_loss"),
              ("sm_", "soil_moisture", "m3/m3", "sequential_moisture"),
              ("flood_", "backscatter_change", "dB", "diverging_displacement"),
              ("defor_", "backscatter_change", "dB", "diverging_displacement"),
              ("offset_", "offset", "m", "sequential_coherence"),
              ("classes_", "backscatter_change", "dB", "sequential_coherence")]


def _layers(layers: list[dict], period: dict | None) -> list[dict]:
    out = []
    for lay in layers or []:
        if not lay or not lay.get("url"):
            continue
        name = lay["url"].split("/")[-1]
        kind, unit, pal = next(((k, u, p) for pre, k, u, p in LAYER_KIND if name.startswith(pre)),
                               ("displacement", "cm", "diverging_displacement"))
        (s, w), (n, e) = lay["bounds"]
        lo, hi = float(lay.get("vmin", 0)), float(lay.get("vmax", 1))
        if pal == "diverging_displacement":
            hi = max(abs(lo), abs(hi))
            lo = -hi
        out.append({"id": name.rsplit(".", 1)[0], "kind": kind, "url": "/api" + lay["url"], "bounds": [w, s, e, n],
                    "unit": unit, "min": lo, "max": hi, "palette": pal,
                    "sign_convention": ("positive_toward_satellite" if LOS_SIGN > 0 else "positive_away_from_satellite")
                    if kind == "displacement" else None,
                    "period": period, "source": lay.get("title") or "NISAR"})
    return out


def _limits(qtype: str, f: dict, tracks: list[dict]) -> list[dict]:
    lim = []
    cs = {L: agent.cannot_say(qtype, L) if qtype in agent.CANNOT_SAY else None for L in LANGS}
    if any(cs.values()):
        lim.append(tt(f"backend.limit.{qtype}", {}, cs["fr"], cs["en"], cs["ar"]))
    if qtype in ("sudden_motion", "slow_motion"):
        if not f.get("sign_verified"):
            lim.append(tt("backend.limit.sign_unverified", {},
                          "Sens du mouvement non vérifié sur données réelles : le signe suit la convention documentée "
                          "(ARIA-tools, MintPy), sans contrôle indépendant.",
                          "Direction of motion not yet verified on real data: the sign follows the documented "
                          "convention (ARIA-tools, MintPy), without an independent check.",
                          "اتجاه الحركة غير متحقَّق منه على بيانات حقيقية: الإشارة تتبع الاصطلاح الموثّق "
                          "(ARIA-tools وMintPy) دون تحقق مستقل."))
        dirs = {t["direction"] for t in tracks}
        lim.append(tt("limit.north_south") if len(dirs) > 1 else tt("limit.los_only"))
        lim.append(tt("limit.no_prediction"))
    if qtype == "slow_motion" and f.get("first_date"):
        lim.append(tt("limit.short_history", {"since": {"date": iso(f["first_date"])}}))
    if qtype == "soil_moisture":
        lim.append(tt("limit.soil_depth"))
    if not lim:
        lim.append(tt("limit.no_prediction"))
    return lim


def _steps(raw_steps: list[dict], recipe: str, n_used: int, period: dict | None) -> list[dict]:
    out, t0 = [], datetime.now(timezone.utc)
    for i, s in enumerate(raw_steps or [], 1):
        name = s.get("step", "")
        low = name.lower()
        if low.startswith("question type"):
            kind, tool, summ = "classify", "agent.classify", tt("step.classify", {"recipe": {"term": f"recipe.{recipe}"}})
        elif low.startswith("found") or "straddle" in low or "interferogram" in low and "found" in low:
            m = re.search(r"found (\d+)", low)
            count = int(m.group(1)) if m else n_used
            params = {"count": count}
            if period:
                params.update(start={"date": period["start"]}, end={"date": period["end"]})
                summ = tt("step.search_scenes", params)
            else:
                summ = same3("backend.step", name)
            kind, tool = "search_scenes", "catalog.find"
        elif any(k in low for k in ("usgs", "rain", "firms", "openstreetmap", "exposed")):
            kind, tool, summ = "cross_evidence", "evidence", same3("backend.step", name)
        elif "rejected" in low or "quality" in low:
            kind, tool, summ = "uncertainty_checks", "quality.split", same3("backend.step", name)
        elif "no gcov" in low:
            kind, tool, summ = "select_recipe", "agent.route", same3("backend.step", name)
        elif "vertical / east-west" in low:
            kind, tool, summ = "compute", "decompose.combine", tt("step.compute.decompose")
        else:
            kind, tool, summ = "compute", f"recipe.{recipe}", same3("backend.step", name)
        ok = s.get("ok", True)
        out.append({"id": f"s{i}", "kind": kind, "tool": tool, "status": "done" if ok else "failed", "params": {},
                    "started_at": (t0 + timedelta(milliseconds=i)).replace(microsecond=0).isoformat(),
                    "duration_ms": s.get("ms", 0), "summary": summ,
                    "error": None if ok else same3("backend.step.error", s.get("error") or "failed")})
    out.append({"id": f"s{len(out) + 1}", "kind": "verdict", "tool": "agent.template", "status": "done", "params": {},
                "started_at": now_iso(), "duration_ms": 0, "summary": tt("step.verdict"), "error": None})
    return out


def answer_id(question: str, lat, lon, lang: str, date_: str | None) -> str:
    return "a-" + hashlib.md5(f"{question}|{lat}|{lon}|{lang}|{date_}".encode()).hexdigest()[:12]


def to_answer(resp: dict, aid: str, question: str, lang: str, name_i18n: dict | None = None,
              cached: bool = False) -> dict:
    qtype = resp.get("type")
    f = resp.get("facts") or {}
    ok = bool(f) and "error" not in f
    recipe = RECIPE.get(qtype, "slow_motion")
    used = _fid(resp.get("data_used") or [])
    tracks, seen = [], set()
    for p in used:
        if (p.track, p.frame) not in seen:
            seen.add((p.track, p.frame))
            tracks.append({"number": p.track, "direction": p.direction, "frame": p.frame})
    acq = sorted({d for p in used for d in (iso(p.ref), iso(p.sec)) if d})
    period = {"start": acq[0], "end": acq[-1]} if acq else {"start": date.today().isoformat(), "end": date.today().isoformat()}
    place = resp.get("place") or {}
    v = _verdicts(qtype, f, ok)
    ev, quakes = _evidence(resp.get("evidence"))
    passes = watch.next_passes(place.get("lat"), place.get("lon")) if place.get("lat") is not None else []
    product = PRODUCT.get(qtype, "GUNW")
    level = resp.get("alert_level")
    return {
        "id": aid, "created_at": now_iso(), "question": question, "lang": lang if lang in LANGS else "fr",
        "location": {"lat": place.get("lat"), "lon": place.get("lon"), "name": place.get("name"),
                     **({"name_i18n": name_i18n} if name_i18n else {}), "bbox": None},
        "recipe": recipe, "product": product,
        "product_status": "validated" if f.get("maturity") == "validated" else "provisional",
        "period": period, "acquisitions": acq, "tracks": tracks,
        "verdict": tt(f"backend.verdict.{qtype}", {}, v.get("fr") or resp.get("verdict"), v.get("en") or resp.get("verdict"),
                      v.get("ar") or resp.get("verdict")),
        "confidence": resp.get("confidence", "low"), "stable_in_noise": _stable(qtype, f) if ok else False,
        "metrics": _metrics(qtype, f) if ok else [], "series": _series(qtype, f) if ok else [],
        "checks": _checks(qtype, f) if ok else [], "evidence": ev,
        "layers": _layers(resp.get("layers"), period), "earthquakes": quakes,
        "limits": _limits(qtype, f, tracks),
        "indication": None, "classifier": None,
        "next_pass": passes[0]["next_pass"] if passes else None, "cached": cached,
        "steps": _steps(resp.get("steps"), recipe, len(used), period if acq else None),
        # Not in the frontend contract (zod strips unknown keys): kept for the watch feature.
        "x_alert_level": None if level in (None, "none") else level,
    }


def save(ans: dict) -> dict:
    (STORE / f"{ans['id']}.json").write_text(json.dumps(ans, ensure_ascii=False), encoding="utf-8")
    return ans


def load(aid: str) -> dict | None:
    f = STORE / f"{aid}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


# ---------------------------------------------------------------------------
# /api/ask  (Server-Sent Events)
# ---------------------------------------------------------------------------
def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/ask")
async def ask(request: Request):
    body = await request.json()
    question = (body.get("question") or "").strip()
    lang = body.get("lang") if body.get("lang") in LANGS else "fr"
    loc = body.get("location") or {}
    lat, lon = loc.get("lat"), loc.get("lon")

    def gen():
        first = {"id": "s0", "kind": "classify", "tool": "agent.classify", "status": "running", "params": {},
                 "started_at": now_iso(), "duration_ms": None, "summary": None, "error": None}
        yield sse("step", first)
        try:
            aid = answer_id(question, lat, lon, lang, None)
            cached = load(aid)
            if cached:
                yield sse("step", {**first, "status": "done", "duration_ms": 0,
                                   "summary": tt("step.cache")})
                yield sse("answer", {**cached, "cached": True})
                return
            resp = agent.investigate(question, lat, lon, lang)
            if resp.get("type") == "unknown":
                yield sse("error", {"code": "unclear_question", "message": tt(
                    "backend.error.unclear_question", {}, agent.UNCLEAR.get("fr"), agent.UNCLEAR.get("en"),
                    agent.UNCLEAR.get("ar"))})
                return
            if "error" in resp and "verdict" not in resp:
                yield sse("error", {"code": "no_location", "message": tt(
                    "backend.error.no_location", {},
                    "Aucun lieu : cliquez sur la carte ou nommez un lieu connu.",
                    "No location: click on the map or name a known place.",
                    "لا يوجد موقع: انقر على الخريطة أو اذكر مكانًا معروفًا.")})
                return
            ans = save(to_answer(resp, aid, question, lang))
            yield sse("step", {**first, "status": "done", "duration_ms": 0,
                               "summary": ans["steps"][0]["summary"] if ans["steps"] else None})
            for s in ans["steps"]:
                yield sse("step", s)
            yield sse("answer", ans)
        except Exception as e:                      # never leave the stream without an answer or an error
            yield sse("error", {"code": "internal", "message": same3("backend.error.internal", str(e))})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.get("/answers/{aid}")
def get_answer(aid: str):
    a = load(aid)
    if not a and aid.startswith("event-"):
        a = event_answer(aid[len("event-"):])
    if not a:
        return api_error("not_found", 404, "Cette réponse n'existe pas.", "This answer does not exist.",
                         "هذه الإجابة غير موجودة.")
    return a


# ---------------------------------------------------------------------------
# events -> library and offline demo bundle
# ---------------------------------------------------------------------------
QUESTIONS_I18N = {   # the event questions in the two other languages (the French ones live in events.py)
    "panama-2026": {"en": "Where did the ground move after the Panama earthquake?",
                    "ar": "أين تحركت الأرض بعد زلزال بنما؟"},
    "haouz-flood-2026-10-10": {"en": "Did the ground change at Asni during the flash flood of 10 October 2026?",
                               "ar": "هل تغيّرت الأرض في أسني خلال سيول 10 أكتوبر 2026؟"},
    "haouz-soil-moisture": {"en": "What is the soil moisture at Asni?", "ar": "ما رطوبة التربة في أسني؟"},
    "gharb-soil-moisture": {"en": "What is the soil moisture in the Gharb?", "ar": "ما رطوبة التربة في الغرب؟"},
    "ben-guerir-mine": {"en": "Where did the surface of the Ben Guerir mine change?",
                        "ar": "أين تغيّر سطح منجم ابن جرير؟"},
    "al-wahda-surroundings": {"en": "Is the ground around the Al Wahda dam moving?",
                              "ar": "هل تتحرك الأرض حول سد الوحدة؟"},
}


def _all_events():
    return events.EVENTS + events.VALIDATION_EVENTS


def _ev(eid):
    return next((e for e in _all_events() if e["id"] == eid), None)


def event_answer(eid: str, refresh: bool = False) -> dict | None:
    ev = _ev(eid)
    if not ev:
        return None
    aid = f"event-{eid}"
    if not refresh:
        a = load(aid)
        if a:
            return a
    resp = events.get(eid, refresh)
    if not resp:
        return None
    names = {"fr": ev.get("title"), "en": ev.get("title_en"), "ar": ev.get("title_ar")}
    return save(to_answer(resp, aid, ev["question"], ev.get("lang", "fr"),
                          {k: v for k, v in names.items() if v} or None, cached=True))


@router.get("/library")
def library():
    out = []
    for ev in _all_events():
        kind = "earthquake" if ev.get("usgs_id") else "flood" if "flood" in ev["id"] else None
        if not kind:                      # sites (soil moisture, mine, dam) are not events: demo bundle only
            continue
        a = event_answer(ev["id"])
        names = {k: v for k, v in {"fr": ev.get("title"), "en": ev.get("title_en"), "ar": ev.get("title_ar")}.items() if v}
        d = iso(ev.get("date") or ev.get("origin_utc"))
        if kind == "earthquake":
            usgs = next((e for e in (a or {}).get("evidence", []) if e["source"] == "usgs"), None)
            ref = {"source": "usgs", "agreement": usgs["agreement"] if usgs else "inconclusive",
                   "summary": tt("library.usgs", {"mag": ev.get("magnitude"), "date": {"date": d}}),
                   "url": ev.get("usgs_url"), "comparison": None}
            mag = {"value": ev.get("magnitude"), "type": "Mww"}
        else:
            rain = next((e for e in (a or {}).get("evidence", []) if e["source"] == "open_meteo"), None)
            ref = {"source": "open_meteo", "agreement": rain["agreement"] if rain else "unavailable",
                   "summary": rain["summary"] if rain else tt("backend.library.no_reference", {},
                                                              "Pas de référence indépendante.", "No independent reference.",
                                                              "لا مرجع مستقل."),
                   "url": None, "comparison": None}
            mag = None
        out.append({"id": ev["id"], "kind": kind, "date": d,
                    "location": {"lat": ev["lat"], "lon": ev["lon"], "name": ev.get("title"),
                                 **({"name_i18n": names} if names else {}), "bbox": None},
                    "magnitude": mag, "answer_id": a["id"] if a else None, "reference": ref})
    return out


@router.get("/demo")
def demo():
    entries = []
    for ev in _all_events():
        a = event_answer(ev["id"])
        if not a:
            continue
        qs = [{"text": ev["question"], "lang": ev.get("lang", "fr")}]
        for L, q in QUESTIONS_I18N.get(ev["id"], {}).items():
            qs.append({"text": q, "lang": L})
        entries.append({"answer_id": a["id"], "questions": qs})
    return {"generated_at": now_iso(), "entries": entries}


@router.get("/proofs/lband-vs-cband")
def lband():
    return api_error("not_available", 404,
                     "La comparaison bande L / bande C n'a pas encore été calculée.",
                     "The L-band versus C-band comparison has not been computed yet.",
                     "لم تُحسب بعد المقارنة بين النطاق L والنطاق C.")


# ---------------------------------------------------------------------------
# discoveries
# ---------------------------------------------------------------------------
REGION = {"MA": {"fr": "Maroc", "ar": "المغرب", "en": "Morocco"}}


@router.get("/discoveries")
def get_discoveries(region: str = "MA"):
    if not discoveries.is_enabled():
        return api_error("discoveries_disabled", 503,
                         "Découverte automatique désactivée : les zones candidates ne sont pas encore validées.",
                         "Automatic discovery is off: the candidate zones are not validated yet.",
                         "الاكتشاف التلقائي معطّل: المناطق المرشّحة غير مؤكَّدة بعد.")
    d = discoveries.cached()
    zones, sig = [], []
    for z in d.get("zones", []):
        unit = z.get("unit", "cm")
        unit = unit if unit in ("cm", "mm/yr") else "cm"
        snr = float(z.get("snr") or 0)
        sigma = abs(z.get("mean", 0)) / snr if snr else 0
        sig.append(sigma)
        ex = z.get("exposure") or {}
        kind = "dam" if ex.get("dams") else "mine" if ex.get("quarries_mines") else \
            "urban" if (ex.get("buildings") or 0) > 50 else "other"
        zones.append({"id": z.get("id", f"zone-{len(zones) + 1}"), "rank": z.get("rank", len(zones) + 1),
                      "location": {"lat": z["lat"], "lon": z["lon"], "name": None, "bbox": None},
                      "kind": kind, "velocity": meas(z.get("mean", 0), sigma, unit), "vertical": None, "east_west": None,
                      "snr": snr, "exposure": {"buildings": ex.get("buildings"), "roads_km": None, "dams": ex.get("dams"),
                                               "mines": ex.get("quarries_mines")},
                      "exposure_score": float((ex.get("buildings") or 0) * 0.01 + (ex.get("dams") or 0) * 5
                                              + (ex.get("quarries_mines") or 0) * 3 + (ex.get("hospitals_schools") or 0)),
                      "confidence": z.get("confidence", "low"), "manually_checked": False, "answer_id": None})
    dates = sorted({d_ for p in catalog.load() if p.level == "GUNW" for d_ in (iso(p.ref), iso(p.sec)) if d_})
    sig.sort()
    return {"region": region, "region_name": REGION.get(region, REGION["MA"]), "generated_at": now_iso(),
            "period": {"start": dates[0], "end": dates[-1]} if dates else {"start": date.today().isoformat(),
                                                                          "end": date.today().isoformat()},
            "noise_floor": meas(sig[len(sig) // 2] if sig else 0, 0, zones[0]["velocity"]["unit"] if zones else "cm"),
            "threshold_factor": 3.0, "zones": zones}


# ---------------------------------------------------------------------------
# watches and notifications
# ---------------------------------------------------------------------------
def _read(path) -> list:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def _watch_view(w: dict) -> dict:
    return {k: w[k] for k in ("id", "location", "question", "recipe", "created_at", "level", "confidence",
                              "last_pass", "next_pass", "track", "answer_id")}


def _place_param(loc: dict) -> dict:
    names = loc.get("name_i18n") or {}
    base = loc.get("name") or f"{loc['lat']:.3f}, {loc['lon']:.3f}"
    return {"localized": {L: names.get(L) or base for L in LANGS}}


def _notify(w: dict, level: str, previous: str | None, message: dict):
    with _lock:
        ns = _read(NOTES)
        ns.append({"id": uuid.uuid4().hex[:10], "watch_id": w["id"], "created_at": now_iso(), "level": level,
                   "previous_level": previous, "message": message, "answer_id": w.get("answer_id")})
        _write(NOTES, ns)


@router.get("/watches")
def list_watches():
    return [_watch_view(w) for w in _read(WATCHES)]


@router.post("/watches")
async def create_watch(request: Request):
    body = await request.json()
    aid = body.get("answer_id")
    a = load(aid) if aid else None
    if not a:
        return api_error("not_found", 404, "Cette réponse n'existe pas.", "This answer does not exist.",
                         "هذه الإجابة غير موجودة.")
    with _lock:
        ws = _read(WATCHES)
        existing = next((w for w in ws if w.get("answer_id") == aid), None)
        if existing:
            return _watch_view(existing)
        nxt = a.get("next_pass")
        last = a["acquisitions"][-1] if a.get("acquisitions") else None
        if not nxt:
            base = date.fromisoformat(last) if last else date.today()
            while base <= date.today():
                base += timedelta(days=watch.REPEAT_DAYS)
            nxt = base.isoformat()
        w = {"id": uuid.uuid4().hex[:8], "location": a["location"], "question": a["question"], "recipe": a["recipe"],
             "created_at": now_iso(), "level": a.get("x_alert_level"), "confidence": a.get("confidence"),
             "last_pass": last, "next_pass": nxt, "track": a["tracks"][0] if a.get("tracks") else None,
             "answer_id": aid, "lang": a.get("lang", "fr")}
        ws.append(w)
        _write(WATCHES, ws)
    if w["level"]:
        _notify(w, w["level"], None, tt("notify.watch_created", {"place": _place_param(w["location"]),
                                                                 "next_pass": {"date": nxt}}))
    return _watch_view(w)


@router.delete("/watches/{wid}")
def delete_watch(wid: str):
    with _lock:
        ws = _read(WATCHES)
        keep = [w for w in ws if w["id"] != wid]
        _write(WATCHES, keep)
    if len(keep) == len(ws):
        return api_error("not_found", 404, "Surveillance inconnue.", "Unknown watch.", "مراقبة غير معروفة.")
    return Response(status_code=204)


@router.get("/notifications")
def notifications():
    return list(reversed(_read(NOTES)))


@router.post("/watches/check")
def check_watches():
    """Re-runs every watch on the data now in the catalog; a notification only when the level changes."""
    catalog.refresh()
    changed = []
    for w in _read(WATCHES):
        resp = agent.investigate(w["question"], w["location"]["lat"], w["location"]["lon"], w.get("lang", "fr"))
        a = save(to_answer(resp, w["answer_id"], w["question"], w.get("lang", "fr"), w["location"].get("name_i18n")))
        new = a.get("x_alert_level")
        if new and new != w.get("level"):
            v = a["verdict"]["text"]
            _notify(w, new, w.get("level"), tt("backend.notify.level_changed", {},
                                               f"Niveau {new} : {v.get('fr', '')}", f"Level {new}: {v.get('en', '')}",
                                               f"المستوى {new}: {v.get('ar', '')}"))
            changed.append(w["id"])
        with _lock:
            ws = _read(WATCHES)
            for x in ws:
                if x["id"] == w["id"]:
                    x.update(level=new, confidence=a.get("confidence"), next_pass=a.get("next_pass") or x["next_pass"])
            _write(WATCHES, ws)
    return {"changed": changed}


@router.post("/watches/{wid}/simulate")
def simulate_pass(wid: str, level: str = "orange"):
    """DEMO ONLY: shows what an alert looks like. The message says SIMULATION in every language."""
    w = next((x for x in _read(WATCHES) if x["id"] == wid), None)
    if not w or level not in ("yellow", "orange", "red"):
        return api_error("not_found", 404, "Surveillance inconnue.", "Unknown watch.", "مراقبة غير معروفة.")
    p = _place_param(w["location"])["localized"]
    _notify(w, level, w.get("level"), tt("backend.notify.simulation", {},
                                          f"SIMULATION (démo) : {p['fr']} passe au niveau {level}.",
                                          f"SIMULATION (demo): {p['en']} moves to level {level}.",
                                          f"محاكاة (عرض): {p['ar']} ينتقل إلى المستوى {level}."))
    return {"simulated": True, "watch_id": wid, "level": level}


@router.get("/health")
def health():
    return {"status": "ok", "version": "nisar-pulse-backend", "data": "live" if catalog.load() else "cache"}


# ---------------------------------------------------------------------------
# case studies (docs/CASE_CONTRACT.md); the logic lives in science/case_store.py
# ---------------------------------------------------------------------------
@router.get("/cases")
def list_cases():
    return case_store.summaries()


@router.get("/cases/{cid}")
def get_case(cid: str):
    try:
        case = case_store.load(cid)
    except case_store.CaseFileError:
        return api_error("case_invalid", 500, "Ce cas d'étude est invalide côté serveur.",
                         "This case study is invalid on the server.", "دراسة الحالة هذه غير صالحة على الخادم.")
    if case is None:
        return api_error("case_not_found", 404, "Cas d'étude introuvable.", "Case study not found.",
                         "دراسة الحالة غير موجودة.")
    return case_store.to_json(case)


@router.get("/cases/{cid}/figures/{name}")
def get_case_figure(cid: str, name: str):
    path = case_store.figure_path(cid, name)
    if path is None:
        return api_error("figure_not_found", 404, "Figure introuvable.", "Figure not found.", "الشكل غير موجود.")
    return FileResponse(path, media_type=case_store.MEDIA[path.suffix.lower().lstrip(".")])
