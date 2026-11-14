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

import config as _config  # noqa: E402

_config.DISCOVERIES_ENABLED = True              # discoveries are off by default: switch them on for these checks only
d = c.get("/discoveries", params={"refresh": True, "exposure": False}).json()
_config.DISCOVERIES_ENABLED = False
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
      "cohérence radar" in verdicts["fr"]["verdict"] and "radar coherence" in verdicts["en"]["verdict"]
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
      all(k in contract for k in ("surface_change", "context", "crid", "maturity", "event_time", "haouz-flood-2026-10-10",
                                  "coverage_5km", "baseline_loss_mean", "baseline_changed_km2", "frame_loss_mean",
                                  "frame_frac_changed", "excess_level", "borderline", "not usable", "null_limits",
                                  "true 5 km radius circle"))
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

# --- surface change: true 5 km circle, baseline pair, frame background, usability rules --------------------
import numpy as _np  # noqa: E402
import raster as _raster  # noqa: E402

KH = (32.88, -6.91)
kh_all = catalog.find(*KH, "GUNW")
res = _damage.analyze(kh_all, *KH, EV, "day")
G = {g["track"]: g for g in res["geometries"]}
check("surface change: nine geometries listed; usable = good, degraded-before, corner-patch, borderline, quiet; "
      "not usable = no baseline, edge of the array, never coherent, baseline pair not measurable",
      res["n_geometries"] == 9 and res["n_usable_geometries"] == 5
      and [t for t in sorted(G) if G[t]["usable"]] == [60, 61, 65, 66, 67], {t: G[t]["usable"] for t in G})
check("surface change: 'not usable: <reason>' names the failing rule and carries no change number",
      G[62]["reason"].startswith("not usable:") and "no earlier pair" in G[62]["reason"]
      and "not covered" in G[63]["reason"] and G[63]["coverage_5km"] < 0.9
      and "less than half" in G[64]["reason"] and G[64]["coherent_before_fraction_5km"] < 0.5
      and "baseline pair cannot be measured" in G[68]["reason"] and G[68]["baseline_loss_mean"] is None
      and all(G[t][k] is None for t in (62, 63, 64, 68)
              for k in ("loss_at_point", "loss_mean_5km", "changed_km2_5km", "baseline_loss_mean", "frame_loss_mean")), G[63]["reason"])
only_bad = _damage.analyze([p for p in kh_all if p.track in (62, 63, 64)], *KH, EV, "day")
check("surface change: when no geometry is usable the recipe returns the error 'not usable: ...' and no number at all",
      only_bad.get("error", "").startswith("not usable:") and "loss_at_point" not in only_bad
      and only_bad["n_usable_geometries"] == 0 and len(only_bad["geometries"]) == 3, only_bad.get("error"))
g = G[60]
check("surface change: coverage_5km, baseline and frame-background facts are present and sensible on the good geometry",
      g["coverage_5km"] >= 0.99 and abs(g["baseline_loss_mean"]) < 0.05 and g["baseline_changed_km2"] < 0.1
      and g["changed_km2_5km"] > 1 and g["frame_loss_mean"] < 0.05 and g["frame_frac_changed"] < 0.05
      and g["baseline_pair"] and res["excess_margin"] == _damage.EXCESS_MARGIN, g)
check("surface change: local excess = circle mean loss above the frame mean by more than the margin (and not otherwise)",
      g["local_excess"] is True and g["excess_over_frame"] > _damage.EXCESS_MARGIN
      and g["excess_over_frame"] == round(g["loss_mean_5km"] - g["frame_loss_mean"], 3)
      and _damage.analyze([p for p in kh_all if p.track in (60,)], *KH, EV, "day")["local_excess"] is True)
check("surface change: baseline unreliable when the before pair is >0.1 below the median of the geometry's other pairs",
      G[61]["baseline_unreliable"] is True and G[60]["baseline_unreliable"] is False
      and G[61]["pair_coherence_mean"] < G[61]["other_pairs_coherence_median"] - 0.1, (G[61]["pair_coherence_mean"], G[61]["other_pairs_coherence_median"]))
cp = _damage.analyze([p for p in kh_all if p.track == 65], *KH, EV, "day")
b65, c65 = [p for p in kh_all if p.track == 65 and p.id == cp["pre_pair"]][0], [p for p in kh_all if p.id == cp["co_pair"]][0]
cb_, prof_ = _raster.read(b65.files["coherence"])
ca_, _ = _raster.read(c65.files["coherence"])
ls_ = _np.where(cb_ >= 0.4, cb_ - ca_, _np.nan)
sq_ = _raster.window(ls_, prof_, *KH, 5000)
square_km2 = float(_np.nansum(sq_ > 0.3) * (_raster.pixel_size_m(prof_) / 1000) ** 2)
check("surface change: the area is a true 5 km radius circle (a patch in the corner of the old 10x10 km square is not counted)",
      square_km2 > 1.0 and cp["changed_km2_5km"] < 0.3, (square_km2, cp["changed_km2_5km"]))
fh = c.post("/ask", json={"question": Q_HAOUZ}).json()["facts"]
check("surface change: the facts reach the Haouz answer (new keys present, old key names unchanged)",
      all(k in fh for k in ("coverage_5km", "baseline_loss_mean", "baseline_changed_km2", "frame_loss_mean",
                           "frame_frac_changed", "changed_km2_5km", "loss_at_point", "coherent_before_fraction_5km")))

# --- three bands: local excess (>= 0.15), borderline (0.11 to 0.15), no clear change (< 0.11) ---------------
check("surface change: excess bands use the stated margins; only the strong band sets local_excess",
      _damage.EXCESS_MARGIN == 0.11 and _damage.EXCESS_STRONG == 0.15
      and G[60]["excess_level"] == "strong" and G[60]["excess_over_frame"] >= 0.15 and G[60]["local_excess"] is True
      and G[66]["excess_level"] == "borderline" and 0.11 <= G[66]["excess_over_frame"] < 0.15 and G[66]["local_excess"] is False
      and G[67]["excess_level"] == "none" and G[67]["excess_over_frame"] < 0.11 and G[67]["local_excess"] is False,
      {t: (G[t]["excess_over_frame"], G[t]["excess_level"]) for t in (60, 66, 67)})
check("surface change: the limits of the no-event reference are in the facts (one geometry, one season, random circles)",
      res["null_false_alarm"] == 0.01 and res["null_false_alarm_pct"] == 1 and res["excess_margin"] == 0.11
      and res["excess_strong"] == 0.15 and len(res["null_limits"]) == 3
      and "one viewing geometry" in res["null_limits"][0] and "one season" in res["null_limits"][1]
      and "random" in res["null_limits"][2], res["null_limits"])


def level_answer(track):
    fx = _damage.analyze([p for p in kh_all if p.track == track], *KH, EV, "day")
    return fx, {lg: agent.template("surface_change", fx, lg) for lg in ("fr", "en", "ar")}, agent.assess("surface_change", fx, [])


fx60, tx60, as60 = level_answer(60)
fx66, tx66, as66 = level_answer(66)
fx67, tx67, as67 = level_answer(67)
check("surface change wording, strong band: 'local excess', medium confidence, orange, in FR/EN/AR, no cause or damage claimed",
      "Excès local" in tx60["fr"] and "Local excess" in tx60["en"] and "فائض محلي" in tx60["ar"]
      and as60[0] == "medium" and as60[2] == "orange" and "borderline" not in tx60["en"])
