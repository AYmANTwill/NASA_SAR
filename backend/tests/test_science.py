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

check("inversion reports the variance reduction of every track (the NISAR_LOS_SIGN ±1 runs compare it)",
      set(best["variance_reduction_per_track"]) == {"asc", "desc"}
      and all(v > 0.9 for v in best["variance_reduction_per_track"].values()), best["variance_reduction_per_track"])

from science import ffm_sign  # noqa: E402

ff = ffm_sign.USGS_FFM_PANAMA
lat0, lon0 = 7.6069, -80.7566
ff_tracks = [Track(name, rng.uniform(-80, 80, 600), rng.uniform(-80, 80, 600), np.zeros(600), np.tile(v, (600, 1)))
             for name, v in (("asc", [-0.62, -0.11, 0.78]), ("desc", [0.62, -0.11, 0.78]))]
model = ffm_sign.forward(ff, ff_tracks, lat0, lon0)
obs = [Track(t.name, t.east, t.north, 2.0 * m + 1.5 + 0.01 * t.east + rng.normal(0, 1.0, m.size), t.vec)
       for t, m in zip(ff_tracks, model)]
sc = ffm_sign.sign_check(obs, lat0, lon0, 1.0)
check("FFM sign test: data built from the USGS model with the right sign -> consistent on every track",
      sc["overall"] == "consistent" and all(abs(v["k"] - 2.0) < 0.2 for v in sc["per_track"].values()), sc["per_track"])
flipped = [Track(t.name, t.east, t.north, -t.los, t.vec) for t in obs]
check("FFM sign test: the same data with the opposite sign -> flipped",
      ffm_sign.sign_check(flipped, lat0, lon0, 1.0)["overall"] == "flipped")
noise = [Track(t.name, t.east, t.north, rng.normal(0, 1.0, t.los.size), t.vec) for t in obs]
check("FFM sign test: pure noise -> inconclusive", ffm_sign.sign_check(noise, lat0, lon0, 1.0)["overall"] == "inconclusive")
top_c = model[0][np.argmin(np.hypot(ff_tracks[0].east - (-80.769 - lon0) * 111.32 * np.cos(np.radians(lat0)),
                                    ff_tracks[0].north - (7.54 - lat0) * 110.574))]
check("FFM forward model: centre given as the surface projection of the fault-plane centre, non-zero signal there",
      abs(top_c) > 1.0, top_c)

from science.panama_fault import largest_component  # noqa: E402

dmap = np.ones((10, 10))
ccmap = np.ones((10, 10))
ccmap[:, 7:] = 2                    # a smaller component, offset by one fringe in the data
dmap[:, 7:] += 11.9
ccmap[0, 0] = 0                     # unwrapping failed there
kept, note = largest_component(dmap, ccmap)
check("largest connected component: the smaller component and label 0 are dropped, the note says so",
      np.isfinite(kept[:, :7]).sum() == 69 and not np.isfinite(kept[:, 7:]).any() and "1 other" in note, note)
check("largest connected component: no layer -> data unchanged and the limitation is noted",
      largest_component(dmap, None)[0] is dmap and "not handled" in largest_component(dmap, None)[1])

from science import sign_decision  # noqa: E402

usgs_planes = (Plane(25.21, 74.77, -155.3), Plane(288.32, 66.22, -16.68))
FAST = [(30.0, 15.0, 1.0), (80.0, 25.0, 8.0)]   # two starts instead of six, to keep the tests fast
vecs = {"A1": [-0.62, -0.11, 0.78], "A2": [-0.55, -0.10, 0.83], "D1": [0.62, -0.11, 0.78], "D2": [0.55, -0.10, 0.83]}
sd_tracks = [Track(n, rng.uniform(-70, 70, 250), rng.uniform(-70, 70, 250), np.zeros(250), np.tile(v, (250, 1)))
             for n, v in vecs.items()]
