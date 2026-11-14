"""End-to-end check of every feature on synthetic data (no internet needed).
Usage (from backend/):  python tests/test_all.py"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp(prefix="nisar_test_"))
os.environ.update(NISAR_DATA=str(tmp / "data"), NISAR_CACHE=str(tmp / "cache"), NISAR_OFFLINE="1")
subprocess.run([sys.executable, str(ROOT / "tests" / "make_synthetic.py"), str(tmp / "data")], check=True,
               capture_output=True)
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import agent  # noqa: E402
import api  # noqa: E402
from recipes import timeseries as _ts  # noqa: E402

agent.classify_llm = lambda q: None      # the tests never call a language model
_ts.MIN_RATE_DAYS = 40                   # the synthetic stacks are 1.5-4 months long; the real 365-day rule is tested below

c = TestClient(api.app)
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  — {detail}" if detail else ""))


h = c.get("/health").json()
check("health: products found", h["products"].get("GUNW", 0) > 0 and not h["mock_mode"], h["products"])
check("catalog lists products", len(c.get("/catalog").json()) > 40)
check("places", len(c.get("/places").json()) > 5)

r = c.post("/ask", json={"question": "Où le sol a-t-il bougé après le séisme du 9 octobre 2026 au Panama ?",
                         "lat": 7.59, "lon": -80.77}).json()
dec = r["facts"].get("decomposition_cm") or {}
check("ask sudden_motion: type", r["type"] == "sudden_motion")
check("ask sudden_motion: recovers 25 cm up / 15 cm east", abs(dec.get("up", 0) - 25) < 2 and abs(dec.get("east", 0) - 15) < 2, dec)
png = r["layers"][0]["url"]
check("layer PNG served", c.get(png).status_code == 200 and c.get(png).headers["content-type"] == "image/png", png)

r = c.post("/ask", json={"question": "Le barrage Al Wahda se déforme-t-il depuis juin ?"}).json()
up = (r["facts"].get("decomposition_mm_yr") or {}).get("up")
check("ask slow_motion: vertical velocity near the -20 mm/yr truth (bump-weighted)", up is not None and -22 < up < -15, up)
check("ask slow_motion: series returned", r.get("series") and len(r["series"][0]["series"]) > 5)

r = c.post("/ask", json={"question": "Y a-t-il des dégâts après le séisme du Panama ?",
                         "lat": 7.59 + 1 / 111, "lon": -80.77 + 1 / 110}).json()
check("ask surface change (earthquake, exact instant): coherence loss found, before and event pairs of the same length",
      r["type"] == "surface_change" and (r["facts"].get("loss_at_point") or 0) > 0.3 and r["facts"]["mode"] == "event"
      and r["facts"]["event_precision"] == "exact" and r["facts"]["window_days"] == 12, r["facts"].get("loss_at_point"))
r = c.post("/ask", json={"question": "Mes champs ont-ils été inondés ?", "lat": 34.5, "lon": -6.0 - 3 / 92}).json()
check("ask flood: open water found", r["type"] == "flood" and r["facts"]["open_water_ha"] > 500, r["facts"].get("open_water_ha"))
r = c.post("/ask", json={"question": "La forêt a-t-elle été coupée ?", "lat": 34.5 + 2 / 111, "lon": -6.0 + 4 / 92}).json()
check("ask deforestation: loss found", r["type"] == "deforestation" and r["facts"]["vegetation_loss_ha"] > 100)
r = c.post("/ask", json={"question": "Quelle est l'humidité du sol ?", "lat": 34.5, "lon": -6.0}).json()
check("ask soil_moisture: series of 6, picks the final soilMoisture grid",
      r["type"] == "soil_moisture" and r["facts"]["n_passes"] == 6 and r["facts"]["dataset"].endswith("grids/soilMoisture")
      and 0.1 < r["facts"]["latest_m3m3"] < 0.4, (r["facts"].get("dataset"), r["facts"].get("latest_m3m3")))
r = c.post("/ask", json={"question": "هل يتحرك سد الوحدة؟"}).json()
check("ask in Arabic: Arabic verdict", r["lang"] == "ar" and any("؀" <= ch <= "ۿ" for ch in r["verdict"]))
r = c.post("/ask", json={"question": "Le glacier avance-t-il ?", "lat": 34.5, "lon": -6.0}).json()
check("ask without data: graceful answer", "verdict" in r and r["confidence"] == "low")
check("ask without location: 400", c.post("/ask", json={"question": "Ça bouge ?"}).status_code == 400)

ev = c.get("/events/al-wahda-surroundings").json()
check("event computed", ev.get("event", {}).get("id") == "al-wahda-surroundings" and ev.get("verdict"))
check("events listing", any(e["computed"] for e in c.get("/events").json()))

d = c.get("/discoveries", params={"refresh": True, "exposure": False}).json()
near = lambda z, lat, lon: abs(z["lat"] - lat) < 0.05 and abs(z["lon"] - lon) < 0.05
check("discoveries: finds the Ben Guerir subsidence", any(near(z, 32.27, -7.93) for z in d["zones"]),
      [(z["lat"], z["lon"], z["mean"], z["unit"]) for z in d["zones"][:5]])
check("discoveries: finds Al Wahda", any(near(z, 34.598, -5.198) for z in d["zones"]))

w = c.post("/watch", json={"lat": 34.598, "lon": -5.198, "question": "Le barrage Al Wahda se déforme-t-il ?"}).json()
check("watch created with next passes", w.get("id") and w["next_passes"], w.get("next_passes", [])[:1])
check("watch listed", any(x["id"] == w["id"] for x in c.get("/watch").json()))
check("watch check runs", "alerts" in c.post("/watch/check").json())
check("watch delete", c.delete(f"/watch/{w['id']}").status_code == 200)
check("next-pass", len(c.get("/next-pass", params={"lat": 34.598, "lon": -5.198}).json()) >= 2)

check("mock mode answers", c.post("/ask?mock=true", json={"question": "x"}).json().get("mock") is True)
check("mock layer served", c.get("/layers/mock_disp.png").status_code == 200)

# change classifier: train on the synthetic GCOV pair (flood + vegetation loss labels), predict
import catalog  # noqa: E402
import ml_classifier as mc  # noqa: E402
import numpy as np  # noqa: E402

g = [p for p in catalog.load() if p.level == "GCOV"]
F, prof = mc.features(g[0], g[1])
db = lambda a: 10 * np.log10(np.clip(a, 1e-6, None))
import raster  # noqa: E402
hh_a = raster.read(g[1].files["hh"])[0]
hv_b, hv_a = raster.read(g[0].files["hv"])[0], raster.read(g[1].files["hv"])[0]
y = mc.labels_from_masks(F.shape[:2], flooded=db(hh_a) < -20, veg_loss=(db(hv_a) - db(hv_b)) < -4)
m = mc.train([(F, y)], (F, y))
check("classifier trained", mc.MODEL_PATH.exists() and m["n_train"] > 1000, m["classes"])
f1 = {k: round(m["report"][k]["f1-score"], 2) for k in m["classes"]}
check("classifier f1 > 0.8 on synthetic", min(f1.values()) > 0.8, f1)
r = c.post("/classify", json={"before_id": g[0].id, "after_id": g[1].id}).json()
check("classify endpoint", "areas_ha" in r and r["areas_ha"].get("flooded", 0) > 100, r.get("areas_ha"))

out = subprocess.run([sys.executable, str(ROOT / "precompute.py"), "--no-exposure"], cwd=ROOT,
                     capture_output=True, text=True, env=os.environ)
check("precompute script", out.returncode == 0, out.stdout.strip().splitlines()[-1] if out.stdout else out.stderr[-300:])

# ---------------------------------------------------------------------------------------------
# Morocco backend (docs/claude/MOROCCO_PLAN.md §5): CRID, event windows, surface change, time-series rules,
# trilingual verdicts. Synthetic data reuse the same formulas as the recipes: these tests check the logic,
# not the physics (see the science-check notes in the review).
# ---------------------------------------------------------------------------------------------
import re as _re  # noqa: E402
import types as _types  # noqa: E402

import evidence as _evidence  # noqa: E402
import events as _events  # noqa: E402
import mock as _mock  # noqa: E402
from recipes import damage as _damage  # noqa: E402

AL = (34.598, -5.198)
ASNI = (31.250, -7.983)

# --- router: whole words, FR / EN / AR, unknown question is not guessed ---------------------------
cases = {"Cette street est-elle un problème ?": None, "Is the street flooded?": "flood",
         "Is the damage visible?": "surface_change", "Is the dam moving?": "slow_motion",
         "Le barrage Al Wahda se déforme-t-il depuis juin ?": "slow_motion",
         "Did the flash flood change Imlil?": "surface_change", "crue éclair à Asni le 10 octobre": "surface_change",
         "سيول الحوز": "surface_change", "هل يتحرك سد الوحدة؟": "slow_motion",
         "Quelle est l'humidité du sol ?": "soil_moisture", "Mes champs ont-ils été inondés ?": "flood",
         "Où la surface de la mine de Ben Guerir a-t-elle changé ?": "surface_change",
         "Is the soil wet?": "soil_moisture", "wetland map": None, "La forêt a-t-elle été coupée ?": "deforestation"}
bad = {q: agent.classify_rules(q)[0] for q, t in cases.items() if agent.classify_rules(q)[0] != t}
check("router: whole-word keywords in FR/EN/AR ('street' is not 'tree', 'damage' is not 'dam', no keyword = no type)",
      not bad, bad)
r = c.post("/ask", json={"question": "Quel temps fait-il ?", "lat": 34.5, "lon": -6.0})
check("unknown question: 200 with a request to rephrase, no type guessed, no alert",
      r.status_code == 200 and r.json()["type"] == "unknown" and "Reformulez" in r.json()["verdict"]
      and r.json()["alert_level"] == "none")
check("event detection: Panama exact instant; Haouz and dated questions are whole-day events",
      agent.find_event("séisme du Panama") == ("20261009T175606", "exact") and agent.find_event("crue à Asni")[1] == "day"
      and agent.find_event("le 10 octobre 2026") == ("20261010T000000", "day") and agent.find_event("rien") == (None, None))

# --- catalog: event windows and CRID ------------------------------------------------------------
P = lambda ref, sec: _types.SimpleNamespace(ref=ref, sec=sec)  # noqa: E731
EV = "20261010T000000"
rel = lambda ref, sec, ev=EV, prec="day": catalog.relation(P(ref, sec), ev, prec)  # noqa: E731
check("catalog.relation: exact instant (ref <= event <= sec straddles)",
      rel("20261009T100000", "20261009T180000", "20261009T175606", "exact") == "straddles"
      and rel("20260927T000000", "20261009T100000", "20261009T175606", "exact") == "before"
      and rel("20261009T180000", "20261012T000000", "20261009T175606", "exact") == "after")
check("catalog.relation: whole-day event: only a pair that starts before the day and ends after it straddles; "
      "an acquisition inside the day is ambiguous",
      rel("20261003T054606", "20261015T054606") == "straddles"
      and rel("20261003T054606", "20261010T054606") == "ambiguous"
      and rel("20261010T054606", "20261022T054606") == "ambiguous"
      and rel("20260921T054606", "20261003T054606") == "before" and rel("20261011T054606", "20261023T054606") == "after")
nm = "NISAR_L2_PR_GUNW_032_044_A_017_033_2000_SH_20261003T054606_20261003T054641_20261015T054606_20261015T054641_{}_N_F_J_001"
check("catalog: CRID parsed; maturity provisional / validated / unknown",
      [catalog.parse_name(nm.format(x))["maturity"] for x in ("P05023", "P05036", "P09999")] == ["provisional", "validated", "unknown"]
      and catalog.parse_name(nm.format("P05036"))["crid"] == "P05036")
cat = c.get("/catalog", params={"level": "GUNW"}).json()
check("/catalog exposes crid and maturity (provisional and validated products both present)",
      all("crid" in x and "maturity" in x for x in cat) and {x["crid"] for x in cat} >= {"P05023", "P05036"})

# --- sudden motion: exact event time, no fallback --------------------------------------------------
r = c.post("/ask", json={"question": "séisme au Panama", "lat": 7.59, "lon": -80.77, "date": "2026-05-05"}).json()
check("sudden motion: no pair straddles the event -> no-data answer, no fallback to other pairs",
      r["type"] == "sudden_motion" and "straddles" in r["facts"].get("error", "") and "value_cm" not in r["facts"]
      and r["confidence"] == "low" and r["alert_level"] == "none" and "straddles" in r["verdict"], r["facts"])
r = c.post("/ask", json={"question": "tremblement de terre ?", "lat": 7.59, "lon": -80.77}).json()
check("sudden motion without an event date: asks for the date instead of picking the latest pair",
      r["type"] == "sudden_motion" and "event" in r["facts"].get("error", "") and "value_cm" not in r["facts"])

# --- surface change (Al Haouz flash flood, whole-day event) ------------------------------------------
Q_HAOUZ = "Le sol a-t-il changé à Asni lors de la crue éclair du 10 octobre 2026 ?"
r = c.post("/ask", json={"question": Q_HAOUZ}).json()
f = r["facts"]
pairs_ok = (f["pre_date_before"], f["pre_date_after"], f["date_before"], f["date_after"]) in {
    ("20260921", "20261003", "20261003", "20261015"), ("20260919", "20261001", "20261001", "20261013")}
check("surface change Haouz: whole-day event; before pair and storm pair share frame, CRID and length (12 d); "
      "provisional label; both geometries used",
      r["type"] == "surface_change" and r["event_time"] == {"utc": "20261010T000000", "precision": "day"} and pairs_ok
      and f["window_days"] == 12 and f["crid"] == "P05023" and f["maturity"] == "provisional"
      and f["n_geometries"] == 3 and f["n_usable_geometries"] == 2
      and {g["direction"] for g in f["geometries"] if g["usable"]} == {"ascending", "descending"}
      and [g["frame"] for g in f["geometries"] if not g["usable"]] == [73] and f["geometries_agree"] is True and (f["loss_at_point"] or 0) > 0.3, {k: f.get(k) for k in ("date_before", "loss_at_point")})
check("surface change: a frame that barely covers the point is listed but unusable, and does not vote",
      sum(not g["usable"] for g in f["geometries"]) == 1 and f["changed_km2_range"][0] <= f["changed_km2_range"][1])
check("surface change: medium at most (never high), orange alert, layer is the coherence-loss map",
      r["confidence"] == "medium" and r["alert_level"] == "orange" and r["layers"] and "Surface change" in r["layers"][0]["title"]
      and "changed_km2_5km" in f and "damaged_km2_5km" not in f)


def stray_numbers(verdict, facts):
    """Numbers in a verdict that are not in the facts (template constants 0, 1, 5 are allowed)."""
    allowed = {0.0, 1.0, 5.0}

    def walk(x):
        if isinstance(x, dict):
            [walk(v) for v in x.values()]
        elif isinstance(x, (list, tuple)):
            [walk(v) for v in x]
        elif isinstance(x, bool) or x is None:
            pass
        elif isinstance(x, (int, float)):
            allowed.add(abs(float(x)))
        elif isinstance(x, str) and _re.fullmatch(r"\d{8}(T\d{6})?", x):
            allowed.update({float(int(x[:4])), float(int(x[4:6])), float(int(x[6:8]))})
    walk(facts)
    stray = set()
    for tok in _re.findall(r"\d+(?:\.\d+)?", verdict):
        dec = len(tok.split(".")[1]) if "." in tok else 0
        if not any(abs(round(a, dec) - float(tok)) < 1e-9 for a in allowed):     # the sentence rounds a fact
            stray.add(tok)
    return stray


verdicts = {lg: c.post("/ask", json={"question": Q_HAOUZ, "lang": lg}).json() for lg in ("fr", "en", "ar")}
check("surface change verdict in French, English and Arabic; every number comes from the facts",
      "perte de cohérence" in verdicts["fr"]["verdict"] and "coherence loss" in verdicts["en"]["verdict"]
      and any("؀" <= ch <= "ۿ" for ch in verdicts["ar"]["verdict"])
      and all(not stray_numbers(v["verdict"], v["facts"]) for v in verdicts.values()),
      {lg: stray_numbers(v["verdict"], v["facts"]) for lg, v in verdicts.items()})
check("surface change: says it is not damage / depth / cause, in the three languages",
      all(verdicts[lg]["cannot_say"] for lg in verdicts) and verdicts["ar"]["cannot_say"] != verdicts["fr"]["cannot_say"])
_rain = _evidence.rainfall
_evidence.rainfall = lambda lat, lon, a, b: {"source": "Open-Meteo", "status": "agrees", "summary": "80 mm", "total_mm": 80, "items": []}
try:
    rr = agent.investigate(Q_HAOUZ, lang="fr")
finally:
    _evidence.rainfall = _rain
st = {e["source"]: e["status"] for e in rr["evidence"]}
check("surface change: rain is CONTEXT, never an independent confirmation (status 'context', confidence stays medium)",
      st.get("Open-Meteo") == "context" and rr["confidence"] == "medium", st)
rr = agent.investigate("Le sol a-t-il changé à Asni ?", date="2026-10-03", lang="fr")
check("surface change: a pair with an acquisition on the event day is ambiguous and never used",
      rr["facts"]["n_geometries"] == 1 and rr["facts"]["direction"] == "descending" and len(rr["facts"]["ambiguous_pairs"]) == 2,
      rr["facts"].get("ambiguous_pairs"))
rr = agent.investigate("Mes champs à Asni ont-ils été inondés ?", lang="fr")
check("flood question with no GCOV product: routed to surface change and says so",
      rr["type"] == "surface_change" and rr["facts"]["routed_from"] == "flood" and rr["verdict"].startswith("Pas de données de rétrodiffusion"))
em = c.get("/events/ben-guerir-mine").json()
check("surface change without an event date: 'latest' mode says so, no change in synthetic data -> no alert",
      em["type"] == "surface_change" and em["facts"]["mode"] == "latest" and em["event_time"] is None
      and "Sans date d'événement" in em["verdict"] and em["alert_level"] == "none", em["facts"].get("loss_at_point"))


def fp(key, span, ref, sec, name):
    return _types.SimpleNamespace(series_key=key, span_days=span, ref=ref, sec=sec, files={"coherence": "x"}, id=name)


k_prov, k_val = (44, 17, "P05023"), (44, 17, "P05036")
pre12, pre24 = fp(k_prov, 12, "20260921T054606", "20261003T054606", "pre12"), fp(k_prov, 24, "20260909T054606", "20261003T054606", "pre24")
co12 = fp(k_prov, 12, "20261003T054606", "20261015T054606", "co12")
ids = lambda cands: [(b.id, c_.id) for b, c_ in cands]  # noqa: E731
check("surface change pairing: same pair length (coherence decays with the baseline) and same CRID are required",
      ids(_damage._candidates([pre12, pre24, co12], EV, "day")) == [("pre12", "co12")]
      and _damage._candidates([pre24, co12], EV, "day") == []
      and _damage._candidates([fp(k_val, 12, "20260921T054606", "20261003T054606", "preV"), co12], EV, "day") == [])

# --- time series: connected chain, CRIDs separate, no rate under 12 months --------------------------------
al_pairs = [p for p in catalog.find(*AL, "GUNW") if p.series_key == (116, 19, "P05023")]
dates_al = sorted({p.ref[:8] for p in al_pairs} | {p.sec[:8] for p in al_pairs})
mid = dates_al[len(dates_al) // 2]
cut = [p for p in al_pairs if not (p.ref[:8] <= mid <= p.sec[:8])]          # remove every pair that spans one date
full_s, cut_s = _ts.point_series(al_pairs, *AL)[0], _ts.point_series(cut, *AL)[0]
check("time series: a connected chain uses its 24-day pairs; cutting the chain is reported, never bridged",
      full_s["chain_connected"] and full_s["n_components"] == 1 and full_s["n_bridge_pairs"] > 0
      and full_s["series"][0]["los_mm"] == 0.0 and full_s["total_los_mm"] == full_s["series"][-1]["los_mm"]
      and not cut_s["chain_connected"] and cut_s["n_components"] == 2 and any(x["los_mm"] is None for x in cut_s["series"]))
lin = np.array([0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0])
short_d = ["20260101", "20260201", "20260301", "20260401", "20260501", "20260601", "20260701"]
long_d = ["20260101", "20260301", "20260501", "20260701", "20260901", "20261101", "20270101"]
check("time series: rate withheld under 12 months (365 d), reported from 12 months",
      _ts._fit(short_d, lin, min_days=365)["velocity_mm_yr"] is None and _ts._fit(short_d, lin, min_days=365)["min_rate_days"] == 365
      and 11 < _ts._fit(long_d, lin, min_days=365)["velocity_mm_yr"] < 13)
_ts.MIN_RATE_DAYS = 365                                                       # the real default, for the next checks
try:
    r = c.post("/ask", json={"question": "Le barrage Al Wahda se déforme-t-il depuis juin ?"}).json()
    vm_none = _ts.velocity_map(al_pairs) is None
finally:
    _ts.MIN_RATE_DAYS = 40
f = r["facts"]
check("slow motion, 4-month record: cumulative LOS only, no mm/yr, no decomposition, confidence capped, provisional label",
      f["velocity_mm_yr"] is None and f["total_mm"] is not None and "decomposition_mm_yr" not in f
      and r["confidence"] in ("low", "medium") and any("capped" in x for x in r["confidence_reasons"])
      and "trop courte" in r["verdict"] and "produit NISAR provisoire" in r["verdict"] and vm_none, (f.get("span_days"), r["confidence"]))
check("slow motion: provisional (P05023) and validated (P05036) chains are separate series, never mixed",
      {s["crid"] for s in r["series"]} == {"P05023", "P05036"} and f["crid"] == "P05023"
      and min(x["date"] for x in next(s for s in r["series"] if s["crid"] == "P05036")["series"]) >= "20261022")
r = c.post("/ask", json={"question": "Le barrage Al Wahda se déforme-t-il depuis juin ?", "lang": "en"}).json()
check("slow motion with a rate (record >= threshold): rate and vertical component are reported, numbers from facts",
      r["facts"]["velocity_mm_yr"] is not None and "decomposition_mm_yr" in r["facts"] and not stray_numbers(r["verdict"], r["facts"]))

# --- gazetteer, events library, mock, contract --------------------------------------------------------
fp_ = agent.find_place
check("gazetteer: FR / EN / AR aliases resolve to the inventory coordinates; Al Wahda is on the dam",
      fp_("سد الوحدة")[:2] == AL and fp_("Barrage Al Wahda")[:2] == AL and fp_("مولاي إبراهيم")[:2] == fp_("Moulay Brahim")[:2]
      and fp_("إمليل")[:2] == (31.136, -7.919) and fp_("القصر الكبير")[:2] == fp_("Ksar El Kébir")[:2]
      and fp_("la mine de Ben Guerir")[:2] == (32.25825, -7.82355) and fp_("à Ben Guerir")[:2] == (32.27, -7.93))
check("/health gives a Moroccan default map view", c.get("/health").json()["map_view"]["lat"] > 30)
listing = c.get("/events").json()
check("events library: the five Morocco events, Panama only as a hidden test fixture",
      [e["id"] for e in listing] == ["haouz-flood-2026-10-10", "haouz-soil-moisture", "gharb-soil-moisture", "ben-guerir-mine",
                                    "al-wahda-surroundings"] and all(e["title_en"] and e["title_ar"] for e in listing)
      and c.get("/events/panama-2026").json()["type"] == "sudden_motion")
hz = c.get("/events/haouz-flood-2026-10-10").json()
check("events: Haouz flash flood computed (surface change), Gharb soil moisture computed",
      hz["type"] == "surface_change" and (hz["facts"].get("loss_at_point") or 0) > 0.3
      and c.get("/events/gharb-soil-moisture").json()["type"] == "soil_moisture")
check("mock: sentences equal the real templates (so the interface mock cannot drift)",
      agent.template("surface_change", _mock.SURFACE_CHANGE["facts"], "fr") == _mock.SURFACE_CHANGE["verdict"]
      and agent.template("slow_motion", _mock.ASK["facts"], "fr") == _mock.ASK["verdict"]
      and c.get("/events/haouz-flood-2026-10-10?mock=true").json()["type"] == "surface_change")
contract = (ROOT.parent / "docs" / "API_CONTRACT.md").read_text(encoding="utf-8")
check("docs/API_CONTRACT.md: surface_change, context status, crid/maturity, event_time documented; no 'damage' type left",
      all(k in contract for k in ("surface_change", "context", "crid", "maturity", "event_time", "haouz-flood-2026-10-10"))
      and "slow_motion, damage" not in contract)

# ---------------------------------------------------------------------------------------------
# Morocco download plan and downloader flags: offline, nothing is downloaded, no token is read.
# ---------------------------------------------------------------------------------------------
import hashlib  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402

import h5py  # noqa: E402

sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(ROOT.parent / "tools"))
import download_all as da  # noqa: E402
import make_morocco_plan as mmp  # noqa: E402

PLAN_NISAR = ROOT.parent / "plan_nisar.json"
sha_before = hashlib.sha256(PLAN_NISAR.read_bytes()).hexdigest()


def fake(level, track, frame, d, ref, sec, crid="P05023", pf="F", cfg="4000", coll=None):
    coll = coll or ("NISAR_L2_GUNW_PROVISIONAL_V1" if level == "GUNW" else "NISAR_L3_SME2_PROVISIONAL_V1")
    if level == "GUNW":
        name = (f"NISAR_L2_PR_GUNW_032_{track:03d}_{d}_{frame:03d}_033_{cfg}_SH_{ref}T054606_{ref}T054640_"
                f"{sec}T054606_{sec}T054641_{crid}_N_{pf}_J_001")
    else:
        name = f"NISAR_L3_PR_SME2_025_{track:03d}_{d}_{frame:03d}_4005_DHDH_A_{ref}T191107_{ref}T191141_{crid}_{pf}_F_J_001"
    return dict(name=name, url=f"https://example.invalid/NISAR/{coll}/{name}/{name}.h5", size=2_000_000_000,
                level=level, **da.parse_name(name), crid=da.parse_crid(name), collection=coll,
                maturity=da.maturity_of(coll), config=cfg if level == "GUNW" else "")


ACQ = ["20260707", "20260719", "20260812", "20260824", "20260905", "20260917", "20260929", "20261011", "20261023"]
SITE_FRAMES = {"imlil": [(44, 17, "A")], "asni": [(44, 17, "A")], "moulay_brahim": [(44, 17, "A")],
               "al_wahda_dam": [(116, 19, "A"), (15, 19, "A")], "gharb": [(116, 19, "A")],
               "ksar_el_kebir": [(116, 19, "A"), (15, 19, "A")], "chefchaouen": [(116, 19, "A"), (15, 19, "A")],
               "ben_guerir_mine": [(44, 18, "A")]}


def frame_gunw(fr):
    t, f, d = fr
    rows = [fake("GUNW", t, f, d, a, b) for a, b in zip(ACQ, ACQ[1:])]     # includes 07-19 -> 08-12 (gap bridge)
    if fr == (44, 17, "A"):
        rows += [fake("GUNW", t, f, d, "20260917", "20260929", pf="P", cfg="2000"),   # Partial duplicate
                 fake("GUNW", t, f, d, "20260824", "20260929"),                       # 36 d, skips an acquisition
                 fake("GUNW", t, f, d, "20260707", "20260905"),                       # 60 d
                 fake("GUNW", t, f, d, "20261011", "20261104", crid="P05036", coll="NISAR_L2_GUNW_V1")]
    return rows


def frame_sme2(fr):
    t, f, d = fr
    rows = [fake("SME2", t, f, d, a, a) for a in ["20260701", "20260915", "20260927", "20261009"]]
    return rows + [fake("SME2", t, f, d, "20260927", "20260927", pf="P")]


def fake_fetch(level, start, bbox=None, point=None):
    if point is not None:
        key = next(k for k, v in mmp.SITES.items() if v == tuple(point))
        frames = SITE_FRAMES[key]
    else:
        frames = sorted({f for fs in SITE_FRAMES.values() for f in fs}) + [(66, 70, "D")]
    mk = frame_gunw if level == "GUNW" else frame_sme2
    return [r for fr in frames for r in mk(fr)]


plan = mmp.build_plan(fake_fetch)
files = plan["files"]
gu = [r for r in files if r["level"] == "GUNW"]
sm = [r for r in files if r["level"] == "SME2"]
names = {r["name"] for r in files}
frame = lambda r: (r["track"], r["frame"], r["dir"])

check("morocco plan: minimal frames cover all sites (44/17, 116/19, 44/18; not 15/19)",
      {tuple(f) for f in plan["minimal_frames"]} == {(44, 17, "A"), (116, 19, "A"), (44, 18, "A")}, plan["minimal_frames"])
check("morocco plan: parts equal tiers, one of 1/2/3, tier labels present",
      all(r["part"] == r["tier"] in (1, 2, 3) for r in files) and set(plan["tiers"]) == {"1", "2", "3"})
check("morocco plan filter: no Partial duplicate, nothing above 48 d, no pair that skips an acquisition",
      all(r["pf"] == "F" for r in gu) and all(r["span"] <= 48 for r in gu)
      and not any(r["ref_ts"][:8] == "20260824" and r["sec_ts"][:8] == "20260929" for r in gu)
      and not any(r["span"] == 60 for r in gu))
check("morocco plan filter: 15/19 (not a minimal frame) only appears in SME2",
      not any(frame(r) == (15, 19, "A") for r in gu) and any(frame(r) == (15, 19, "A") for r in sm))
bridge = [r for r in gu if frame(r) == (44, 17, "A") and r["ref_ts"][:8] == "20260719" and r["sec_ts"][:8] == "20260812"]
check("morocco plan: the 24-day pair across the data gap is kept (tier 2)",
      len(bridge) == 1 and bridge[0]["span"] == 24 and bridge[0]["tier"] == 2, bridge and bridge[0]["span"])
roles = {r["event_role"]: r for r in gu if r.get("event_role") and r["crid"] == "P05023"}
check("morocco plan: Al Haouz tier 1 = last pre, straddling and first post pair of 10 Oct",
      roles.get("pre", {}).get("sec_ts", "")[:8] == "20260929" and roles.get("straddle", {}).get("ref_ts", "")[:8] == "20260929"
      and roles["straddle"]["sec_ts"][:8] == "20261011" and roles.get("post", {}).get("ref_ts", "")[:8] == "20261011"
      and all(r["tier"] == 1 for r in roles.values()), sorted(roles))
val = [r for r in gu if r["crid"] == "P05036"]
check("morocco plan: VALIDATED pair kept in its own chain (CRIDs not mixed), tier 1, provisional chain untouched",
      len(val) == 1 and val[0]["tier"] == 1 and val[0]["maturity"] == "validated"
      and not any(r["crid"] == "P05023" and r["sec_ts"][:8] == "20261104" for r in gu))
mixed = da.nearest_neighbour([fake("GUNW", 1, 1, "A", "20260929", "20261011"), fake("GUNW", 1, 1, "A", "20261011", "20261023"),
                              fake("GUNW", 1, 1, "A", "20261011", "20261104", crid="P05036")])
check("nearest_neighbour: a VALIDATED pair is judged against VALIDATED acquisitions only", len(mixed) == 3)
check("morocco plan: SME2 tier 1 (since 20 Sep, sites, one version per date) and tier 3 (rest of the box)",
      len([r for r in sm if r["tier"] == 1]) == 8 and len([r for r in sm if r["tier"] == 3]) == 12
      and len(sm) == len({(r["track"], r["frame"], r["ref_ts"]) for r in sm}), (len(sm),))
check("morocco plan: extra_layers only on GUNW rows, no duplicated file across tiers",
      all(r.get("extra_layers") for r in gu) and not any(r.get("extra_layers") for r in sm) and len(names) == len(files))
check("morocco plan: plan_nisar.json untouched by the builder",
      hashlib.sha256(PLAN_NISAR.read_bytes()).hexdigest() == sha_before)

# --- downloader: --plan, tiers, --keep-raw, extra layers --------------------------------------
plan_file = tmp / "plan_morocco_test.json"
plan_file.write_text(json.dumps(plan))
loaded = da.load_plan(plan_file)
check("download_all --plan: loads the given file; tier plan has parts 1..3 and tier labels",
      loaded["files"] == plan["files"] and da.plan_parts(loaded) == [1, 2, 3] and "palier 2" in da.part_tag(loaded, 2))
check("download_all default plan unchanged: parts 1..5, part 1 is the pilot",
      da.plan_parts({"files": []}) == [1, 2, 3, 4, 5] and da.part_tag({}, 1) == " (pilote)" and da.part_tag({}, 2) == "")
help_txt = subprocess.run([sys.executable, str(ROOT.parent / "download_all.py"), "--help"], capture_output=True, text=True).stdout
check("download_all --help lists --plan and --keep-raw", "--plan" in help_txt and "--keep-raw" in help_txt)
bp = subprocess.run([sys.executable, str(ROOT.parent / "download_all.py"), "build-plan", "--plan", str(plan_file)],
                    capture_output=True, text=True)
miss = subprocess.run([sys.executable, str(ROOT.parent / "download_all.py"), "status", "--plan", str(tmp / "nope.json"),
                       "--out", str(tmp / "o")], capture_output=True, text=True)
check("download_all: build-plan refuses --plan; a missing plan is an error (no automatic rebuild)",
      bp.returncode != 0 and "plan_nisar.json" in (bp.stderr + bp.stdout) and miss.returncode != 0
      and "introuvable" in (miss.stderr + miss.stdout).lower())


def make_gunw_h5(path, with_tide=True):
    rng = np.random.default_rng(0)
    with h5py.File(path, "w") as f:
        g = f.create_group("science/LSAR/GUNW/grids/frequencyA")
        g["xCoordinates"] = np.linspace(-80.9, -80.6, 8)
        g["yCoordinates"] = np.linspace(7.8, 7.4, 8)
        g["projection"] = np.int32(4326)
        u = g.create_group("unwrappedInterferogram/HH")
        for n in ["unwrappedPhase", "coherenceMagnitude", "ionospherePhaseScreen",
                  "ionospherePhaseScreenUncertainty", "mask"]:
            u[n] = rng.random((8, 8)).astype("float32")
        u["connectedComponents"] = np.ones((8, 8), dtype="uint32")
        g.create_group("wrappedInterferogram/HH")["coherenceMagnitude"] = np.ones((16, 16), "float32")
        m = f.create_group("science/LSAR/GUNW/metadata/radarGrid")
        m["losUnitVectorX"] = np.ones((4, 4), "float32")
        m["xCoordinates"] = np.linspace(0, 3, 4)          # radarGrid axes (NOT the 8-pixel grid axes above)
        m["yCoordinates"] = np.linspace(3, 0, 4)
        m["heightAboveEllipsoid"] = np.array([-500.0, 0.0])
        m["projection"] = np.uint32(32629)
        m["hydrostaticTroposphericPhaseScreen"] = np.ones((2, 4, 4), "float32")
        m["wetTroposphericPhaseScreen"] = np.ones((2, 4, 4), "float32")
        if with_tide:
            m["slantRangeSolidEarthTidesPhase"] = np.full((2, 4, 4), -5.5, "float64")


h5a = tmp / "gunw_a.h5"
make_gunw_h5(h5a)
o1 = da.extract(h5a, tmp / "x1" / "GUNW" / "p1", "GUNW")
files1 = {f.name for f in (tmp / "x1" / "GUNW" / "p1").iterdir()}
npz1 = set(np.load(tmp / "x1" / "GUNW" / "p1" / "radar_geometry.npz").files)
check("extract default (no extra): exactly the old outputs, no new layer, wrapped coherence skipped",
      files1 == {"unwrappedInterferogram_HH_unwrappedPhase.tif", "unwrappedInterferogram_HH_coherenceMagnitude.tif",
                 "unwrappedInterferogram_HH_connectedComponents.tif", "unwrappedInterferogram_HH_ionospherePhaseScreen.tif",
                 "radar_geometry.npz"} and len(npz1) == 1, sorted(files1))
o2 = da.extract(h5a, tmp / "x2" / "GUNW" / "p2", "GUNW", extra=True)
d2 = tmp / "x2" / "GUNW" / "p2"
npz2 = set(np.load(d2 / "radar_geometry.npz").files)
rep2 = json.loads((d2 / "_extra_layers.json").read_text())
check("extract extra: ionosphere uncertainty + mask as GeoTIFF, troposphere and tide cubes in the npz, nothing missing",
      (d2 / "unwrappedInterferogram_HH_ionospherePhaseScreenUncertainty.tif").exists()
      and (d2 / "unwrappedInterferogram_HH_mask.tif").exists()
      and any("hydrostaticTroposphericPhaseScreen" in k for k in npz2) and any("wetTroposphericPhaseScreen" in k for k in npz2)
      and "slantRangeSolidEarthTidesPhase" in npz2 and rep2["manquantes"] == [], rep2)
h5b = tmp / "gunw_b.h5"
make_gunw_h5(h5b, with_tide=False)
da.extract(h5b, tmp / "x3" / "GUNW" / "p3", "GUNW", extra=True)
check("extract extra: a requested layer absent from the file is reported, not silently ignored",
      da.extra_missing(tmp / "x3" / "GUNW" / "p3") == ["slantRangeSolidEarthTidesPhase"], da.extra_missing(tmp / "x3" / "GUNW" / "p3"))

row = fake("GUNW", 44, 17, "A", "20260929", "20261011")
row["extra_layers"] = True
data_gunw = Path(os.environ["NISAR_DATA"]) / "GUNW"
n_products = len(catalog.load())
part1 = tmp / "_tmp" / "a.h5.part"
part1.parent.mkdir(parents=True, exist_ok=True)
shutil.copy(h5a, part1)
fin1 = data_gunw / row["name"]
k1 = da.finish(row, part1, fin1, fin1 / "_DONE", keep_raw=True)
raw1 = fin1 / (row["name"] + ".h5")
done1 = json.loads((fin1 / "_DONE").read_text())
check("finish --keep-raw: raw .h5 kept next to the GeoTIFFs, partial file gone, _DONE says raw",
      raw1.exists() and not part1.exists() and done1.get("raw") is True and k1 > raw1.stat().st_size
      and (fin1 / "unwrappedInterferogram_HH_unwrappedPhase.tif").exists(), done1)
catalog.refresh()
p = next((q for q in catalog.load() if q.name == row["name"]), None)
check("catalog still indexes a folder holding raw .h5 + extra layers + _extra_layers.json",
      p is not None and p.level == "GUNW" and p.files["phase"].suffix == ".tif" and len(catalog.load()) == n_products + 1
      and "iono" in p.files and p.files["phase"].name.endswith("unwrappedPhase.tif"), p and p.id)
shutil.rmtree(fin1)
catalog.refresh()
row2 = fake("GUNW", 44, 17, "A", "20260917", "20260929")
part2 = tmp / "_tmp" / "b.h5.part"
shutil.copy(h5a, part2)
fin2 = tmp / "x4" / "GUNW" / row2["name"]
da.finish(row2, part2, fin2, fin2 / "_DONE")
done2 = json.loads((fin2 / "_DONE").read_text())
check("finish without --keep-raw: raw removed, extra layers off (row has no extra_layers), _DONE as before",
      not (fin2 / (row2["name"] + ".h5")).exists() and not part2.exists() and set(done2) == {"kept_bytes", "at"}
      and not (fin2 / "_extra_layers.json").exists())
# --- safety net: a missing extra layer must never cost us the raw file --------------------------
row3 = fake("GUNW", 44, 17, "A", "20260905", "20260917")
row3["extra_layers"] = True
part3 = tmp / "_tmp" / "c.h5.part"
shutil.copy(h5b, part3)                                  # h5b has no slantRangeSolidEarthTidesPhase
fin3 = tmp / "x5" / "GUNW" / row3["name"]
k3 = da.finish(row3, part3, fin3, fin3 / "_DONE")        # no --keep-raw
raw3 = fin3 / (row3["name"] + ".h5")
done3 = json.loads((fin3 / "_DONE").read_text())
check("safety net: missing extra layer -> raw .h5 kept WITHOUT --keep-raw, _DONE lists the missing name",
      raw3.exists() and not part3.exists() and done3.get("raw_kept_missing_layers") == ["slantRangeSolidEarthTidesPhase"]
      and done3.get("raw") is True and k3 > raw3.stat().st_size, done3)
check("safety net: the warning names the missing layer and the kept raw file",
      "solidEarthTide" in da.missing_warning(["solidEarthTide"], raw3) and raw3.name in da.missing_warning(["solidEarthTide"], raw3)
      and "inconnu" in da.missing_warning(["?"], raw3))
row4 = fake("GUNW", 44, 17, "A", "20260824", "20260905")
row4["extra_layers"] = True
part4 = tmp / "_tmp" / "d.h5.part"
shutil.copy(h5a, part4)                                  # h5a has every extra layer
fin4 = tmp / "x6" / "GUNW" / row4["name"]
da.finish(row4, part4, fin4, fin4 / "_DONE")
done4 = json.loads((fin4 / "_DONE").read_text())
check("safety net: all extra layers present and no --keep-raw -> raw deleted, no marker",
      not (fin4 / (row4["name"] + ".h5")).exists() and not part4.exists() and "raw_kept_missing_layers" not in done4
      and set(done4) == {"kept_bytes", "at"}, done4)
bad_dir = tmp / "x7"
bad_dir.mkdir()
(bad_dir / "_extra_layers.json").write_text("{not json")
check("extra_missing: unreadable report -> [\"?\"]; absent report -> [\"?\"] if required, [] if not",
      da.extra_missing(bad_dir) == ["?"] and da.extra_missing(tmp / "x7b") == []
      and da.extra_missing(tmp / "x7b", required=True) == ["?"])
real_extract = da.extract


def extract_then_corrupt(h5_path, out_dir, level, extra=False):
    k = real_extract(h5_path, out_dir, level, extra=extra)
    (Path(out_dir) / "_extra_layers.json").write_text("{not json")
    return k


da.extract = extract_then_corrupt
try:
    row5 = fake("GUNW", 44, 17, "A", "20260812", "20260824")
    row5["extra_layers"] = True
    part5 = tmp / "_tmp" / "e.h5.part"
    shutil.copy(h5a, part5)
    fin5 = tmp / "x8" / "GUNW" / row5["name"]
    da.finish(row5, part5, fin5, fin5 / "_DONE")
finally:
    da.extract = real_extract
done5 = json.loads((fin5 / "_DONE").read_text())
check("safety net: unreadable _extra_layers.json also keeps the raw .h5",
      (fin5 / (row5["name"] + ".h5")).exists() and done5.get("raw_kept_missing_layers") == ["?"], done5)
rows_sp = [fake("GUNW", 1, 1, "A", "20260101", "20260113"), fake("SME2", 1, 1, "A", "20260101", "20260101")]
base_need = da.space_needed(rows_sp, 3)
check("free-disk check: --keep-raw adds the raw GUNW size (not SME2, which is kept whole anyway)",
      base_need == 3 * 3e9 + 5e9 and da.space_needed(rows_sp, 3, True) == base_need + 2_000_000_000)

# --- HTTP 416 on resume: the partial file is already complete -----------------------------------
class FakeResp:
    def __init__(self, status, body=b"", headers=None):
        self.status_code, self.body, self.headers = status, body, headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise da.requests.HTTPError(str(self.status_code))

    def iter_content(self, chunk_size=0):
        if self.body:
            yield self.body


class FakeSession:
    def __init__(self, *resps):
        self.resps, self.calls = list(resps), []

    def get(self, url, headers=None, stream=True, timeout=None):
        self.calls.append(dict(headers or {}))
        return self.resps.pop(0)


def run_download(resps, size, have_bytes):
    p = tmp / "_tmp" / f"r416_{len(resps)}_{size}_{have_bytes}.part"
    p.write_bytes(b"x" * have_bytes)
    moved = []
    s = FakeSession(*resps)
    da.download(s, {"url": "u", "size": size}, p, moved.append, tries=2)
    return p, s, sum(moved)


p1, s1, _ = run_download([FakeResp(416, headers={"Content-Range": "bytes */1000"})], 0, 1000)
check("download 416 + Content-Range equal to the partial size: treated as complete, one request, file untouched",
      p1.stat().st_size == 1000 and len(s1.calls) == 1 and s1.calls[0] == {"Range": "bytes=1000-"})
p2, s2, _ = run_download([FakeResp(416)], 0, 1000)
check("download 416 without Content-Range: treated as complete (finish() will verify)",
      p2.stat().st_size == 1000 and len(s2.calls) == 1)
p3, s3, net = run_download([FakeResp(416, headers={"Content-Range": "bytes */500"}), FakeResp(200, b"y" * 500)], 0, 1000)
check("download 416 saying a different size: partial dropped, file restarted from zero",
      p3.read_bytes() == b"y" * 500 and len(s3.calls) == 2 and s3.calls[1] == {} and net == -500, (p3.stat().st_size, net))
p4, s4, _ = run_download([FakeResp(206, b"z" * 400, {})], 1000, 600)
check("download resume still works: 206 appends the missing bytes with a Range header",
      p4.stat().st_size == 1000 and s4.calls == [{"Range": "bytes=600-"}])

# --- tools/list_h5_layers.py -----------------------------------------------------------------
lst = subprocess.run([sys.executable, str(ROOT.parent / "tools" / "list_h5_layers.py"), str(h5a), "TROPO", "Tide"],
                     capture_output=True, text=True)
allp = subprocess.run([sys.executable, str(ROOT.parent / "tools" / "list_h5_layers.py"), str(h5a)], capture_output=True, text=True)
nofile = subprocess.run([sys.executable, str(ROOT.parent / "tools" / "list_h5_layers.py"), str(tmp / "absent.h5")],
                        capture_output=True, text=True)
check("list_h5_layers: case-insensitive keyword filter prints path, shape, dtype; no keyword lists everything; bad file fails",
      lst.returncode == 0 and len(lst.stdout.strip().splitlines()) == 3 and "shape=(2, 4, 4)" in lst.stdout
      and "dtype=float32" in lst.stdout and "mask" not in lst.stdout.lower()
      and len(allp.stdout.strip().splitlines()) == 18 and nofile.returncode == 1, (len(lst.stdout.splitlines()), len(allp.stdout.splitlines())))

# --- radar_geometry.npz: axes + tide cube under short names, six old keys unchanged -------------------
LONG = "science__LSAR__GUNW__metadata__radarGrid__"
with np.load(d2 / "radar_geometry.npz") as z2:
    keys2 = set(z2.files)
    x_shape, proj, tide = z2["xCoordinates"].shape, int(z2["projection"]), z2["slantRangeSolidEarthTidesPhase"]
check("npz (extra): the 3 long keys unchanged + 4 axes and the tide cube under short names, nothing else",
      keys2 == {LONG + "losUnitVectorX", LONG + "hydrostaticTroposphericPhaseScreen", LONG + "wetTroposphericPhaseScreen",
                "heightAboveEllipsoid", "xCoordinates", "yCoordinates", "projection", "slantRangeSolidEarthTidesPhase"}, sorted(keys2))
check("npz (extra): axes come from radarGrid (4 values), not from the 8-pixel grid; projection and tide values intact",
      x_shape == (4,) and proj == 32629 and tide.shape == (2, 4, 4) and float(tide[0, 0, 0]) == -5.5)
check("_extra_layers.json: the tide cube and the axes are reported found, nothing missing",
      {"slantRangeSolidEarthTidesPhase", "xCoordinates", "heightAboveEllipsoid"} <= set(rep2["trouvees"])
      and "solidEarthTide" not in rep2["demandees"] and rep2["manquantes"] == [], rep2)
# default extraction (no extra layers) must select exactly what the old rule selected
legacy = {}
with h5py.File(h5a, "r") as hh:
    def _legacy(name, obj):
        base = name.split("/")[-1]
        if (isinstance(obj, h5py.Dataset) and not ("wrappedInterferogram" in name and "unwrappedInterferogram" not in name)
                and not (base in da.LAYERS["GUNW"] and obj.ndim == 2)
                and any(k in base for k in da.META_KEYWORDS) and obj.size < 50_000_000):
            legacy[name.replace("/", "__")] = obj[()]
    hh.visititems(_legacy)
    now, _seen = da.scan_geometry(hh, "GUNW", False)
check("npz (default, no extra): same keys and values as the legacy selection rule (default extraction unchanged)",
      set(now) == set(legacy) and all(np.array_equal(now[k], legacy[k]) for k in now) and _seen == set(), sorted(now))

# --- rebuild-npz: from kept raw files, offline, nothing deleted ---------------------------------------
rb_root = tmp / "rb"
rows_rb = []
for i, (ref, sec) in enumerate([("20260101", "20260113"), ("20260113", "20260125")]):
    r_ = fake("GUNW", 44, 17, "A", ref, sec)
    r_["extra_layers"] = True
    pt = tmp / "_tmp" / f"rb{i}.h5.part"
    shutil.copy(h5a, pt)
    da.finish(r_, pt, rb_root / "GUNW" / r_["name"], rb_root / "GUNW" / r_["name"] / "_DONE", keep_raw=True)
    rows_rb.append(r_)
f1_ = rb_root / "GUNW" / rows_rb[0]["name"]
f2_ = rb_root / "GUNW" / rows_rb[1]["name"]
with np.load(f1_ / "radar_geometry.npz") as z_:                      # downgrade folder 1 to the OLD state on disk
    old_long = {k: z_[k] for k in z_.files if k.startswith(LONG) and k.endswith(("losUnitVectorX", "PhaseScreen"))}
np.savez_compressed(str(f1_ / "radar_geometry.npz")[:-4], **old_long)
(f1_ / "_extra_layers.json").write_text(json.dumps({"demandees": ["solidEarthTide"], "trouvees": [], "manquantes": ["solidEarthTide"]}))
(f1_ / "_DONE").write_text(json.dumps({"kept_bytes": 1, "at": "x", "raw": True, "raw_kept_missing_layers": ["solidEarthTide"]}))
raw_f1 = f1_ / (rows_rb[0]["name"] + ".h5")
raw_sha = hashlib.sha256(raw_f1.read_bytes()).hexdigest()
npz_before = (f1_ / "radar_geometry.npz").read_bytes()
no_raw = rb_root / "GUNW" / "NISAR_noraw"
no_raw.mkdir()
(no_raw / "_DONE").write_text("{}")
not_done = rb_root / "GUNW" / "NISAR_notdone"
not_done.mkdir()
(not_done / (not_done.name + ".h5")).write_bytes(b"x")
broken = rb_root / "GUNW" / "NISAR_broken"
broken.mkdir()
(broken / "_DONE").write_text("{}")
(broken / "NISAR_broken.h5").write_bytes(b"not an hdf5 file")
(broken / "radar_geometry.npz").write_bytes(b"keep me")
dry = {r["name"]: r for r in da.rebuild_npz(rb_root, dry_run=True)}
check("rebuild-npz --dry-run: reports what would change and writes nothing",
      "dry-run" in dry[rows_rb[0]["name"]]["status"] and (f1_ / "radar_geometry.npz").read_bytes() == npz_before
      and "slantRangeSolidEarthTidesPhase" in dry[rows_rb[0]["name"]]["ajoutes"]
      and json.loads((f1_ / "_DONE").read_text()).get("raw_kept_missing_layers") == ["solidEarthTide"])
real = {r["name"]: r for r in da.rebuild_npz(rb_root)}
with np.load(f1_ / "radar_geometry.npz") as z_:
    rebuilt = {k: z_[k] for k in z_.files}
done_rb = json.loads((f1_ / "_DONE").read_text())
rep_rb = json.loads((f1_ / "_extra_layers.json").read_text())
check("rebuild-npz: old keys kept with identical values, axes + tide cube added, report and _DONE corrected",
      real[rows_rb[0]["name"]]["status"] == "reconstruit" and set(rebuilt) == keys2
      and all(np.array_equal(rebuilt[k], v) for k, v in old_long.items())
      and rep_rb["manquantes"] == [] and "raw_kept_missing_layers" not in done_rb and done_rb["raw"] is True
      and "npz_rebuilt_at" in done_rb, sorted(set(rebuilt) ^ keys2))
check("rebuild-npz: the raw .h5 is untouched (same bytes); no temp file left behind",
      raw_f1.exists() and hashlib.sha256(raw_f1.read_bytes()).hexdigest() == raw_sha
      and not list(f1_.glob("*.tmp")) and not (f1_ / "radar_geometry.tmp").exists())
check("rebuild-npz: a product that is already up to date is left alone; second run is a no-op",
      real[rows_rb[1]["name"]]["status"] == "à jour"
      and {r["status"] for r in da.rebuild_npz(rb_root) if r["name"] in (rows_rb[0]["name"], rows_rb[1]["name"])} == {"à jour"})
check("rebuild-npz: folders without raw .h5 or without _DONE are skipped; an unreadable raw file is an error and its npz is kept",
      real["NISAR_noraw"]["status"].startswith("ignoré") and real["NISAR_notdone"]["status"].startswith("ignoré")
      and real["NISAR_broken"]["status"].startswith("erreur") and (broken / "radar_geometry.npz").read_bytes() == b"keep me"
      and (broken / "NISAR_broken.h5").exists())
cli = subprocess.run([sys.executable, str(ROOT.parent / "download_all.py"), "rebuild-npz", "--out", str(rb_root), "--dry-run"],
                     capture_output=True, text=True)
check("download_all rebuild-npz CLI: runs offline without a token or a plan; exit code 1 only because of the broken test folder",
      cli.returncode == 1 and "dry-run" in cli.stdout and "erreur" in cli.stdout and "reconstruits" in cli.stdout, cli.stdout[-200:])

check("plan_nisar.json still byte-identical after all Morocco checks",
      hashlib.sha256(PLAN_NISAR.read_bytes()).hexdigest() == sha_before)

n_ok = sum(ok for _, ok in results)
print(f"\n{n_ok}/{len(results)} checks passed")
sys.exit(0 if n_ok == len(results) else 1)
