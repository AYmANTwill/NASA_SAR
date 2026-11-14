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
    print(("PASS " if cond else "FAIL ") + name + (f"  — {detail}" if detail and not cond else ""))


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

passed = sum(ok for _, ok in results)
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