# fault placed where the USGS finite-fault model is (top-edge centre ~16 km SSW of the epicentre), left-lateral plane
theta_ll = np.concatenate([[-0.05, -15.8, 55, 33.6, 0.5, 3.0], np.zeros(12)])
sd_tracks = [Track(t.name, t.east, t.north, p + rng.normal(0, 1.0, p.size), t.vec)
             for t, p in zip(sd_tracks, predict(theta_ll, sd_tracks, usgs_planes[1]))]
dec = sign_decision.decide(sd_tracks, usgs_planes, lat0, lon0, starts=FAST)
check("sign decision: left-lateral data in the +1 convention -> '+1' with all three criteria met",
      dec["decision"] == "+1" and all(dec["criteria_plus1"].values()) and dec["ffm"]["n_k_positive_3sigma"] >= 3,
      (dec["criteria_plus1"], dec["inversion"]))
dec_m = sign_decision.decide(sign_decision.flipped(sd_tracks), usgs_planes, lat0, lon0, starts=FAST)
check("sign decision: the same data with the opposite sign -> '-1'", dec_m["decision"] == "-1", dec_m["criteria_minus1"])
noise_tracks = [Track(t.name, t.east, t.north, rng.normal(0, 1.0, t.los.size), t.vec) for t in sd_tracks]
check("sign decision: noise -> 'undecided'",
      sign_decision.decide(noise_tracks, usgs_planes, lat0, lon0, starts=FAST)["decision"] == "undecided")
check("sign decision JSON: k, σ, k/σ and verdict per track, the rule text, both criteria sets",
      all({"k", "sigma_k", "k_over_sigma", "verdict"} <= set(v) for v in dec["ffm"]["per_track"].values())
      and "288/66/-17" in dec["rule"] and json.dumps(dec))
check("sign decision: fewer than 3 tracks can never accept a sign",
      sign_decision.decide(sd_tracks[:2], usgs_planes, lat0, lon0, starts=FAST)["decision"] == "undecided")

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

# ---------------------------------------------------------------- case assembly (science/cases.py)
import shutil  # noqa: E402
from types import SimpleNamespace  # noqa: E402

from config import CACHE_DIR  # noqa: E402
from science import cases as cs  # noqa: E402

work = tmp / "cases_work"
shutil.copytree(case_store.CASES_DIR, work, ignore=shutil.ignore_patterns("out", "figures"))
cs.CASES_DIR = work
(work / "out").mkdir()
(CACHE_DIR / "usgs").mkdir(parents=True, exist_ok=True)
(CACHE_DIR / "usgs" / "us6000u18k.json").write_text(json.dumps({**usgs_fixture, "id": "us6000u18k"}), encoding="utf-8")
(CACHE_DIR / "asf").mkdir(parents=True, exist_ok=True)
(CACHE_DIR / "asf" / "GUNW_TEST.json").write_text(json.dumps({"processingDate": "2026-10-13T08:00:00Z"}),
                                                  encoding="utf-8")
(CACHE_DIR / "asf" / "GUNW_TEST2.json").write_text(json.dumps({"processingDate": "2026-10-10T02:00:00Z"}),
                                                   encoding="utf-8")
fake_pairs = [SimpleNamespace(id="GUNW_TEST", name="GUNW_TEST", track=4, direction="ascending",
                              ref="20260930T110250", sec="20261012T110301", bbox=(-81.6, 6.9, -80.0, 8.4)),
              SimpleNamespace(id="GUNW_TEST2", name="GUNW_TEST2", track=141, direction="descending",
                              ref="20260927T231500", sec="20261009T231520", bbox=(-81.2, 7.1, -79.8, 8.6))]
cs._coseismic_pairs = lambda eid: fake_pairs if eid else []
fake_by_id = {p.id: p for p in fake_pairs}
cs._catalog_products = lambda ids: ([fake_by_id[i] for i in ids if i in fake_by_id],
                                    [f"product {i} not in the catalog" for i in ids if i not in fake_by_id])

from science import case_layers  # noqa: E402

map_arr = np.linspace(-5, 5, 400, dtype="float32").reshape(20, 20)
map_prof = {"transform": from_origin(-81.0, 8.0, 0.05, 0.05), "crs": "EPSG:4326"}