check("surface change wording, borderline band: 'just above the no-event level', low confidence, yellow, no cause, FR/EN/AR",
      "cas limite" in tx66["fr"] and "borderline" in tx66["en"] and "just above" in tx66["en"] and "حالة حدّية" in tx66["ar"]
      and "no cause can be given" in tx66["en"] and "aucune cause" in tx66["fr"] and "Local excess" not in tx66["en"]
      and as66[0] == "low" and as66[2] == "yellow", (as66[0], as66[2]))
check("surface change wording, below the margin: 'no clear local change', no alert, FR/EN/AR",
      "Pas de changement local net" in tx67["fr"] and "No clear local change" in tx67["en"] and "لا تغيّر محلي واضح" in tx67["ar"]
      and as67[2] == "none" and "Local excess" not in tx67["en"] and "borderline" not in tx67["en"])
check("surface change wording: every sentence states the limits of the no-event reference (FR/EN/AR)",
      all("une seule géométrie" in t["fr"] and "one viewing geometry" in t["en"] and "هندسة رؤية واحدة" in t["ar"]
          for t in (tx60, tx66, tx67)))
check("surface change wording: every number of every sentence in every band and language comes from the facts",
      all(not stray_numbers(t[lg], fx) for fx, t in ((fx60, tx60), (fx66, tx66), (fx67, tx67)) for lg in ("fr", "en", "ar")),
      [(lg, stray_numbers(t[lg], fx)) for fx, t in ((fx60, tx60), (fx66, tx66), (fx67, tx67)) for lg in ("fr", "en", "ar")])
fx61, tx61, as61 = level_answer(61)
check("surface change wording: an unreliable baseline is said in FR/EN/AR and caps confidence at low (yellow, not orange)",
      fx61["baseline_unreliable"] is True and "n'est pas fiable" in tx61["fr"] and "baseline is unreliable" in tx61["en"]
      and "غير موثوق" in tx61["ar"] and as61[0] == "low" and as61[2] == "yellow"
      and "baseline_unreliable" not in str(tx60["en"]) and "unreliable" not in tx60["en"], (as61[0], as61[2]))
check("surface change: the loss at the point stays a fact and is not in the sentence",
      fx60["loss_at_point"] is not None and f"{fx60['loss_at_point']:.2f}" not in tx60["en"]
      and "at the point" not in tx60["en"].split("Local excess")[0])
check("surface change: a reliable baseline is preferred when choosing the main geometry",
      _damage.analyze([p for p in kh_all if p.track in (60, 61)], *KH, EV, "day")["track"] == 60
      and res["geometries_agree"] is False)
_find = catalog.find
catalog.find = lambda lat, lon, level=None, *a, **k: [p for p in _find(lat, lon, level, *a, **k) if p.track in (62, 63, 64, 68)]
try:
    rn = agent.investigate("Le sol a-t-il changé à Khouribga lors de la crue éclair du 10 octobre 2026 ?", lat=KH[0], lon=KH[1], lang="en")
finally:
    catalog.find = _find
check("surface change: no usable geometry gives 'not usable: <reason>', no number, no alert, through the whole answer",
      rn["type"] == "surface_change" and "not usable:" in rn["verdict"] and "km²" not in rn["verdict"]
      and "loss_mean_5km" not in rn["facts"] and rn["confidence"] == "low" and rn["alert_level"] in ("none", "yellow"),
      rn["verdict"])
mf = _mock.SURFACE_CHANGE["facts"]
check("mock: surface-change facts, confidence, reasons and alert are exactly what assess() gives (the mock cannot drift)",
      (_mock.SURFACE_CHANGE["confidence"], _mock.SURFACE_CHANGE["confidence_reasons"], _mock.SURFACE_CHANGE["alert_level"])
      == agent.assess("surface_change", mf, []) and mf["excess_level"] == "strong"
      and all(not stray_numbers(agent.template("surface_change", mf, lg), mf) for lg in ("fr", "en", "ar")))

# --- entry points that print verdicts must survive a non-UTF-8 stdout (redirected output on Windows) ---------
env_ascii = {k: v for k, v in os.environ.items() if k != "PYTHONUTF8"}
env_ascii["PYTHONIOENCODING"] = "ascii"
out_b = subprocess.run([sys.executable, str(ROOT / "precompute.py"), "--no-exposure"], cwd=ROOT, capture_output=True, env=env_ascii)
txt_b = out_b.stdout.decode("utf-8", "strict")
check("precompute prints French/Arabic verdicts even when stdout is ascii (exit 0, output is UTF-8)",
      out_b.returncode == 0 and "é" in txt_b and "→" in txt_b, out_b.stderr[-200:].decode("utf-8", "replace"))
check("every entry point that prints reconfigures stdout (precompute.py, train_classifier.py)",
      all('sys.stdout.reconfigure(encoding="utf-8", errors="replace")' in (ROOT / n).read_text(encoding="utf-8")
          for n in ("precompute.py", "train_classifier.py")))

# =============================================================================================================
# Discoveries off by default, unvalidated candidates, sign unverified, data gap / reference / ionosphere, soil-moisture
# uncertainty, event status.   (Synthetic: logic only, not physics.)
# =============================================================================================================
import dataclasses as _dc  # noqa: E402

from recipes import displacement as _disp  # noqa: E402
from recipes import soil_moisture as _sm  # noqa: E402
import discoveries as _disc  # noqa: E402

# --- 1. discoveries ---------------------------------------------------------------------------------------------
check("discoveries are disabled by default (config.DISCOVERIES_ENABLED is False)", _config.DISCOVERIES_ENABLED is False)
(_config.CACHE_DIR / "discoveries.json").write_text(
    json.dumps({"schema": 2, "enabled": True, "zones": [{"id": "zone-1", "confidence": "high", "alert_level": "orange"}]}), encoding="utf-8")
off = c.get("/discoveries").json()
off_r = c.get("/discoveries", params={"refresh": True}).json()
check("discoveries off: the API returns an empty list with a reason, with or without refresh, and never an old cache",
      off["zones"] == [] and off["enabled"] is False and "disabled" in off["reason"] and off_r["zones"] == []
      and off["label"] == "unvalidated candidate" and _disc.cached()["zones"] == [])
_config.DISCOVERIES_ENABLED = True
on = c.get("/discoveries", params={"refresh": True, "exposure": False}).json()
_config.DISCOVERIES_ENABLED = False
check("discoveries on: every zone is an 'unvalidated candidate', confidence low, alert yellow (never high, orange or red)",
      on["enabled"] is True and on["zones"] and all(z["label"] == "unvalidated candidate" and z["confidence"] == "low"
                                                    and z["alert_level"] == "yellow" for z in on["zones"]),
      [(z["confidence"], z["alert_level"]) for z in on["zones"][:3]])


def _prof(n=200):
    from rasterio.transform import from_origin
    return dict(transform=from_origin(500000.0, 3500000.0, 80.0, 80.0), crs="EPSG:32629", width=n, height=n)


# a 40x40 px block of -60 cm (about 5 fringes) in the middle of a quiet 200x200 map
rng_t = _np.random.default_rng(3)
arr_t = rng_t.normal(0, 0.5, (200, 200)).astype("float32")
arr_t[80:120, 80:120] = -60.0
cc_one = _np.ones((200, 200), "uint32")
z_one, _ = _disc._zones(arr_t.copy(), _prof(), "cm", "pair a→b", (23, 73, "P05023"), "descending", cc=cc_one)
cc_two = cc_one.copy()
cc_two[:, 100:] = 2                                        # the block spans two connected components
z_two, _ = _disc._zones(arr_t.copy(), _prof(), "cm", "pair a→b", (23, 73, "P05023"), "descending", cc=cc_two)
zt = z_one[0]
check("discoveries: fringes = |cm| / 11.92 and the area is reported (a 60 cm block is 3 to 5 fringes after smoothing)",
      abs(zt["fringes"] - abs(zt["mean"]) / 11.92) < 0.06 and 3 < zt["fringes"] < 5.2 and zt["area_km2"] > 5, (zt["fringes"], zt["area_km2"]))
