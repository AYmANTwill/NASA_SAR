"""decompose.los_vector: no silent fallback to the nominal geometry.
Usage (from backend/):  python tests/test_decompose.py"""
import logging
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp(prefix="nisar_decompose_"))
os.environ.update(NISAR_DATA=str(tmp / "data"), NISAR_CACHE=str(tmp / "cache"), NISAR_OFFLINE="1")
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from recipes import decompose  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  — {detail}" if not cond and str(detail) else ""))


class Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


cap = Capture()
logging.getLogger("recipes.decompose").addHandler(cap)


def product(name, direction="descending"):
    folder = tmp / name
    folder.mkdir()
    return SimpleNamespace(id=name, folder=folder, direction=direction)


# a good file: the vector comes from the file
p = product("good")
nominal = decompose._nominal("descending")
np.savez(p.folder / "radar_geometry.npz", **{"a__losUnitVectorX": np.full((3, 3), nominal[0]),
                                             "a__losUnitVectorY": np.full((3, 3), nominal[1])})
v, src = decompose.los_vector(p)
check("good npz: source is exactly 'file' and no warning", src == "file" and np.allclose(v[:2], nominal[:2]) and not cap.messages,
      (src, cap.messages))

# unreadable npz: the error is logged and named in the source
p = product("corrupt")
(p.folder / "radar_geometry.npz").write_bytes(b"not a zip file")
cap.messages.clear()
v, src = decompose.los_vector(p)
check("corrupt npz: source 'nominal (npz error: ...)' and a warning is logged",
      src.startswith("nominal (npz error:") and len(cap.messages) == 1 and np.allclose(v, nominal), (src, cap.messages))

# missing file and missing keys: also named
p = product("missing")
cap.messages.clear()
_, src = decompose.los_vector(p)
check("no npz: source says so and a warning is logged", src == "nominal (no radar_geometry.npz)" and len(cap.messages) == 1, (src, cap.messages))
p = product("nokeys")
np.savez(p.folder / "radar_geometry.npz", other=np.zeros(2))
cap.messages.clear()
_, src = decompose.los_vector(p)
check("npz without losUnitVector keys: source says so", "no losUnitVectorX/Y" in src and len(cap.messages) == 1, (src, cap.messages))

# combine reports an approximate geometry when one pair fell back
asc, desc = product("asc", "ascending"), product("desc2")
np.savez(desc.folder / "radar_geometry.npz", **{"a__losUnitVectorX": np.full((3, 3), nominal[0]),
                                                "a__losUnitVectorY": np.full((3, 3), nominal[1])})
check("combine: geometry_source is 'nominal (approximate)' when a pair has no file",
      decompose.combine(1.0, asc, 1.0, desc)["geometry_source"] == "nominal (approximate)")

passed = sum(ok for _, ok in results)
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