def fake_displacement_figure(case_id, p, lat, lon, fdir):
    """The real map_figure / render_png on a synthetic raster (no GUNW on the test machine)."""
    return case_layers.map_figure(
        case_id, map_arr, map_prof, fig_dir=fdir, fig_id=f"los_T{p.track}", kind="displacement", unit="cm",
        palette="diverging_displacement", vmin=-5.0, vmax=5.0, title={"fr": "m", "en": "m", "ar": "m"},
        caption={"template": "x", "params": {}}, source=p.id, period={"start": "2026-09-30", "end": "2026-10-12"},
        sign_convention="positive_toward_satellite")


case_layers.displacement_figure = fake_displacement_figure
mw_finding = {"id": "mw", "label": {"fr": "Mw", "en": "Mw", "ar": "Mw"},
              "nisar": {"value": 7.62, "uncertainty": 0.08, "unit": "Mw", "sigma": 1},
              "reference": {"value": 7.7, "uncertainty": 0.1, "unit": "Mw", "sigma": 1},
              "reference_source": {"name": "USGS", "url": "https://earthquake.usgs.gov/"}, "agreement": "agree"}
(work / "out" / "panama-2026_fit.png").write_bytes(b"\x89PNG\r\n\x1a\n")
fault_out = {"stable": True, "findings": [mw_finding], "limits": [{"fr": "l", "en": "l", "ar": "l"}],
             "figures": [{"id": "fault_fit", "path": "panama-2026_fit.png", "kind": "image"}]}
(work / "out" / "panama-2026.json").write_text(json.dumps(fault_out), encoding="utf-8")
(work / "out" / "panama-2026_exposure.json").write_text(json.dumps({"exposure": case_exp}), encoding="utf-8")
pan = cs.build_quake("panama-2026", tmp / "results", "us6000u18k", offline=True)
check("cases: Panama with fault, exposure, USGS and ASF inputs becomes FINAL with no placeholder",
      pan["status"] == "final" and pan["placeholders"] == [], pan["placeholders"])
check("cases: full timeline, sorted: USGS origin, every NISAR acquisition time of the pairs, ASF publication dates",
      [t["at"] for t in pan["timeline"]] == ["2026-09-27T23:15:00Z", "2026-09-30T11:02:50Z", "2026-10-09T17:56:06Z",
                                              "2026-10-09T23:15:20Z", "2026-10-10T02:00:00Z", "2026-10-12T11:03:01Z",
                                              "2026-10-13T08:00:00Z"]
      and pan["date"] == "2026-10-09T17:56:06Z", [t["at"] for t in pan["timeline"]])
maps = [f for f in pan["figures"] if f.get("layer")]
lay = maps[0]["layer"] if maps else {}
check("cases: one map figure with a RasterLayer per co-seismic pair (PNG rendered with the frontend palette, served)",
      len(maps) == 2 and maps[0]["kind"] == "map" and lay["palette"] == "diverging_displacement"
      and lay["unit"] == "cm" and lay["sign_convention"] == "positive_toward_satellite"
      and np.allclose(lay["bounds"], [-81.0, 7.0, -80.0, 8.0], atol=0.02)
      and case_store.figure_path("panama-2026", lay["url"].rsplit("/", 1)[1], work) is not None, lay)
check("cases: headline numbers come from the Mw finding; the fit figure is copied and served under /api/cases",
      "7.62 ± 0.08" in pan["headline"]["text"]["en"]
      and any(f["url"] == "/api/cases/panama-2026/figures/panama-2026_fit.png" for f in pan["figures"])
      and case_store.figure_path("panama-2026", "panama-2026_fit.png", work) is not None)
check("cases: unsafe figure names are refused (traversal, other case, unknown extension)",
      case_store.figure_path("panama-2026", "../panama-2026.json", work) is None
      and case_store.figure_path("nope", "panama-2026_fit.png", work) is None
      and case_store.figure_path("panama-2026", "x.exe", work) is None)
(work / "out" / "panama-2026.json").write_text(json.dumps({**fault_out, "stable": False, "findings": [],
                                                           "unstable_reasons": ["variance reduction 0.3 < 0.5"]}),
                                              encoding="utf-8")