check("discoveries: one connected component is detected, and a zone that spans two is flagged",
      zt["in_one_component"] is True and zt["n_components"] == 1
      and z_two[0]["in_one_component"] is False and z_two[0]["n_components"] == 2 and z_two[0]["main_component_share"] < 0.95)
zt["track"], zt["frame"], zt["direction"] = 23, 73, "descending"
mk = lambda geom, v: {"arr": _np.full((200, 200), v, "float32"), "prof": _prof(), "sigma": 1.0, "med": 0.0, "geom": geom,  # noqa: E731
                      "direction": "ascending", "unit": "cm"}
own, other_yes, other_no = mk((23, 73, "P05023"), -60.0), mk((44, 17, "P05023"), -50.0), mk((95, 73, "P05023"), 0.0)
za, zb, zc = dict(zt), dict(zt), dict(zt)
_disc._other_geometries(za, [own])
_disc._other_geometries(zb, [own, other_yes])
_disc._other_geometries(zc, [own, other_no])
check("discoveries: the zone's own geometry is never a second opinion; another geometry that shows it confirms it",
      za["second_geometry_shows"] is None and za["n_other_geometries_covering"] == 0
      and zb["second_geometry_shows"] is True and zb["other_geometries_showing"][0]["track"] == 44
      and zc["second_geometry_shows"] is False and zc["n_other_geometries_covering"] == 1)
check("discoveries: a zone of one fringe or more in one pair is flagged as not physical",
      any("fringes in a single pair" in f for f in _disc._flags({**za, "in_frame_main_component": True})), _disc._flags(za))

# --- 2. signed line-of-sight answers: sign unverified until STATUS H4 is closed -------------------------------------
check("LOS_SIGN_VERIFIED is False by default (STATUS H4 open)", _config.LOS_SIGN_VERIFIED is False)
Q_PAN = "Y a-t-il eu un mouvement du sol après le séisme du Panama ?"
lat_p, lon_p = 7.59 + 1 / 111, -80.77 + 1 / 110
un = {lg: agent.investigate(Q_PAN, lat_p, lon_p, lg, "2026-10-09") for lg in ("fr", "en", "ar")}
check("sign unverified: sudden motion says 'uncorrected line-of-sight change, sign unverified' (FR/EN/AR), confidence low, no alert",
      un["en"]["type"] == "sudden_motion" and "Uncorrected line-of-sight change, sign unverified" in un["en"]["verdict"]
      and "Variation de ligne de visée non corrigée, signe non vérifié" in un["fr"]["verdict"]
      and "الإشارة غير متحقَّق منها" in un["ar"]["verdict"]
      and all(u["confidence"] == "low" and u["alert_level"] == "none" for u in un.values())
      and any("LOS sign unverified" in x for x in un["en"]["confidence_reasons"]), (un["en"]["confidence"], un["en"]["alert_level"]))
check("sign unverified: ionosphere and troposphere are stated (no screen in the synthetic products -> 'not corrected')",
      "Ionosphere and troposphere: not corrected" in un["en"]["verdict"] and "Ionosphère et troposphère : non corrigées" in un["fr"]["verdict"]
      and un["en"]["facts"]["iono_screen"] == "not applied" and un["en"]["facts"]["troposphere_corrected"] is False)
_config.LOS_SIGN_VERIFIED = True
ver = agent.investigate(Q_PAN, lat_p, lon_p, "en", "2026-10-09")
_config.LOS_SIGN_VERIFIED = False
check("sign verified (flag on): the old sentence and the normal confidence rules come back",
      "sign unverified" not in ver["verdict"] and ver["confidence"] in ("medium", "high") and ver["facts"]["sign_verified"] is True,
      (ver["confidence"], ver["alert_level"]))

# --- 3. Al Wahda: data gap, reference component, ionosphere -------------------------------------------------------------
AL_ps = catalog.find(*AL, "GUNW")
s0 = _ts.point_series(AL_ps, *AL)[0]
check("time series: no data gap crossed and the reference shares the point's component on the synthetic stack",
      s0["crosses_data_gap"] is False and s0["n_pairs_across_gap"] == 0 and s0["reference_same_component"] is True
      and s0["n_pairs_reference_other_component"] == 0 and s0["iono_screen"] == "not applied" and s0["troposphere_corrected"] is False)
_gap = _ts.DATA_GAPS
_ts.DATA_GAPS = [("20260705", "20260715")]                 # a pair that starts before and ends after this window crosses it
s1 = _ts.point_series(AL_ps, *AL)[0]
_ts.DATA_GAPS = _gap
check("time series: a pair that starts before and ends after the gap is counted as crossing it",
      s1["crosses_data_gap"] is True and s1["n_pairs_across_gap"] >= 1 and s1["data_gaps_crossed"] == [["20260705", "20260715"]], s1["n_pairs_across_gap"])
_ts.DATA_GAPS = [("20260705", "20260715")]
rg = {lg: agent.investigate("Le barrage Al Wahda se déforme-t-il depuis juin ?", *AL, lg) for lg in ("fr", "en", "ar")}
_ts.DATA_GAPS = _gap
check("Al Wahda sentence: says the chain crosses the data gap, in the three languages, with the pair count from the facts",
      "crosses the data gap" in rg["en"]["verdict"] and "traverse la lacune de données" in rg["fr"]["verdict"]
      and "فجوة البيانات" in rg["ar"]["verdict"] and rg["en"]["facts"]["crosses_data_gap"] is True
      and rg["en"]["confidence"] == "low" and rg["en"]["alert_level"] == "none"
      and "Uncorrected line-of-sight change, sign unverified" in rg["en"]["verdict"])
ap = AL_ps[0]
_cc_keep = _disp._components_raster
_disp._components_raster = lambda p: _np.ones((600, 600), "uint32")
ref_ok = _disp.analyze(ap, *AL, make_layer=False)
_far = _np.ones((600, 600), "uint32")
_ii, _jj = _np.ogrid[:600, :600]
_far[_np.hypot(_ii - 300, _jj - 300) * 80 > 8000] = 2     # the point is in component 1, everything beyond 8 km in component 2
_disp._components_raster = lambda p: _far
ref_bad = _disp.analyze(ap, *AL, make_layer=False)
_disp._components_raster = _cc_keep
check("reference component: shared -> reference_same_component True; reference in another component -> False, with the share",
      ref_ok["reference_same_component"] is True and ref_ok["reference_share_in_point_component"] == 1.0
      and ref_bad["reference_same_component"] is False and ref_bad["reference_share_in_point_component"] < 0.9
      and ref_bad["point_component"] == 1, (ref_ok["reference_share_in_point_component"], ref_bad["reference_share_in_point_component"]))
f_ref = {**rg["en"]["facts"], "reference_same_component": False, "n_pairs_reference_other_component": 3}
sent_ref = {lg: agent.template("slow_motion", f_ref, lg) for lg in ("fr", "en", "ar")}
check("reference in another component: said in FR/EN/AR and the confidence is capped at low",
      "not in the same connected component" in sent_ref["en"] and "pas dans la même composante connexe" in sent_ref["fr"]
      and "ليست في المركّبة المتصلة نفسها" in sent_ref["ar"]
      and agent.assess("slow_motion", {**f_ref, "sign_verified": True}, [])[0] == "low")
