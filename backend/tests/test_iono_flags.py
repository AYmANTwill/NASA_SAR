"""corrections.already_applied: the geocoding flags do not count as "the phase is already corrected".
Usage (from backend/):  python tests/test_iono_flags.py"""
import os
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp(prefix="nisar_flags_"))
os.environ.update(NISAR_DATA=str(tmp / "data"), NISAR_CACHE=str(tmp / "cache"), NISAR_OFFLINE="1")
sys.path.insert(0, str(ROOT))

from recipes import corrections  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  — {detail}" if not cond and str(detail) else ""))


P = "science/LSAR/GUNW/metadata/processingInformation/"
GEO = {P + "parameters/geocoding/azimuthIonosphericCorrectionApplied": "True",
       P + "parameters/geocoding/rangeIonosphericCorrectionApplied": "True",
       P + "parameters/geocoding/hydrostaticTroposphericCorrectionApplied": "True",
       P + "parameters/geocoding/wetTroposphericCorrectionApplied": "True"}


def attrs(flags):
    return {"source": "x.h5", "datasets": {"unwrappedPhase": {"description": "Unwrapped interferogram between HH layers"}},
            "flags": flags}


def test_geocoding_flags_do_not_count():
    check("geocoding flags True: iono is not 'already applied'", corrections.already_applied("iono", attrs(GEO)) is False)
    check("geocoding flags True: tropo is not 'already applied'", corrections.already_applied("tropo", attrs(GEO)) is False)
    phase_flag = {P + "algorithms/unwrappedInterferogram/ionosphereCorrectionApplied": "True"}
    check("a flag under unwrappedInterferogram still counts", corrections.already_applied("iono", attrs({**GEO, **phase_flag})) is True)
    check("the same flag set to False does not count",
          corrections.already_applied("iono", attrs({k: "False" for k in phase_flag})) is False)
    check("the unwrappedPhase description still counts",
          corrections.already_applied("iono", {"source": "x.h5", "flags": GEO, "datasets": {"unwrappedPhase": {
              "description": "Unwrapped phase, ionosphere corrected"}}}) is True)
    check("no raw file read: unknown (None)", corrections.already_applied("iono", {"source": None, "flags": {}, "datasets": {}}) is None)


test_geocoding_flags_do_not_count()
passed = sum(ok for _, ok in results)
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
