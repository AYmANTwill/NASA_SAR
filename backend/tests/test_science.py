"""Checks of the science layer (case contract now; Okada, inversion, exposure next). No internet needed.
Usage (from backend/):  python tests/test_science.py"""
import copy
import json
import os
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows consoles default to cp1252
ROOT = Path(__file__).resolve().parents[1]
tmp =Path(tempfile.mkdtemp(prefix="nisar_science_"))
os.environ.update(NISAR_DATA=str(tmp / "data"), NISAR_CACHE=str(tmp / "cache"), NISAR_OFFLINE="1")
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from pydantic import ValidationError  # noqa: E402

import api  # noqa: E402
from science import case_store  # noqa: E402
from science.case_models import CaseStudy, Measurement, agreement  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  — {detail}" if not cond and str(detail) else ""))


def rejects(data) -> bool:
    try:
        CaseStudy.model_validate(data)
    except ValidationError:
        return True
    return False


def m(value, unc, unit="Mw", sigma=1):
    return Measurement(value=value, uncertainty=unc, unit=unit, sigma=sigma)


# ---------------------------------------------------------------- agreement rule
# sigma_combined = sqrt(0.3² + 0.4²) = 0.5
check("agreement: |d| = 2σ exactly is agree", agreement(m(7.0, 0.3), m(8.0, 0.4)) == "agree")
check("agreement: |d| = 3σ is partial", agreement(m(7.0, 0.3), m(8.5, 0.4)) == "partial")
check("agreement: |d| = 4σ exactly is partial", agreement(m(7.0, 0.3), m(9.0, 0.4)) == "partial")
check("agreement: |d| = 5σ is disagree", agreement(m(7.0, 0.3), m(9.5, 0.4)) == "disagree")
check("agreement: no reference", agreement(m(7.0, 0.3), None) == "no_reference")
check("agreement: a 2-sigma uncertainty is converted to 1 sigma",
      agreement(m(7.0, 0.6, sigma=2), m(8.0, 0.8, sigma=2)) == "agree"
      and agreement(m(7.0, 0.6, sigma=1), m(8.6, 0.8, sigma=1)) == "agree"
      and agreement(m(7.0, 0.6, sigma=2), m(8.6, 0.8, sigma=2)) == "partial")
try:
    agreement(m(7.0, 0.1, "km"), m(7.0, 0.1, "m"))
    check("agreement: different units raise", False)
except ValueError:
    check("agreement: different units raise", True)

# ---------------------------------------------------------------- the four draft fixtures
cases, errors = case_store.load_all()
check("the 4 fixtures load and validate", [c.id for c in cases] == list(case_store.ORDER) and not errors, errors)
check("all fixtures are drafts with their placeholders listed",
      all(c.status == "draft" and c.placeholders for c in cases))
base = json.loads((case_store.CASES_DIR / "panama-2026.json").read_text(encoding="utf-8"))

# ---------------------------------------------------------------- the contract refuses broken cases
final_with_placeholders = {**base, "status": "final"}
check("a final case with placeholders is refused", rejects(final_with_placeholders))
d = copy.deepcopy(base)
d.update(status="final", placeholders=[])
check("a final case with a zero NISAR uncertainty is refused", rejects(d))
d = copy.deepcopy(base)
d["findings"][0]["agreement"] = "agree"
check("a hand-typed agreement that breaks the 2σ/4σ rule is refused", rejects(d))
d = copy.deepcopy(base)
d["findings"][0]["reference_source"] = None
check("a reference without its source is refused", rejects(d))
d = copy.deepcopy(base)
d["limits"] = []
check("a case without limits is refused", rejects(d))
d = copy.deepcopy(base)
d["kind"] = "flood"
check("a case whose kind does not match its id is refused", rejects(d))
d = copy.deepcopy(base)
d["date"] = "2026-10-09"
check("a date that is not an ISO UTC date-time is refused", rejects(d))
d = copy.deepcopy(base)
d["location"]["lat"] = 20.0
check("a bbox that does not contain the point is refused", rejects(d))
d = copy.deepcopy(base)
d["findings"][1]["id"] = "mw"
check("duplicate finding ids are refused", rejects(d))