f_one = {**rg["en"]["facts"], "n_pairs_across_gap": 1}
check("one bridging pair is said in the singular (FR/EN/AR)",
      "1 pair bridges it" in agent.template("slow_motion", f_one, "en") and "1 paire l'enjambe" in agent.template("slow_motion", f_one, "fr")
      and "زوج واحد يعبرها" in agent.template("slow_motion", f_one, "ar"))
f_iono = {**rg["en"]["facts"], "iono_screen": "subtracted"}
check("ionosphere screen subtracted: the sentence says so (not validated) in FR/EN/AR; troposphere is never corrected",
      "screen is subtracted (not validated); troposphere: not corrected" in agent.template("slow_motion", f_iono, "en")
      and "écran du produit soustrait (non validé)" in agent.template("slow_motion", f_iono, "fr")
      and "خُصمت شاشة المنتج" in agent.template("slow_motion", f_iono, "ar"))

# --- 4. soil moisture: a change inside the retrieval uncertainty is not a change -------------------------------------------
sm_all = catalog.find(34.5, -6.0, "SME2")
sm_few = sorted(sm_all, key=lambda p: p.ref)[2:4]          # two close passes: small anomaly
r_all = _sm.analyze(sm_all, 34.5, -6.0)
r_few = _sm.analyze(sm_few, 34.5, -6.0)
check("soil moisture: the product's own uncertainty layer is read; a large change is outside it, a small one inside",
      r_all["uncertainty_m3m3"] == 0.04 and r_all["within_uncertainty"] is False and abs(r_all["anomaly_m3m3"]) > 0.04
      and r_few["within_uncertainty"] is True and abs(r_few["anomaly_m3m3"]) < 0.04, (r_all["anomaly_m3m3"], r_few["anomaly_m3m3"]))
_unc = _sm._uncertainty
_sm._uncertainty = lambda *a, **k: None
r_fb = _sm.analyze(sm_all, 34.5, -6.0)
_sm._uncertainty = _unc
check("soil moisture: without an uncertainty layer the 0.028 default is used", r_fb["uncertainty_m3m3"] == 0.028)
mk_sm = lambda anom, unc: {"latest_date": "20261020", "latest_m3m3": 0.219, "anomaly_m3m3": anom, "n_passes": 6,  # noqa: E731
                           "uncertainty_m3m3": unc, "within_uncertainty": abs(anom) < unc}
a_in, a_out = agent.assess("soil_moisture", mk_sm(0.025, 0.028), []), agent.assess("soil_moisture", mk_sm(0.075, 0.028), [])
_agree = [{"source": "Open-Meteo", "status": "agrees"}]
a_ag = agent.assess("soil_moisture", mk_sm(0.075, 0.028), _agree)
check("soil moisture: inside the uncertainty -> confidence forced low; outside -> medium; never high, even if rain 'agrees'; no alert",
      a_in[0] == "low" and a_out[0] == "medium" and a_ag[0] == "medium" and a_in[2] == a_out[2] == a_ag[2] == "none"
      and "within the product's uncertainty" in a_in[1][0])
t_in = {lg: agent.template("soil_moisture", mk_sm(0.025, 0.028), lg) for lg in ("fr", "en", "ar")}
t_out = {lg: agent.template("soil_moisture", mk_sm(0.075, 0.028), lg) for lg in ("fr", "en", "ar")}
check("soil moisture: the sentence says the change is within the product's uncertainty (FR/EN/AR) only when it is",
      "within the product's uncertainty (0.028)" in t_in["en"] and "dans l'incertitude du produit (0.028)" in t_in["fr"]
      and "ضمن عدم اليقين" in t_in["ar"] and all("uncertainty" not in t_out["en"] and "incertitude" not in t_out["fr"]
                                                 and "عدم اليقين" not in t_out["ar"] for _ in (0,)))

# --- 5. events: the Ben Guerir mine has no polygon -> marked, not validated ----------------------------------------------
lst = {e["id"]: e for e in c.get("/events").json()}
check("events: ben-guerir-mine is marked 'not validated' (status, note and title); the others are 'ready'",
      lst["ben-guerir-mine"]["status"] == "not validated" and "polygon" in lst["ben-guerir-mine"]["status_note"]
      and "not validated" in lst["ben-guerir-mine"]["title_en"] and "non validé" in lst["ben-guerir-mine"]["title"]
      and all(lst[k]["status"] == "ready" for k in lst if k != "ben-guerir-mine"))
bg = c.get("/events/ben-guerir-mine", params={"refresh": True}).json()
check("events: the computed answer of the mine carries the status too", bg["status"] == "not validated" and bg["status_note"])
check("mock discoveries: same shape, labelled, never high or orange",
      _mock.DISCOVERIES["label"] == "unvalidated candidate" and all(z["confidence"] == "low" and z["alert_level"] == "yellow"
                                                                    for z in _mock.DISCOVERIES["zones"]))
contract2 = (ROOT.parent / "docs" / "API_CONTRACT.md").read_text(encoding="utf-8")
check("docs: sign_verified, iono_screen, crosses_data_gap, reference_same_component, uncertainty_m3m3, status, discoveries off documented",
      all(k in contract2 for k in ("sign_verified", "iono_screen", "crosses_data_gap", "reference_same_component",
                                   "uncertainty_m3m3", "within_uncertainty", "not validated", "NISAR_DISCOVERIES_ENABLED",
                                   "unvalidated candidate", "fringes")))

from datetime import date as _dt_date  # noqa: E402


def _raises(fn, exc=ValueError):
    try:
        fn()
    except exc:
        return True
    return False


# =============================================================================================================
# Validation and corrections (feat/validation-corrections). Synthetic data: logic only, not physics.
# =============================================================================================================
# --- 1. Panama: a global VALIDATION event, outside the Morocco scope -------------------------------------------
import make_validation_plan as _mvp  # noqa: E402

pv = c.get("/events/panama-2026", params={"refresh": True}).json()
check("validation event: Panama computes as sudden motion at the exact USGS instant, both look directions, labelled validation",
      pv["type"] == "sudden_motion" and pv["kind"] == "validation" and pv["status"] == "validation"
      and pv["event"]["usgs_id"] == "us6000u18k" and pv["facts"]["event_precision"] == "exact"
      and "decomposition_cm" in pv["facts"] and "outside Morocco" in c.get("/events", params={"include_validation": True}).json()[-1]["title_en"],
      (pv.get("kind"), pv["facts"].get("event_precision")))
lv = c.get("/events", params={"include_validation": True}).json()
check("validation event: listed only on request, after the five unchanged Morocco events, each entry with its kind",
      [e["id"] for e in lv] == [e["id"] for e in c.get("/events").json()] + ["panama-2026"]
      and lv[-1]["kind"] == "validation" and all(e["kind"] == "morocco" for e in lv[:-1]))
vrows = _mvp.select(json.loads(PLAN_NISAR.read_text())["files"])
vplan = json.loads((ROOT.parent / "plan_validation.json").read_text())
geoms = {_mvp.geometry(r) for r in vrows}
check("plan_validation: part 1 = the 8 co-seismic 12-day pairs across 2026-10-09 17:56 UTC (tracks 4, 40, 76, 141, ~13.3 GB), "
      "part 2 = the last pre-event pair per geometry; extra layers on",
      len(geoms) == 8 and len(vrows) == 16 and all(r["dataset"] == "panama" and r["extra_layers"] for r in vrows)
      and all(r["part"] == r["tier"] == (1 if r["event_role"] == "co" else 2) for r in vrows)
      and {r["track"] for r in vrows if r["part"] == 1} == {4, 40, 76, 141} and sum(r["part"] == 1 for r in vrows) == 8
      and 13.0e9 < sum(r["size"] for r in vrows if r["part"] == 1) < 13.6e9
      and all(r["ref_ts"] <= _mvp.EVENT <= r["sec_ts"] and r["span"] == 12 for r in vrows if r["event_role"] == "co")
      and all(sum(r["event_role"] == "pre" and _mvp.geometry(r) == g for r in vrows) == 1 for g in geoms)
      and all(r["sec_ts"] < _mvp.EVENT for r in vrows if r["event_role"] == "pre"), len(vrows))
