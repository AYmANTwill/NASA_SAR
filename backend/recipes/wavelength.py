"""Radar wavelength of a product: lambda = c / centerFrequency, read per product.

NISAR L-band runs in several range-bandwidth modes with different centre frequencies (e.g. 1239 MHz in the 40 MHz
mode, lambda = 0.24196 m; 1229 MHz in the 20 MHz mode, lambda = 0.24393 m), so one constant is wrong for some
products. Sources, in order:
1. radar_geometry.npz, a key ending in "centerFrequency" (if the downloader stores it);
2. the raw .h5 kept next to the layers, grids/frequencyA/centerFrequency;
3. config.WAVELENGTH_M, with a warning.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import numpy as np

from config import WAVELENGTH_M

log = logging.getLogger(__name__)
C_M_S = 299_792_458.0
FREQ_SUFFIX = "frequencyA/centerFrequency"
L_BAND_HZ = (1.0e9, 2.0e9)       # sanity range: anything else is a unit or parsing error


def _valid(f: float) -> bool:
    return bool(np.isfinite(f)) and L_BAND_HZ[0] <= f <= L_BAND_HZ[1]


def _from_npz(folder: Path) -> float | None:
    npz = folder / "radar_geometry.npz"
    if not npz.is_file():
        return None
    with np.load(npz) as z:
        key = next((k for k in z.files if k.endswith("centerFrequency")), None)
        return float(np.ravel(z[key])[0]) if key else None


def _from_h5(folder: Path) -> float | None:
    raw = next(iter(sorted(folder.glob("*.h5"))), None)
    if raw is None:
        return None
    import h5py
    found = []
    with h5py.File(raw, "r") as h5:
        h5.visititems(lambda name, obj: found.append(name)
                      if isinstance(obj, h5py.Dataset) and name.endswith(FREQ_SUFFIX) else None)
        return float(np.ravel(h5[found[0]][()])[0]) if found else None


@lru_cache(maxsize=256)
def _for_folder(folder: Path) -> tuple[float, str]:
    for source, reader in (("radar_geometry.npz", _from_npz), ("raw .h5", _from_h5)):
        try:
            f = reader(folder)
        except (OSError, KeyError, ValueError) as exc:
            log.warning("%s: cannot read centerFrequency from %s: %s", folder.name, source, exc)
            continue
        if f is not None and _valid(f):
            return C_M_S / f, f"c / centerFrequency ({f / 1e6:.1f} MHz, {source})"
        if f is not None:
            log.warning("%s: centerFrequency %r Hz from %s is not L-band, ignored", folder.name, f, source)
    log.warning("%s: no centerFrequency found, using config WAVELENGTH_M = %s m", folder.name, WAVELENGTH_M)
    return WAVELENGTH_M, "config WAVELENGTH_M (no centerFrequency in the product)"


def wavelength_m(p) -> tuple[float, str]:
    """(wavelength in metres, where it came from) for a catalog Product (anything with a .folder)."""
    return _for_folder(Path(p.folder))
