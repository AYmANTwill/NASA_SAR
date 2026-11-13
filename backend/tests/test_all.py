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
        m["hydrostaticTroposphericPhaseScreen"] = np.ones((2, 4, 4), "float32")
        m["wetTroposphericPhaseScreen"] = np.ones((2, 4, 4), "float32")
        if with_tide:
            m["solidEarthTidePhase"] = np.ones((2, 4, 4), "float32")


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
      and any("solidEarthTidePhase" in k for k in npz2) and rep2["manquantes"] == [], rep2)
h5b = tmp / "gunw_b.h5"
make_gunw_h5(h5b, with_tide=False)
da.extract(h5b, tmp / "x3" / "GUNW" / "p3", "GUNW", extra=True)
check("extract extra: a requested layer absent from the file is reported, not silently ignored",
      da.extra_missing(tmp / "x3" / "GUNW" / "p3") == ["solidEarthTide"], da.extra_missing(tmp / "x3" / "GUNW" / "p3"))

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
shutil.copy(h5b, part3)                                  # h5b has no solidEarthTidePhase
fin3 = tmp / "x5" / "GUNW" / row3["name"]
k3 = da.finish(row3, part3, fin3, fin3 / "_DONE")        # no --keep-raw
raw3 = fin3 / (row3["name"] + ".h5")
done3 = json.loads((fin3 / "_DONE").read_text())
check("safety net: missing extra layer -> raw .h5 kept WITHOUT --keep-raw, _DONE lists the missing name",
      raw3.exists() and not part3.exists() and done3.get("raw_kept_missing_layers") == ["solidEarthTide"]
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
      and len(allp.stdout.strip().splitlines()) == 14 and nofile.returncode == 1, (len(lst.stdout.splitlines()), len(allp.stdout.splitlines())))

check("plan_nisar.json still byte-identical after all Morocco checks",
      hashlib.sha256(PLAN_NISAR.read_bytes()).hexdigest() == sha_before)

n_ok = sum(ok for _, ok in results)
print(f"\n{n_ok}/{len(results)} checks passed")
sys.exit(0 if n_ok == len(results) else 1)