# a well-formed final case is accepted and serialized without null optional keys
good = copy.deepcopy(base)
good.update(status="final", placeholders=[])
for f in good["findings"]:
    f["nisar"] = {"value": 7.6, "uncertainty": 0.05, "unit": f["nisar"]["unit"], "sigma": 1}
good["findings"][0]["agreement"] = "agree"     # |7.6 - 7.7| = 0.1 <= 2·sqrt(0.05² + 0.1²) = 0.22
good["figures"] = [{"id": "dmr", "kind": "image", "title": {"fr": "a", "en": "a", "ar": "a"},
                    "url": "/api/cases/panama-2026/figures/dmr.png", "caption": {"template": "x", "params": {}}}]
try:
    out = case_store.to_json(CaseStudy.model_validate(good))
    check("a complete final case is accepted", out["status"] == "final")
    check("serialization omits figure.layer and an empty TemplatedText.text (zod optional, not nullable)",
          "layer" not in out["figures"][0] and "text" not in out["figures"][0]["caption"]
          and out["exposure"] is None and out["findings"][1]["reference"] is None)
except ValidationError as exc:
    check("a complete final case is accepted", False, str(exc)[:400])

# ---------------------------------------------------------------- API
c = TestClient(api.app)
r = c.get("/api/cases")
check("GET /api/cases lists the 4 cases in order",
      r.status_code == 200 and [s["id"] for s in r.json()] == list(case_store.ORDER), r.text[:300])
check("summaries have exactly the contract keys",
      all(set(s) == {"id", "kind", "title", "date", "status", "thumbnail_url"} for s in r.json()))
r = c.get("/api/cases/panama-2026")
check("GET /api/cases/panama-2026 returns the case",
      r.status_code == 200 and r.json()["findings"][0]["reference"]["value"] == 7.7, r.text[:300])
r = c.get("/api/cases/nope")
check("unknown case: 404 with an ApiErrorBody", r.status_code == 404 and r.json()["code"] == "case_not_found")

bad_dir = tmp / "bad_cases"
bad_dir.mkdir()
(bad_dir / "panama-2026.json").write_text(json.dumps({**base, "limits": []}), encoding="utf-8")
(bad_dir / "haouz-flood-2026.json").write_text(
    (case_store.CASES_DIR / "haouz-flood-2026.json").read_text(encoding="utf-8"), encoding="utf-8")
cases, errors = case_store.load_all(bad_dir)
check("an invalid case file is reported and skipped, the valid ones still load",
      [x.id for x in cases] == ["haouz-flood-2026"] and len(errors) == 1 and "panama-2026" in errors[0], errors)
try:
    case_store.load("panama-2026", bad_dir)
    check("load() raises CaseFileError on an invalid file", False)
except case_store.CaseFileError:
    check("load() raises CaseFileError on an invalid file", True)

# ---------------------------------------------------------------- Okada (1985)
import numpy as np  # noqa: E402

from science.okada import fault_enu, okada85  # noqa: E402

# Table 2 of Okada (1985), finite rectangular source: x=2, y=3, d=4, dip=70°, L=3, W=2, lambda=mu.
TABLE2 = {"strike": ({"U1": 1}, (-8.689e-3, -4.298e-3, -2.747e-3)),
          "dip": ({"U2": 1}, (-4.682e-3, -3.527e-2, -3.564e-2)),
          "tensile": ({"U3": 1}, (-2.660e-4, 1.056e-2, 3.214e-3))}
for name, (kw, expected) in TABLE2.items():
    got = np.array(okada85(2.0, 3.0, 4.0, 70.0, 3.0, 2.0, **kw), dtype=float)
    check(f"Okada Table 2, {name} slip: (ux, uy, uz) to 4 significant figures",
          np.allclose(got, expected, rtol=6e-4, atol=0), f"{got} vs {expected}")
for kw in ({"U1": 1}, {"U2": 1}, {"U3": 1}):
    a = np.array(okada85(2.0, 3.0, 4.0, 90.0, 3.0, 2.0, **kw))
    b = np.array(okada85(2.0, 3.0, 4.0, 89.9999, 3.0, 2.0, **kw))
    check(f"Okada: the vertical-fault branch (eq. 29) joins the dipping branch, {kw}", np.abs(a - b).max() < 1e-4)
