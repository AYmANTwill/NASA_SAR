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

import api  # noqa: E402

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
check("ask damage: coherence loss found", r["type"] == "damage" and (r["facts"].get("loss_at_point") or 0) > 0.3,
      r["facts"].get("loss_at_point"))
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

ev = c.get("/events/al-wahda").json()
check("event computed", ev.get("event", {}).get("id") == "al-wahda" and ev.get("verdict"))
check("events listing", any(e["computed"] for e in c.get("/events").json()))

d = c.get("/discoveries", params={"refresh": True, "exposure": False}).json()
near = lambda z, lat, lon: abs(z["lat"] - lat) < 0.05 and abs(z["lon"] - lon) < 0.05
check("discoveries: finds the Ben Guerir subsidence", any(near(z, 32.27, -7.93) for z in d["zones"]),
      [(z["lat"], z["lon"], z["mean"], z["unit"]) for z in d["zones"][:5]])
check("discoveries: finds Al Wahda", any(near(z, 34.64, -5.17) for z in d["zones"]))

w = c.post("/watch", json={"lat": 34.64, "lon": -5.17, "question": "Le barrage Al Wahda se déforme-t-il ?"}).json()
check("watch created with next passes", w.get("id") and w["next_passes"], w.get("next_passes", [])[:1])
check("watch listed", any(x["id"] == w["id"] for x in c.get("/watch").json()))
check("watch check runs", "alerts" in c.post("/watch/check").json())
check("watch delete", c.delete(f"/watch/{w['id']}").status_code == 200)
check("next-pass", len(c.get("/next-pass", params={"lat": 34.64, "lon": -5.17}).json()) >= 2)

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

n_ok = sum(ok for _, ok in results)
print(f"\n{n_ok}/{len(results)} checks passed")
sys.exit(0 if n_ok == len(results) else 1)