check("plan_validation.json (committed) = the builder's output, same row format, readable by download_all --plan (parts 1 and 2)",
      [r["name"] for r in vplan["files"]] == [r["name"] for r in vrows] and da.plan_parts(vplan) == [1, 2]
      and set(json.loads(PLAN_NISAR.read_text())["files"][0]) <= set(vplan["files"][0]))

# --- 2. corrections: optional, measured, each one a separate tested function ----------------------------------------
from recipes import corrections as _corr  # noqa: E402

import noise_report as _nr  # noqa: E402

check("corrections setting: default = iono (the old behaviour), 'none' = nothing, canonical order, unknown name fails",
      _corr.parse_setting(None) == ("iono",) and _corr.parse_setting("none") == () and _corr.parse_setting("") == ()
      and _corr.parse_setting("tide, tropo,iono") == ("iono", "tropo", "tide") and _corr.active() == ("iono",)
      and _raises(lambda: _corr.parse_setting("tropo,magic")))
_ph = _np.zeros((4, 4))
_scr = _np.full((4, 4), 2.0)
_scr[0, 0] = _np.nan
check("corrections: each screen is SUBTRACTED by its own function (iono, tropo = hydrostatic + wet, tide); NaN leaves the "
      "phase unchanged; sign -1 adds; the input is never modified",
      _np.allclose(_corr.correct_iono(_ph, _scr)[1:, 1:], -2.0) and _corr.correct_iono(_ph, _scr)[0, 0] == 0.0
      and _np.allclose(_corr.correct_tropo(_ph, _np.full((4, 4), 1.5), _np.full((4, 4), 0.5)), -2.0)
      and _np.allclose(_corr.correct_tide(_ph, _np.full((4, 4), 0.25), sign=-1), 0.25) and not _ph.any())
check("corrections units: radians kept, metres of delay converted with -4*pi/lambda, unknown units = radians ASSUMED and said",
      _corr.to_radians(_np.ones(2), "radians", 0.2384)[1] == "radians"
      and _np.allclose(_corr.to_radians(_np.full(2, 0.2384 / (4 * _np.pi)), "meters", 0.2384)[0], -1.0)
      and "assumed" in _corr.to_radians(_np.ones(2), None, 0.2384)[1])
_hs, _ys, _xs = _np.array([0.0, 1000.0]), _np.array([20.0, 10.0, 0.0]), _np.array([0.0, 10.0])
_cube = _np.stack([_np.add.outer(_ys, _xs), _np.add.outer(_ys, _xs) + 100.0])     # value = y + x (+100 at 1000 m)
check("cube interpolation: exact at the nodes, linear in height, descending axes handled, clipped (no extrapolation)",
      _np.isclose(_corr.interp_cube(_cube, _hs, _ys, _xs, _np.array([0.0]), _np.array([10.0]), _np.array([10.0]))[0], 20.0)
      and _np.isclose(_corr.interp_cube(_cube, _hs, _ys, _xs, _np.array([500.0]), _np.array([5.0]), _np.array([2.0]))[0], 57.0)
      and _np.isclose(_corr.interp_cube(_cube, _hs, _ys, _xs, _np.array([5000.0]), _np.array([99.0]), _np.array([0.0]))[0], 120.0))
check("terrain height: Copernicus GLO-30 public tile names; offline -> the documented constant, said in the source",
      _corr.glo30_tiles(-80.9, 7.4, -80.6, 7.8) == [_corr.GLO30_URL.format(n="Copernicus_DSM_COG_10_N07_00_W081_00_DEM")]
      and len(_corr.glo30_tiles(-7.2, 33.9, -6.5, 34.1)) == 4 and "constant 0 m" in _corr.terrain_height(_prof())[1])
TS = (30.40, -9.55)
tps = [p for p in catalog.find(*TS, "GUNW") if p.track == 172]
sig = {n: _disp.referenced(tps[0], *TS, names)[3] for n, names in
       (("none", ()), ("tropo", ("tropo",)), ("tide", ("tide",)), ("both", ("tropo", "tide")))}
rep_tt = _disp.los_cm_full(tps[0], ("tropo", "tide"))[4]
check("corrections reduce a synthetic tropospheric ramp (+ tide ramp): noise floor none > tropo > tropo+tide, close to the "
      "pixel noise once both are removed",
      sig["none"] > 3 * sig["tropo"] and sig["tropo"] > sig["both"] and sig["tide"] < sig["none"] and sig["both"] < 0.4, sig)
check("corrections report: applied, convention, units 'assumed' without a raw .h5, terrain-height source, cube EPSG",
      rep_tt["tropo"]["applied"] and rep_tt["tide"]["applied"] and rep_tt["tropo"]["convention"] == "subtracted from unwrappedPhase"
      and "assumed" in rep_tt["tropo"]["units"] and "no raw .h5" in rep_tt["tropo"]["attributes_from"]
      and "constant" in rep_tt["tropo"]["height_source"] and rep_tt["tropo"]["cube_epsg"] == 32629
      and rep_tt["tropo"]["already_applied_flag"] is None, rep_tt["tropo"])
rep_none = _disp.los_cm_full(AL_ps[0], ("tropo", "tide"))[4]
check("corrections: a product without cubes (no extra layers) is left alone and says why",
      not rep_none["tropo"]["applied"] and "lacks the cube" in rep_none["tropo"]["reason"])
fa = _disp.analyze(tps[0], *TS, make_layer=False)
check("default setting: facts list the requested and applied corrections; tropo/tide stay off by default",
      fa["corrections_requested"] == ["iono"] and fa["corrections_applied"] == [] and "iono" in fa["corrections"]
      and "tropo" not in fa["corrections"])
# raw .h5 kept: attributes are read, and a product flag saying "already applied" stops a second correction
raw_dir = tmp / "raw_attrs"
raw_dir.mkdir()
with h5py.File(raw_dir / "x.h5", "w") as hf:
    dset = hf.create_dataset("science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH/unwrappedPhase", data=_np.zeros(2))
    dset.attrs["description"] = b"Unwrapped interferometric phase"
    dset.attrs["units"] = b"radians"
    w_ = hf.create_dataset("science/LSAR/GUNW/metadata/radarGrid/wetTroposphericPhaseScreen", data=_np.zeros((2, 2, 2)))
    w_.attrs["units"] = b"radians"
    hf.create_dataset("science/LSAR/GUNW/metadata/processingInformation/parameters/troposphereCorrectionApplied", data=True)
attrs = _corr.product_attributes(str(raw_dir))
check("raw .h5 attributes: description/units read, processingInformation flag read; 'already applied' -> never applied twice",
      attrs["datasets"]["unwrappedPhase"]["units"] == "radians" and _corr.already_applied("tropo", attrs) is True
      and _corr.already_applied("tide", attrs) is False and _corr.already_applied("tide", {"source": None}) is None
      and _corr._apply_cube("tropo", tps[0], _np.zeros((2, 2)), None, attrs, 0.2384, 1, {}, None)[1]["applied"] is False)
