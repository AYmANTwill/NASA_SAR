"""NISAR Pulse API.  Run:  uvicorn api:app --reload --port 8000   then open http://localhost:8000/docs

If no NISAR data has been processed yet (or ?mock=true), endpoints answer with realistic fake data
marked "mock": true, so the interface can be wired immediately."""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import agent
import catalog
import discoveries
import events
import mock
import watch
from config import ANTHROPIC_API_KEY, CACHE_DIR, DATA_DIR, FIRMS_MAP_KEY, OFFLINE

app = FastAPI(title="NISAR Pulse API", version="0.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
(CACHE_DIR / "layers").mkdir(parents=True, exist_ok=True)
app.mount("/layers", StaticFiles(directory=CACHE_DIR / "layers"), name="layers")
FORCE_MOCK = os.environ.get("NISAR_MOCK", "0") == "1"


def _mock_layer():
    """Placeholder image for the mock answer's map layer."""
    import numpy as np
    from PIL import Image
    f = CACHE_DIR / "layers" / "mock_disp.png"
    if not f.exists():
        y, x = np.mgrid[-1:1:256j, -1:1:256j]
        v = np.exp(-(x ** 2 + y ** 2) * 6)
        rgba = np.zeros((256, 256, 4), "uint8")
        rgba[..., 0] = (255 * (1 - v)).astype("uint8")
        rgba[..., 1] = (255 * (1 - v)).astype("uint8")
        rgba[..., 2] = 255
        rgba[..., 3] = (200 * v).astype("uint8")
        Image.fromarray(rgba, "RGBA").save(f)


_mock_layer()


def use_mock(flag: bool) -> bool:
    return flag or FORCE_MOCK or not catalog.load()


class Ask(BaseModel):
    question: str
    lat: float | None = None
    lon: float | None = None
    lang: str | None = None          # fr | en | ar (auto-detected if absent)
    date: str | None = None          # YYYY-MM-DD of an event, optional


class WatchIn(BaseModel):
    lat: float
    lon: float
    question: str
    lang: str = "fr"
    label: str | None = None


@app.get("/health")
def health():
    ps = catalog.refresh()
    counts = {}
    for p in ps:
        counts[p.level] = counts.get(p.level, 0) + 1
    return {"ok": True, "data_dir": str(DATA_DIR), "products": counts, "mock_mode": use_mock(False),
            "llm": bool(ANTHROPIC_API_KEY), "firms": bool(FIRMS_MAP_KEY), "offline": OFFLINE}


@app.get("/catalog")
def get_catalog(level: str | None = None):
    return [p.summary() for p in catalog.load() if level is None or p.level == level]


@app.get("/places")
def places():
    from config import GAZETTEER
    return [{"name": k, "lat": v[0], "lon": v[1]} for k, v in GAZETTEER.items()]


@app.post("/ask")
def ask(body: Ask, mock_: bool = Query(False, alias="mock")):
    if use_mock(mock_):
        return mock.ASK
    res = agent.investigate(body.question, body.lat, body.lon, body.lang, body.date)
    if "error" in res and "verdict" not in res:
        raise HTTPException(400, res)
    return res


@app.get("/events")
def list_events():
    return events.listing()


@app.get("/events/{eid}")
def get_event(eid: str, refresh: bool = False, mock_: bool = Query(False, alias="mock")):
    if use_mock(mock_):
        return {**mock.ASK, "event": {"id": eid, "title": eid}}
    r = events.get(eid, refresh)
    if r is None:
        raise HTTPException(404, "unknown event")
    return r


@app.get("/discoveries")
def get_discoveries(refresh: bool = False, exposure: bool = True, mock_: bool = Query(False, alias="mock")):
    if use_mock(mock_):
        return mock.DISCOVERIES
    return discoveries.scan(with_exposure=exposure) if refresh else discoveries.cached()


@app.get("/next-pass")
def next_pass(lat: float, lon: float):
    return watch.next_passes(lat, lon)


@app.post("/watch")
def add_watch(body: WatchIn, mock_: bool = Query(False, alias="mock")):
    if use_mock(mock_):
        return mock.WATCH
    return watch.add(body.lat, body.lon, body.question, body.lang, body.label)


@app.get("/watch")
def list_watch():
    return watch.all_watches()


@app.delete("/watch/{wid}")
def delete_watch(wid: str):
    if not watch.remove(wid):
        raise HTTPException(404, "unknown watch")
    return {"deleted": wid}


@app.post("/watch/check")
def check_watch():
    return {"alerts": watch.check_all()}


class ClassifyIn(BaseModel):
    before_id: str
    after_id: str


@app.post("/classify")
def classify(body: ClassifyIn):
    import ml_classifier
    if not ml_classifier.MODEL_PATH.exists():
        raise HTTPException(409, "classifier not trained yet (run train_classifier.py)")
    b, a = catalog.by_id(body.before_id), catalog.by_id(body.after_id)
    if not b or not a:
        raise HTTPException(404, "unknown product id")
    return ml_classifier.predict(b, a, f"{b.id}_{a.id}")
