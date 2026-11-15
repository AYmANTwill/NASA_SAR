"""Checks of the Water U-Net outputs against the case contract (no internet, no GPU, no data root needed).
Usage (from backend/):  python tests/test_water.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pydantic import ValidationError  # noqa: E402
from science import case_models as cm  # noqa: E402

OUT = ROOT / "water" / "outputs"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  — {detail}" if detail else ""))


def valid(model, obj):
    try:
        model.model_validate(obj)
        return True, ""
    except ValidationError as e:
        return False, str(e).splitlines()[0]


# Haouz extra finding
h = json.loads((OUT / "haouz_open_water.json").read_text(encoding="utf-8"))
for f in h["findings"]:
    ok, err = valid(cm.Finding, f)
    check(f"haouz finding {f['id']} validates as Finding", ok, err)
for g in h["figures"]:
    ok, err = valid(cm.Figure, g)
    check(f"haouz figure {g['id']} validates as Figure", ok, err)
    check(f"haouz figure {g['id']} file exists", (ROOT / g["url"]).exists(), g["url"])
f = h["findings"][0]
check("haouz finding renamed open_water_change", f["id"] == "open_water_change")
check("haouz finding has non-zero uncertainty", f["nisar"]["uncertainty"] > 0)
check("haouz finding claims no flooded area (consistent with zero at 2σ)",
      abs(f["nisar"]["value"]) <= 2 * f["nisar"]["uncertainty"] / f["nisar"]["sigma"])
check("haouz limits mention the 12-day revisit", any("12-day" in l["en"] for l in h["limits"]))

# Reservoir case
c = json.loads((OUT / "reservoir_case.json").read_text(encoding="utf-8"))
for f in c["findings"]:
    ok, err = valid(cm.Finding, f)
    check(f"reservoir finding {f['id']} validates as Finding", ok, err)
    check(f"reservoir finding {f['id']} has non-zero uncertainty", f["nisar"]["uncertainty"] > 0)
for g in c["figures"]:
    ok, err = valid(cm.Figure, g)
    check(f"reservoir figure {g['id']} validates as Figure", ok, err)
    check(f"reservoir figure {g['id']} file exists", (ROOT / g["url"]).exists(), g["url"])
for name, model, obj in (("location", cm.Location, c["location"]), ("headline", cm.TemplatedText, c["headline"])):
    ok, err = valid(model, obj)
    check(f"reservoir {name} validates", ok, err)
check("reservoir timeline items validate", all(valid(cm.TimelineItem, t)[0] for t in c["timeline"]), f"{len(c['timeline'])} passes")
check("reservoir limits validate", len(c["limits"]) >= 1 and all(valid(cm.TemplatedText, l)[0] for l in c["limits"]))
if "bin-el-ouidane-2026" in cm.CaseId.__args__:
    ok, err = valid(cm.CaseStudy, c)
    check("reservoir case validates as CaseStudy", ok, err)
else:
    print("SKIP reservoir CaseStudy: id not yet in CaseId (see backend/water/INTEGRATION_REQUESTS.md)")
held = json.loads((OUT / "heldout_eval.json").read_text())
iou = next(f for f in c["findings"] if f["id"] == "heldout_iou")
check("headline IoU is the held-out-track value", abs(iou["nisar"]["value"] - 100 * held["headline_heldout"]["iou"]) < 0.01)

# Map layers
ri = json.loads((OUT / "raster_index.json").read_text())
check("raster index uses EPSG:4326", ri["crs"] == "EPSG:4326")
for layer in ri["layers"]:
    w, s, e, n = layer["bounds"]
    check(f"layer {layer['id']}: file exists and bounds ordered", (OUT / layer["file"]).exists() and w < e and s < n)

# Size budget
size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file()) / 1e6
check("backend/water/outputs under 50 MB", size < 50, f"{size:.1f} MB")

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