f_tr = {**rg["en"]["facts"], "troposphere_corrected": True, "tide_corrected": True, "iono_screen": "subtracted"}
tt = {lg: agent.template("slow_motion", f_tr, lg) for lg in ("fr", "en", "ar")}
check("sentences: when tropo/tide are applied the verdict says so (FR/EN/AR, not validated); default wording unchanged",
      "troposphere: the product's weather-model screen is subtracted (not validated)" in tt["en"]
      and "Solid-earth tide" in tt["en"] and "troposphère : écran du modèle météo" in tt["fr"] and "المد الأرضي" in tt["ar"]
      and "troposphere: not corrected" in agent.template("slow_motion", f_iono, "en")
      and "troposphere: the product's weather-model screen is subtracted" in " ".join(agent.assess("slow_motion", {**f_tr, "sign_verified": True}, [])[1]))
nr_out = tmp / "results_out"
nr_rc = _nr.main(["--out", str(nr_out), "--match", "T172"])
nr = json.loads((nr_out / "noise_report.json").read_text(encoding="utf-8"))
check("noise_report: writes json + md; tropo recommended on the ramp, iono never applicable here, sign check consistent",
      nr_rc == 0 and (nr_out / "noise_report.md").exists() and nr["summary"]["tropo"]["recommended"]
      and nr["summary"]["iono"]["n_products"] == 0 and not nr["summary"]["iono"]["recommended"]
      and "convention consistent" in nr["summary"]["tropo"]["sign_check"]["verdict"] and "tropo" in nr["recommended_setting"],
      nr["recommended_setting"])
check("noise_report: a correction that does not lower the noise is not recommended (stays off)",
      not _nr.summarise([{"sigma_cm": {"none": 1.0, "tropo": 1.2, **{k: None for k in _nr.SETS if k not in ("none", "tropo")}},
                          "applied": {"tropo": True}, "sigma_cm_opposite_sign": {}}])["tropo"]["recommended"])
check(".gitignore ignores results_out/ (local outputs, never committed)",
      "results_out/" in (ROOT.parent / ".gitignore").read_text(encoding="utf-8"))

# --- 3. GPS validation (NGL tenv3), offline sample ---------------------------------------------------------------
import validate_gps as _vg  # noqa: E402

gps_dir = Path(os.environ["NISAR_DATA"]) / "GPS_sample"
tv = _vg.parse_tenv3((gps_dir / "RABT.tenv3").read_text())
hold = {s["station"]: s for s in _vg.parse_holdings((gps_dir / "DataHoldings.txt").read_text())}
check("NGL parsing: tenv3 dates (26JUL04), E/N/U = integer + fractional columns, coordinates from the file; "
      "DataHoldings longitudes 0..360 -> -180..180",
      tv["station"] == "RABT" and abs(tv["lat"] - 33.9981) < 1e-3 and abs(tv["lon"] + 6.8543) < 1e-3
      and tv["epochs"][0][0] == _dt_date(2026, 6, 1) and 4222.9 < tv["epochs"][0][1] < 4223.1
      and abs(hold["RABT"]["lon"] + 6.8543) < 1e-3 and hold["OLDX"]["end"] == _dt_date(2009, 8, 12)
      and _vg.TENV3_URL.startswith("https://geodesy.unr.edu/") and "{sta}" in _vg.TENV3_URL)
gout = tmp / "gps_out"
g_rc = _vg.main(["--offline-sample", "--out", str(gout)])
gj = json.loads((gout / "gps_RABT.json").read_text(encoding="utf-8"))
gs = gj["summary"]["all"]
check("GPS validation recovers the synthetic displacement at RABT: 6 pairs, RMS < 1.5 mm raw and after mean removal, "
      "correlation > 0.95, same sign; json + md + png written",
      g_rc == 0 and gj["status"] == "compared" and gs["n_pairs"] == 6 and gs["rms_mm"] < 1.5
      and gs["rms_after_removing_mean_mm"] < 1.5 and gs["correlation"] > 0.95 and gj["summary"]["sign_hint"] == "same sign as GPS"
      and (gout / "gps_RABT.md").exists() and (gout / "gps_RABT.png").stat().st_size > 1000, gs)
check("GPS validation: InSAR is relative -> raw and mean-removed comparisons both reported; a reversed sign is hinted",
      "mean_difference_mm" in gs and _vg.summarise([{**r, "nisar_los_mm": -r["nisar_los_mm"]} for r in gj["pairs"]])["sign_hint"]
      .startswith("anti-correlated"))
a_rc = _vg.main(["--offline-sample", "--auto", "--out", str(gout)])
found = {s["station"]: s for s in json.loads((gout / "gps_stations.json").read_text(encoding="utf-8"))}
check("GPS --auto: stations inside the frames are listed (RABT with data in the window, OLDX without), FARX outside is not",
      a_rc == 0 and found["RABT"]["overlaps_nisar"] is True and found["OLDX"]["overlaps_nisar"] is False and "FARX" not in found)
far_dir = tmp / "gps_far"
far_dir.mkdir()
far_txt = (gps_dir / "RABT.tenv3").read_text().replace("RABT ", "FARX ").replace("33.9981036600   -6.8542892180", "10.0000000000   10.0000000000")
(far_dir / "FARX.tenv3").write_text(far_txt)
old_txt = "\n".join(l.replace(" 26", " 24", 1) if l.startswith("RABT") else l for l in (gps_dir / "RABT.tenv3").read_text().splitlines())
(far_dir / "RABT.tenv3").write_text(old_txt)
f_rc = _vg.main(["--offline-sample", str(far_dir), "--station", "FARX", "--out", str(gout)])
fj = json.loads((gout / "gps_FARX.json").read_text(encoding="utf-8"))
o_rc = _vg.main(["--offline-sample", str(far_dir), "--station", "RABT", "--out", str(gout / "old")])
oj = json.loads((gout / "old" / "gps_RABT.json").read_text(encoding="utf-8"))
m_rc = _vg.main(["--offline-sample", str(far_dir), "--station", "NONE", "--out", str(gout)])
check("GPS validation never crashes: station in no frame -> 'no_coverage', GPS ending before NISAR -> 'no_gps_in_window', "
      "unknown station -> 'no_gps'; exit code 2 and the files still say why",
      f_rc == 2 and fj["status"] == "no_coverage" and "inside none" in fj["message"] and (gout / "gps_FARX.md").exists()
      and o_rc == 2 and oj["status"] == "no_gps_in_window" and "2024" in oj["gps_last_date"]
      and m_rc == 2 and json.loads((gout / "gps_NONE.json").read_text(encoding="utf-8"))["status"] == "no_gps",
      (fj["status"], oj["status"]))

# --- addendum (Phase A real-data report): sign basis, ionosphere rules, pair quality, User-Agent, failed steps ------
import quality as _q  # noqa: E402

check("sign basis: every signed answer carries the documented convention (ARIA-tools, MintPy prep_nisar); still "
      "'sign unverified' until NISAR_LOS_SIGN_VERIFIED=1",
      "ARIA-tools" in pv["facts"]["sign_basis"] and "MintPy prep_nisar" in pv["facts"]["sign_basis"]
      and "ARIA-tools" in rg["en"]["facts"]["sign_basis"] and "ARIA-tools" in pv["facts"]["pairs"][0]["sign_basis"]
      and pv["facts"]["sign_verified"] is False and pv["confidence"] == "low" and pv["alert_level"] == "none")