yy = np.array([1.0, 5.0, 20.0, -5.0])
_, un, uu = fault_enu(yy, np.zeros(4), x0=0, y0=0, strike_deg=0, dip_deg=90, rake_deg=0, top_depth=0,
                      length=1e5, width=10, slip=1)
check("Okada: long vertical strike-slip fault = 2D screw dislocation, u = sign(y)·atan(D/|y|)/π",
      np.allclose(un, np.sign(yy) * np.arctan(10 / np.abs(yy)) / np.pi, atol=1e-6) and np.abs(uu).max() < 1e-9, un)
ee = np.array([-10.0, 5.0, 15.0])
_, _, uu = fault_enu(ee, np.zeros(3), x0=0, y0=0, strike_deg=0, dip_deg=30, rake_deg=90, top_depth=1,
                     length=100, width=20, slip=1)
check("Okada: a thrust (rake 90) lifts the hanging wall (east of a north-striking, east-dipping fault)",
      uu[1] > 0.3 and uu[2] > 0 and uu[0] < 0, uu)
try:
    okada85(0.0, 0.0, 1.0, 30.0, 10.0, 10.0, U1=1)
    check("Okada: a fault crossing the free surface is refused", False)
except ValueError:
    check("Okada: a fault crossing the free surface is refused", True)

# ---------------------------------------------------------------- nodal planes and fault inversion
from science.invert_fault import Track, invert, moment_mw, predict  # noqa: E402
from science.usgs import Plane, UsgsError, auxiliary_plane, parse  # noqa: E402

aux = auxiliary_plane(Plane(0, 45, 90))
check("auxiliary plane of (0, 45, 90) is (180, 45, 90)",
      np.allclose([aux.strike, aux.dip, aux.rake], [180, 45, 90], atol=1e-6), aux)
ok = True
for p in (Plane(30, 60, -120), Plane(200, 80, 10), Plane(300, 20, 95)):
    back = auxiliary_plane(auxiliary_plane(p))
    ok &= np.allclose([back.strike, back.dip, back.rake], [p.strike, p.dip, p.rake], atol=1e-6)
check("auxiliary plane of the auxiliary plane is the original plane", ok)
check("Mw = 2/3 (log10(mu L W s) - 9.1) with mu = 30 GPa",
      abs(moment_mw(120, 40, 2.5)[1] - (2 / 3) * (np.log10(30e9 * 120e3 * 40e3 * 2.5) - 9.1)) < 1e-12)

usgs_fixture = {"id": "us_test", "geometry": {"coordinates": [-80.77, 7.59, 20.0]},
                "properties": {"time": 1791568566000, "mag": 7.7, "magType": "mww", "products": {"moment-tensor": [
                    {"source": "us", "properties": {"derived-magnitude-type": "Mww",
                     "nodal-plane-1-strike": "290", "nodal-plane-1-dip": "30", "nodal-plane-1-rake": "90",
                     "nodal-plane-2-strike": "110", "nodal-plane-2-dip": "60", "nodal-plane-2-rake": "90"}}]}}}
ev = parse(usgs_fixture)
check("USGS GeoJSON: epicentre, magnitude and both nodal planes are parsed",
      (ev.lat, ev.lon, ev.magnitude, ev.planes[1].dip) == (7.59, -80.77, 7.7, 60.0))
try:
    parse({**usgs_fixture, "properties": {**usgs_fixture["properties"], "products": {}}})
    check("USGS GeoJSON without a moment tensor raises UsgsError", False)
except UsgsError:
    check("USGS GeoJSON without a moment tensor raises UsgsError", True)

rng = np.random.default_rng(1)
true_plane = Plane(290, 30, 90)
synth = [Track(name, rng.uniform(-150, 150, 500), rng.uniform(-150, 150, 500), np.zeros(500), np.tile(v, (500, 1)))
         for name, v in (("asc", [-0.62, -0.11, 0.78]), ("desc", [0.62, -0.11, 0.78]))]
true_theta = np.array([10, -5, 120, 40, 2, 2.5, 3, 0.01, -0.02, -2, 0.0, 0.015])
synth = [Track(t.name, t.east, t.north, p + rng.normal(0, 1.0, p.size), t.vec)
         for t, p in zip(synth, predict(true_theta, synth, true_plane))]