pan2 = cs.build_quake("panama-2026", tmp / "results", "us6000u18k", offline=True)
check("cases: unstable fault -> draft, 'Magnitude not estimated' with the reason in limits",
      pan2["status"] == "draft" and any("Magnitude not estimated" in lim["text"]["en"] and "0.3 < 0.5" in lim["text"]["en"]
                                        for lim in pan2["limits"]), pan2["placeholders"])

res_dir = tmp / "results"
for label, offset in (("none", 6.0), ("iono", 1.0)):
    d = res_dir / "gps" / f"gps_{label}"
    d.mkdir(parents=True)
    gps_pairs = [{"gps_los_mm": g, "nisar_los_mm": g + (offset if i % 2 else -offset), "date_after": f"202610{10 + i}",
                  "product": "GUNW_TEST"} for i, g in enumerate([1.0, 5.0, -3.0, 8.0, 2.0, -1.0, 4.0, 0.0])]
    (d / "gps_CEU1.json").write_text(json.dumps({"station": {"station": "CEU1", "lat": 35.89, "lon": -5.31},
                                                 "pairs": gps_pairs}), encoding="utf-8")
iono = cs.build_iono(res_dir, offline=True)
by = {f["id"]: f["nisar"] for f in iono["findings"]}
check("cases: ionosphere-gps RMS before/after from the GPS reports, uncertainty RMS/sqrt(2n), FINAL",
      iono["status"] == "final" and by["rms_before"]["value"] == 6.0 and by["rms_after"]["value"] == 1.0
      and abs(by["rms_before"]["uncertainty"] - 6.0 / 4.0) < 0.01, (iono["placeholders"], by))
check("cases: ionosphere-gps location around the stations, date = latest NISAR acquisition, map + timeline of its pairs",
      abs(iono["location"]["lat"] - 35.89) < 1e-6 and iono["date"] == "2026-10-17T00:00:00Z"
      and any(f.get("layer") for f in iono["figures"]) and len(iono["timeline"]) == 3, iono["placeholders"])

if os.environ.get("NISAR_CASE_DUMP"):          # final cases for tools/frontend_contract/validate.ts
    dump_dir = Path(os.environ["NISAR_CASE_DUMP"])
    dump_dir.mkdir(parents=True, exist_ok=True)
    for name, built in (("panama-final", pan), ("ionosphere-final", iono)):
        (dump_dir / f"case__{name}.json").write_text(json.dumps(built, ensure_ascii=False), encoding="utf-8")

(res_dir / "haouz-flood-2026").mkdir()
(res_dir / "haouz-flood-2026" / "findings.json").write_text(json.dumps({"findings": [
    {"id": "flooded_area", "label": {"fr": "a", "en": "a", "ar": "a"},
     "nisar": {"value": 3.2, "uncertainty": 0.4, "unit": "km2", "sigma": 1}, "reference": None,
     "reference_source": None, "agreement": "no_reference"}], "limits": [{"fr": "l", "en": "l", "ar": "l"}]}),
    encoding="utf-8")
flood = cs.build_flood("haouz-flood-2026", res_dir, offline=True)
check("cases: a flood case without date / products / map / exposure stays a draft and says what is missing",
      flood["status"] == "draft" and any("'date'" in p for p in flood["placeholders"])
      and any("'products'" in p for p in flood["placeholders"])
      and "figures: no map with a layer" in flood["placeholders"]
      and any("exposure" in p for p in flood["placeholders"]), flood["placeholders"])
(res_dir / "haouz-flood-2026" / "findings.json").write_text(json.dumps({"findings": [{"id": "x"}]}), encoding="utf-8")
try:
    cs.build_flood("haouz-flood-2026", res_dir, offline=True)
    check("cases: a results/<id>/findings.json that breaks the Finding contract is refused", False)
except cs.CaseInputError:
    check("cases: a results/<id>/findings.json that breaks the Finding contract is refused", True)

passed = sum(ok for _, ok in results)
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