IS = (29.60, -9.00)
ips = sorted([p for p in catalog.find(*IS, "GUNW") if p.track == 173], key=lambda p: p.ref)
ig, ib = (_disp.los_cm_full(p)[4]["iono"] for p in ips)
dg = _disp.los_cm(ips[0])[0]
check("ionosphere: the screen is subtracted where it lowers the robust sigma, and pixels whose screen uncertainty is "
      "above the setting are masked (4 % corner), all recorded in the facts",
      ig["applied"] and ig["kept_raw"] is False and ig["frame_sigma_subtracted_rad"] < ig["frame_sigma_raw_rad"]
      and ig["uncertainty_layer"] == "present" and ig["uncertainty_max_rad"] == _corr.IONO_UNC_MAX_RAD
      and abs(ig["uncertainty_masked_fraction"] - 0.04) < 0.005 and _np.isnan(dg[:100, :100]).all()
      and _np.isfinite(dg[300:400, 300:400]).mean() > 0.9, ig)
check("ionosphere: per pair the RAW phase is kept when subtracting does not lower the robust sigma (said, not masked)",
      ib["applied"] is False and ib["kept_raw"] is True and "kept the raw phase" in ib["reason"]
      and ib["frame_sigma_subtracted_rad"] > ib["frame_sigma_raw_rad"]
      and _disp.analyze(ips[1], *IS, make_layer=False)["iono_applied"] is False
      and _np.isfinite(_disp.los_cm(ips[1])[0][:100, :100]).mean() > 0.9)
check("ionosphere rules are pure functions: uncertainty mask threshold, keep-raw decision",
      _corr.uncertainty_mask(_np.array([0.5, 1.5, _np.nan]), 1.0).tolist() == [False, True, False]
      and _corr.uncertainty_mask(None) is None and _corr.keep_raw_phase(1.0, 1.2) and not _corr.keep_raw_phase(1.0, 0.5)
      and _corr.keep_raw_phase(1.0, float("nan")))
nr_out2 = tmp / "results_out_iono"
_nr.main(["--out", str(nr_out2), "--match", "T173"])
nri = json.loads((nr_out2 / "noise_report.json").read_text(encoding="utf-8"))
dec = {r["id"]: r["iono_decision"] for r in nri["products"]}
check("noise_report: the ionosphere decision is reported per pair (subtracted / kept raw, both sigmas, masked share)",
      [d["kept_raw"] for d in dec.values()] == [False, True] and all("frame_sigma_raw_rad" in d for d in dec.values())
      and "kept raw" in (nr_out2 / "noise_report.md").read_text(encoding="utf-8")
      and nri["summary"]["iono"]["n_products"] == 2, dec)
QS = (29.00, -10.00)
qps = sorted([p for p in catalog.find(*QS, "GUNW") if p.track == 174], key=lambda p: p.ref)
qgood, qbad = _q.split(qps)
bad_ids = {b["product"] for b in qbad}
check("pair quality: a flat unwrapped phase and a median coherence < 0.15 are rejected with the reason; good pairs kept",
      len(qgood) == 2 and bad_ids == {qps[1].id, qps[2].id}
      and any("flat unwrapped phase" in x for b in qbad for x in b["reasons"])
      and any("median coherence 0.10 < 0.15" in x for b in qbad for x in b["reasons"])
      and _q.assess(_np.zeros((50, 50)), None)["ok"] is False and _q.assess(_np.random.default_rng(1).normal(0, 1, (50, 50)),
                                                                           _np.full((50, 50), 0.5))["ok"] is True)
qs = _ts.point_series(qps, *QS)
qsd = _damage.analyze(qps, *QS, qps[3].ref[:8] + "T120000", "exact")
qsd_txt = json.dumps({k: v for k, v in qsd.items() if k != "rejected_pairs"}, default=str)
check("pair quality: rejected pairs are left out of the series and of the surface-change before/baseline pairs, and listed",
      all(s["n_pairs"] <= 2 for s in qs) and {r["product"] for r in qs[0]["rejected_pairs"]} == bad_ids
      and {r["product"] for r in qsd["rejected_pairs"]} == bad_ids and not any(b in qsd_txt for b in bad_ids)
      and _ts.velocity_map(qps) is None, (qs[0]["n_pairs"], qsd.get("error")))
qa = agent.investigate("Le sol bouge-t-il ici ?", *QS, "fr")
check("pair quality: the answer lists the rejected pairs in facts and a step says so",
      qa["type"] == "slow_motion" and {r["product"] for r in qa["facts"]["rejected_pairs"]} == bad_ids
      and any("rejected by the quality filter" in s["step"] for s in qa["steps"]), qa["facts"].get("error"))
_config.DISCOVERIES_ENABLED = True
dq = _disc.scan(with_exposure=False)
_config.DISCOVERIES_ENABLED = False
check("pair quality: discoveries never scan a rejected pair and list them",
      bad_ids <= {r["product"] for r in dq["rejected_pairs"]} and not any(b in json.dumps(dq["zones"]) for b in bad_ids))
seen_headers = []


class _FakeReq:
    class RequestException(Exception):
        pass

    @staticmethod
    def get(url, **kw):
        seen_headers.append(kw.get("headers"))
        raise _FakeReq.RequestException("blocked in the tests")

    @staticmethod
    def post(url, **kw):
        seen_headers.append(kw.get("headers"))
        raise _FakeReq.RequestException("406 Not Acceptable")


_real_req, _real_off, _real_key = _evidence.requests, _evidence.OFFLINE, _evidence.FIRMS_MAP_KEY
_evidence.requests, _evidence.OFFLINE, _evidence.FIRMS_MAP_KEY = _FakeReq, False, "test"
try:
    ev_out = [_evidence.earthquakes(7.59, -80.77, "20260927", "20261009"), _evidence.rainfall(31.25, -7.98, "20261001", "20261013"),
              _evidence.fires(31.25, -7.98, "20261013"), _evidence.exposure(31.25, -7.98)]
    st_ = agent.Steps()
    st_.run("buildings and roads around the point", _evidence.exposure, 31.25, -7.98)
finally:
    _evidence.requests, _evidence.OFFLINE, _evidence.FIRMS_MAP_KEY = _real_req, _real_off, _real_key
check("evidence: every outside request (USGS, Open-Meteo, FIRMS, Overpass) sends a User-Agent header",
      len(seen_headers) >= 4 and all(h and h.get("User-Agent", "").startswith("NISAR-Pulse") for h in seen_headers)
      and all(e["status"] == "unavailable" for e in ev_out), seen_headers)
check("agent steps: an evidence source that returns 'unavailable' is recorded ok: false with its error",
      st_[0]["ok"] is False and "406" in st_[0]["error"] and agent.Steps().run("x", lambda: {"status": "agrees"}) == {"status": "agrees"})

# --- 4. sign-check helper: shows, explains, never decides ----------------------------------------------------------
import sign_check as _sc  # noqa: E402

env_before = {k: os.environ.get(k) for k in ("NISAR_LOS_SIGN", "NISAR_LOS_SIGN_VERIFIED")}
sc_out = tmp / "sign_out"
sc_rc = _sc.main(["--out", str(sc_out)])
sc_md = (sc_out / "sign_check.md").read_text(encoding="utf-8")
check("sign_check without a raw file: explains --keep-raw and list_h5_layers.py, renders ascending + descending Panama "
      "co-seismic maps, links the USGS mechanism and finite fault, says strike-slip and not to use the synthetic uplift",
      sc_rc == 0 and "--keep-raw" in sc_md and "list_h5_layers.py" in sc_md and (sc_out / "sign_check.png").stat().st_size > 10_000
      and "ascending T4" in sc_md and "descending T141" in sc_md and _sc.USGS in sc_md and "/moment-tensor" in sc_md
      and "/finite-fault" in sc_md and "strike-slip" in sc_md and "Do NOT use the synthetic" in sc_md and "ARIA-tools" in sc_md)