res, _ = invert(synth, (true_plane, auxiliary_plane(true_plane)), n_boot=5)
best = res["planes"][res["best_plane"]]
check("synthetic inversion keeps the true nodal plane (lower RMS than the auxiliary plane)",
      res["best_plane"] == 0 and best["rms_cm"] < res["planes"][1]["rms_cm"], [p["rms_cm"] for p in res["planes"]])
check("synthetic inversion recovers Mw within 0.05 and the top depth within 1 km",
      abs(best["mw"]["value"] - moment_mw(120, 40, 2.5)[1]) < 0.05
      and abs(best["params"]["top_depth_km"]["value"] - 2) < 1, best["mw"])
check("synthetic inversion: RMS at the noise level (1 cm), stable, Mw sigma reported",
      0.8 < best["rms_cm"] < 1.2 and res["stable"] and best["mw"]["sigma"] is not None, res["unstable_reasons"])

from science.panama_fault import block_means  # noqa: E402

grid = np.arange(100 * 80, dtype=float).reshape(100, 80)
grid[:50, :] = np.nan                                   # top half masked
rows, cols, vals = block_means(grid, n_target=40)
b = int(np.ceil(np.sqrt(50 * 80 / 40)))
check("block means: masked blocks dropped, about n_target points kept, centres and means exact",
      30 <= vals.size <= 60 and rows.min() >= 50 and vals[0] == np.nanmean(grid[int(rows[0] - b / 2):int(rows[0] + b / 2),
                                                                              int(cols[0] - b / 2):int(cols[0] + b / 2)]),
      (vals.size, rows.min()))
check("block means: an all-masked raster gives no point", block_means(np.full((10, 10), np.nan))[2].size == 0)

# ---------------------------------------------------------------- exposure (offline: synthetic rasters, cached OSM)
import hashlib  # noqa: E402

import rasterio  # noqa: E402
from rasterio.transform import from_origin  # noqa: E402

from science import exposure as ex  # noqa: E402
from science.case_models import Exposure  # noqa: E402

ex.AUX_DIR = tmp / "aux"
# 100 m UTM grid (zone 17N) near the Panama epicentre, 60 x 60 pixels; zone = a 20 x 20 pixel square (4 km2)
utm_grid = ex.Grid(from_origin(500_000, 850_000, 100, 100), "EPSG:32617", (60, 60))
square = np.zeros((60, 60), bool)
square[20:40, 20:40] = True
check("exposure: area of 400 pixels of 100 m = 4 km2", abs(ex.area_km2(square, utm_grid) - 4.0) < 1e-9)
geo_grid = ex.Grid(from_origin(-81.0, 8.0, 0.01, 0.01), "EPSG:4326", (10, 10))
expected_geo = 100 * (0.01 * 111.32) * (0.01 * 110.574) * np.mean(np.cos(np.radians(8.0 - 0.005 - 0.01 * np.arange(10))))
check("exposure: area on a geographic grid uses cos(latitude)",
      abs(ex.area_km2(np.ones((10, 10), bool), geo_grid) - expected_geo) < 1e-6)

pop_path = tmp / "pop.tif"
pop_tf = from_origin(-81.0, 8.0, 0.001, 0.001)                        # ~110 m cells, 10 people each
with rasterio.open(pop_path, "w", driver="GTiff", width=1000, height=1000, count=1, dtype="float32",
                   crs="EPSG:4326", transform=pop_tf, nodata=-99999) as dst:
    dst.write(np.full((1, 1000, 1000), 10.0, dtype="float32"))
pop = ex.PopSource(pop_path, "synthetic population", "https://example.org/pop")
cell_km2 = (0.001 * 111.32 * np.cos(np.radians(7.7))) * (0.001 * 110.574)
people = ex.people_in(square, utm_grid, pop)
check("exposure: people = sum of the population cells inside the zone (counts not resampled)",
      abs(people - 10 * 4.0 / cell_km2) / (10 * 4.0 / cell_km2) < 0.05, (people, 10 * 4.0 / cell_km2))
check("exposure: an empty zone has nobody", ex.people_in(np.zeros((60, 60), bool), utm_grid, pop) == 0)

