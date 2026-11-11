"""Combine ascending and descending line-of-sight values into vertical and east-west motion.

LOS = e*E + n*N + u*U with (e, n, u) the ground-to-satellite unit vector. With two geometries and
north motion neglected (polar orbits are almost blind to it), solve a 2x2 system for (E, U)."""
from __future__ import annotations

import numpy as np

from catalog import Product

# Nominal fall-back geometry if the file's line-of-sight vectors cannot be read.
# NISAR granules are labelled "left looking" on ASF.
LOOK_SIDE = "left"
NOMINAL = {"ascending": dict(heading=-12.0, incidence=37.0), "descending": dict(heading=192.0, incidence=37.0)}


def _nominal(direction: str) -> np.ndarray:
    g = NOMINAL[direction]
    inc, head = np.radians(g["incidence"]), np.radians(g["heading"])
    # ground-to-satellite azimuth: heading + 90 deg for a left-looking radar, heading - 90 for right-looking
    az = head + (np.pi / 2 if LOOK_SIDE == "left" else -np.pi / 2)
    return np.array([np.sin(inc) * np.sin(az), np.sin(inc) * np.cos(az), np.cos(inc)])


def los_vector(p: Product) -> tuple[np.ndarray, str]:
    """Ground-to-satellite unit vector (east, north, up). Tries radar_geometry.npz first."""
    npz = p.folder / "radar_geometry.npz"
    if npz.exists():
        try:
            z = np.load(npz)
            kx = next((k for k in z.files if k.endswith("losUnitVectorX")), None)
            ky = next((k for k in z.files if k.endswith("losUnitVectorY")), None)
            if kx and ky:
                e, n = float(np.nanmean(z[kx])), float(np.nanmean(z[ky]))
                u = float(np.sqrt(max(0.0, 1 - e * e - n * n)))
                v = np.array([e, n, u])
                # the file may store satellite-to-ground: flip if it points away from the nominal side
                if np.dot(v[:2], _nominal(p.direction)[:2]) < 0:
                    v[:2] *= -1
                return v, "file"
        except Exception:
            pass
    return _nominal(p.direction), "nominal"


def combine(asc_value: float, asc_p: Product, desc_value: float, desc_p: Product) -> dict:
    va, sa = los_vector(asc_p)
    vd, sd = los_vector(desc_p)
    M = np.array([[va[0], va[2]], [vd[0], vd[2]]])
    east, up = np.linalg.solve(M, np.array([asc_value, desc_value]))
    return {"east": round(float(east), 2), "up": round(float(up), 2),
            "geometry_source": "file" if sa == sd == "file" else "nominal (approximate)"}