check("sign_check prints the exact commands and never sets them itself (environment and config unchanged)",
      '$env:NISAR_LOS_SIGN = "1"; $env:NISAR_LOS_SIGN_VERIFIED = "1"' in sc_md and '$env:NISAR_LOS_SIGN = "-1"' in sc_md
      and {k: os.environ.get(k) for k in env_before} == env_before and _config.LOS_SIGN_VERIFIED is False
      and "os.environ[\"NISAR_LOS_SIGN" not in (ROOT / "sign_check.py").read_text(encoding="utf-8"))
pan_co = _sc.coseismic(catalog.load())[0]
raw_sc = pan_co.folder / (pan_co.name + ".h5")
with h5py.File(raw_sc, "w") as hf:
    u_ = hf.create_dataset("science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH/unwrappedPhase", data=_np.zeros(2))
    u_.attrs["description"] = b"Unwrapped interferometric phase"
    u_.attrs["units"] = b"radians"
    hf.create_dataset("science/LSAR/GUNW/metadata/radarGrid/losUnitVectorX", data=_np.zeros((2, 2))).attrs["units"] = b"1"
try:
    _sc.main(["--out", str(sc_out / "raw")])
    sc_md2 = (sc_out / "raw" / "sign_check.md").read_text(encoding="utf-8")
finally:
    raw_sc.unlink()
check("sign_check with a kept raw .h5: prints the attributes of unwrappedPhase and of the LOS vectors",
      "unwrappedPhase" in sc_md2 and "units: radians" in sc_md2 and "losUnitVectorX" in sc_md2 and "--keep-raw" not in sc_md2)

# --- 5. discoveries, safely: the consistent mode ---------------------------------------------------------------------
check("discoveries mode: off by default (no NISAR_DISCOVERIES_MODE, no NISAR_DISCOVERIES_ENABLED); the API says so",
      _config.DISCOVERIES_MODE == "" and _disc.mode() == "off" and c.get("/discoveries").json()["mode"] == "off"
      and c.get("/discoveries").json()["zones"] == [] and "NISAR_DISCOVERIES_MODE=consistent" in _config.DISCOVERIES_OFF_REASON)
check("consistent rule: a single-pair artefact is rejected; a 3-pair signal of one sign is kept; one dominant pair, or a "
      "sign that flips, is rejected",
      not _disc.consistent_zone([(-60.0, 1.0), (0.1, 1.0), (-0.2, 1.0), (0.05, 1.0)])["kept"]
      and "seen in 1" in _disc.consistent_zone([(-60.0, 1.0), (0.1, 1.0), (-0.2, 1.0), (0.05, 1.0)])["why_not"][0]
      and _disc.consistent_zone([(-1.5, 0.3), (-1.4, 0.3), (-1.6, 0.3), (0.1, 0.3)])["kept"]
      and not _disc.consistent_zone([(-1.0, 0.1), (-1.0, 0.1), (-20.0, 0.1)])["kept"]
      and not _disc.consistent_zone([(-1.0, 0.1), (-1.0, 0.1), (-1.0, 0.1), (1.0, 0.1)])["kept"])
P2 = lambda ref, sec, i: _types.SimpleNamespace(ref=ref, sec=sec, span_days=12, id=i)  # noqa: E731
check("consistent mode uses INDEPENDENT pairs only (no shared time interval)",
      [p.id for p in _disc.independent([P2("20260801", "20260813", "a"), P2("20260801", "20260825", "b"),
                                         P2("20260813", "20260825", "c"), P2("20260819", "20260831", "d"),
                                         P2("20260825", "20260906", "e")])] == ["a", "c", "e"])
_config.DISCOVERIES_MODE = "consistent"
try:
    dc = c.get("/discoveries", params={"refresh": True, "exposure": False}).json()
    dc_cached = c.get("/discoveries").json()
finally:
    _config.DISCOVERIES_MODE = ""
CS = (28.50, -10.50)
bump_z = [z for z in dc["zones"] if z["track"] == 175 and abs(z["lon"] - (CS[1] + 5 / 98)) < 0.03 and abs(z["lat"] - CS[0]) < 0.03]
check("consistent discoveries keep the 4-pair signal and reject the single-pair -60 cm artefact of the same geometry",
      dc["mode"] == "consistent" and len(bump_z) == 1 and bump_z[0]["n_pairs_detected"] == 4 and bump_z[0]["same_sign"]
      and bump_z[0]["max_single_pair_share"] <= 0.5 and len(bump_z[0]["pairs_detected"]) == 4
      and not any(z["track"] == 175 and z["lon"] < CS[1] - 0.03 for z in dc["zones"]),
      [(z["track"], z["lat"], z["lon"], z["n_pairs_detected"]) for z in dc["zones"]])
check("consistent discoveries: unvalidated candidates only (low, yellow), quality filter and masked-ionosphere setting "
      "recorded, an oscillating (seasonal) signal is not kept, the cache answers in the same mode",
      dc["zones"] and all(z["label"] == "unvalidated candidate" and z["confidence"] == "low" and z["alert_level"] == "yellow"
                          for z in dc["zones"])
      and bad_ids <= {r["product"] for r in dc["rejected_pairs"]} and dc["rules"]["corrections"] == ["iono"]
      and dc["rules"]["quality_filter"] is True and not any(z["track"] == 170 for z in dc["zones"])
      and dc_cached["mode"] == "consistent" and dc_cached["zones"] == dc["zones"])
check("mock discoveries: consistent-mode shape (mode, rules, per-zone pair counts), never above low / yellow",
      _mock.DISCOVERIES["mode"] == "consistent" and _mock.DISCOVERIES["rules"]["min_independent_pairs"] == 3
      and all(z["n_pairs_detected"] >= 3 and z["same_sign"] and z["confidence"] == "low" and z["alert_level"] == "yellow"
              for z in _mock.DISCOVERIES["zones"]))

# --- 6. docs: README validation commands, MOROCCO_PLAN link, contract for every new field ------------------------
readme = (ROOT.parent / "README.md").read_text(encoding="utf-8")
contract3 = (ROOT.parent / "docs" / "API_CONTRACT.md").read_text(encoding="utf-8")
check("README: a Validation section lists noise_report, validate_gps, sign_check, the plan_validation download and "
      "precompute with their output paths; the MOROCCO_PLAN.md link resolves",
      "## Validation" in readme and all(k in readme for k in (
          "python noise_report.py", "python validate_gps.py", "python sign_check.py", "--plan plan_validation.json --part 1",
          "python precompute.py", "results_out\\noise_report.json", "results_out\\gps_RABT.json", "results_out\\sign_check.md",
          "results_out\\gps_stations.json"))
      and "docs/claude/MOROCCO_PLAN.md" in readme and (ROOT.parent / "docs" / "claude" / "MOROCCO_PLAN.md").exists())
check("API contract: validation event, correction facts, sign basis, pair quality, discoveries mode documented "
      "(older keys still there)",
      all(k in contract3 for k in ("include_validation", "kind", "us6000u18k", "corrections_requested", "corrections_applied",
                                   "tide_corrected", "kept_raw", "uncertainty_masked_fraction", "sign_basis", "rejected_pairs",
                                   "NISAR_DISCOVERIES_MODE", "n_pairs_detected", "max_single_pair_share", "ok: false"))
      and all(k in contract3 for k in ("surface_change", "crid", "maturity", "event_time", "iono_screen", "unvalidated candidate")))
check("plan_nisar.json still byte-identical after all Morocco checks",
      hashlib.sha256(PLAN_NISAR.read_bytes()).hexdigest() == sha_before)

n_ok = sum(ok for _, ok in results)
print(f"\n{n_ok}/{len(results)} checks passed")
sys.exit(0 if n_ok == len(results) else 1)