from pyproj import Transformer  # noqa: E402

to_ll = Transformer.from_crs("EPSG:32617", 4326, always_xy=True)
inside = [to_ll.transform(500_000 + 100 * c + 50, 850_000 - 100 * r - 50) for r, c in ((25, 25), (30, 35), (39, 20))]
outside = [to_ll.transform(500_000 + 100 * c + 50, 850_000 - 100 * r - 50) for r, c in ((5, 5), (45, 30))]
pts = np.array(inside + outside)
check("exposure: buildings counted only when their centroid is in the zone", ex.buildings_in(square, utm_grid, pts) == 3)

disp = np.zeros((60, 60))
disp[10:50, 10:50] = 9.0
disp[20:40, 20:40] = 12.0
central, variants = ex.quake_masks(disp, noise_cm=2.5)
check("exposure: earthquake zone |LOS| > 10 cm, variants at 10 ∓ σ are nested",
      central.sum() == 400 and variants[0].sum() == 1600 and variants[1].sum() == 0
      and (variants[0] >= central).all() and (central >= variants[1]).all())
res = ex.exposure(central, variants, utm_grid, pop, pts)
check("exposure: uncertainty = largest departure of the ±σ zones, range contains the value",
      res["area_km2"]["value"] == 4.0 and res["area_km2"]["uncertainty"] == 12.0
      and res["area_km2"]["range"] == [0.0, 16.0] and res["buildings"]["value"] == 3, res["area_km2"])
fm, fv = ex.flood_masks(square)
check("exposure: flood variants are the mask eroded and dilated by one pixel",
      fv[0].sum() == 18 * 18 and fv[1].sum() == 22 * 22 - 4 and (fv[1] >= fm).all() and (fm >= fv[0]).all())
case_exp = ex.to_case_exposure(res, pop, "2026-11-14")
try:
    Exposure.model_validate(case_exp)
    check("exposure: output is a valid CaseStudy.exposure (people / count / km2, source {name, url})", True)
except ValidationError as exc:
    check("exposure: output is a valid CaseStudy.exposure (people / count / km2, source {name, url})", False, exc)
try:
    ex.quake_masks(disp, float("nan"))
    check("exposure: an invalid noise sigma is refused", False)
except ex.ExposureError:
    check("exposure: an invalid noise sigma is refused", True)

# OSM: tiles are read from the cache; offline without a cache -> ExposureError
lon_c, lat_c = to_ll.transform(500_000 + 3000, 850_000 - 3000)
ti, tj = int(np.floor(lat_c / ex.OSM_TILE_DEG)), int(np.floor(lon_c / ex.OSM_TILE_DEG))
s_, w_ = ti * ex.OSM_TILE_DEG, tj * ex.OSM_TILE_DEG
key = hashlib.sha1(f"{s_:.4f},{w_:.4f},{s_ + ex.OSM_TILE_DEG:.4f},{w_ + ex.OSM_TILE_DEG:.4f}".encode()).hexdigest()[:16]
(ex.AUX_DIR / "osm").mkdir(parents=True, exist_ok=True)
(ex.AUX_DIR / "osm" / f"buildings_{key}.json").write_text(
    json.dumps({"bbox": [s_, w_, 0, 0], "fetched": "2026-11-14", "centroids": [list(p) for p in inside]}),
    encoding="utf-8")
small = np.zeros((60, 60), bool)
small[25:35, 25:35] = True
got, date = ex.osm_buildings(small, utm_grid)
check("exposure: OSM buildings come from the cached 0.25° tile, with its fetch date",
      got.shape == (3, 2) and date == "2026-11-14", (got.shape, date))
far_grid = ex.Grid(from_origin(200_000, 1_500_000, 100, 100), "EPSG:32617", (60, 60))
try:
    ex.osm_buildings(square, far_grid)
    check("exposure: an uncached OSM tile offline raises ExposureError", False)
except ex.ExposureError:
    check("exposure: an uncached OSM tile offline raises ExposureError", True)
try:
    ex.population_source("ZZZ")
    check("exposure: no population raster offline raises ExposureError", False)
except ex.ExposureError:
    check("exposure: no population raster offline raises ExposureError", True)

passed = sum(ok for _, ok in results)
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
