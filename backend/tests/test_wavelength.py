"""Per-product wavelength (recipes/wavelength.py): lambda = c / centerFrequency, config fallback with a warning.
Usage (from backend/):  python tests/test_wavelength.py"""
import logging
import os
import sys
import tempfile
from pathlib import Path
from dataclasses import dataclass, field

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp(prefix="nisar_wavelength_"))
os.environ.update(NISAR_DATA=str(tmp / "data"), NISAR_CACHE=str(tmp / "cache"), NISAR_OFFLINE="1")
sys.path.insert(0, str(ROOT))

import h5py  # noqa: E402
import numpy as np  # noqa: E402

import raster  # noqa: E402
from config import WAVELENGTH_M  # noqa: E402
from recipes import displacement  # noqa: E402
from recipes import wavelength as wlmod  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  — {detail}" if not cond and str(detail) else ""))


@dataclass(frozen=True)
class FakeProduct:          # hashable, like catalog.Product (displacement._los_cm is lru_cached)
    folder: Path
    id: str
    files: dict = field(default_factory=lambda: {"phase": "unused"}, hash=False, compare=False)


def product(name: str, h5_hz=None, npz_hz=None) -> FakeProduct:
    folder = tmp / name
    folder.mkdir()
    if h5_hz is not None:
        with h5py.File(folder / f"{name}.h5", "w") as h5:
            h5["science/LSAR/GUNW/grids/frequencyA/centerFrequency"] = np.float64(h5_hz)
    if npz_hz is not None:
        np.savez(folder / "radar_geometry.npz",
                 science__LSAR__GUNW__grids__frequencyA__centerFrequency=np.array([npz_hz]))
    return FakeProduct(folder, name)


class Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


cap = Capture()
logging.getLogger("recipes.wavelength").addHandler(cap)

p40 = product("mode40", h5_hz=1239e6)
wl40, src = wlmod.wavelength_m(p40)
check("40 MHz mode: 1239 MHz in the raw .h5 gives lambda = 0.24196 m",
      abs(wl40 - 0.24196) < 1e-5 and ".h5" in src, (wl40, src))
wl, src = wlmod.wavelength_m(product("mode20", h5_hz=1229e6))
check("20 MHz mode: 1229 MHz gives lambda = 0.24393 m", abs(wl - 0.24393) < 1e-5, (wl, src))
wl, src = wlmod.wavelength_m(product("npz", h5_hz=1229e6, npz_hz=1239e6))
check("radar_geometry.npz is read first when it stores centerFrequency",
      abs(wl - 0.24196) < 1e-5 and "npz" in src, (wl, src))
wl, src = wlmod.wavelength_m(product("none"))
check("no centerFrequency: config WAVELENGTH_M, with a warning",
      wl == WAVELENGTH_M and "config" in src and any("no centerFrequency" in m for m in cap.messages), cap.messages)
wl, src = wlmod.wavelength_m(product("bad", h5_hz=1239.0))       # MHz written as Hz
check("a centerFrequency outside L-band is ignored (fallback + warning)",
      wl == WAVELENGTH_M and any("not L-band" in m for m in cap.messages), cap.messages)

# displacement scales with the product's own wavelength: one fringe = lambda / 2
phase = np.full((4, 4), -2 * np.pi, dtype="float32")
original_read = raster.read
raster.read = lambda path: (phase.copy(), {"transform": None, "crs": None, "width": 4, "height": 4})
try:
    disp, _coh, _prof, _notes, report = displacement._los_cm(p40, (), ())
finally:
    raster.read = original_read
expected = displacement.LOS_SIGN * wl40 / 2 * 100
check("displacement uses the product wavelength: one fringe = 12.10 cm in the 40 MHz mode (11.92 cm before)",
      abs(float(np.nanmean(disp)) - expected) < 1e-3 and report["wavelength"]["value_m"] == wl40,
      (float(np.nanmean(disp)), expected))

passed = sum(ok for _, ok in results)
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
