"""USGS event data for the fault inversion: origin, magnitude and moment-tensor nodal planes.

The event GeoJSON is fetched once from the USGS detail feed and cached in <NISAR_CACHE>/usgs/<id>.json.
With NISAR_OFFLINE=1 only the cache is used.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import requests

from config import CACHE_DIR

DETAIL_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/detail/{id}.geojson"
EVENT_PAGE = "https://earthquake.usgs.gov/earthquakes/eventpage/{id}"
TIMEOUT_S = 30
USER_AGENT = "nisar-pulse/1.0 (NASA Space Apps 2026)"


class UsgsError(RuntimeError):
    """The USGS event or its moment tensor could not be obtained."""


@dataclass(frozen=True)
class Plane:
    strike: float
    dip: float
    rake: float


@dataclass(frozen=True)
class UsgsEvent:
    id: str
    lat: float
    lon: float
    depth_km: float
    time_ms: int
    magnitude: float
    magnitude_type: str
    planes: tuple[Plane, Plane]
    mt_source: str          # which moment-tensor product the planes come from
    url: str


def _cache_path(event_id: str) -> Path:
    return CACHE_DIR / "usgs" / f"{event_id}.json"


def fetch(event_id: str) -> dict:
    """The raw GeoJSON (cached). Raises UsgsError when it is neither cached nor downloadable."""
    path = _cache_path(event_id)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    if os.environ.get("NISAR_OFFLINE") == "1":
        raise UsgsError(f"{event_id}: not in the cache ({path}) and NISAR_OFFLINE=1")
    try:
        r = requests.get(DETAIL_URL.format(id=event_id), timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as exc:
        raise UsgsError(f"{event_id}: USGS request failed: {exc}") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def parse(data: dict) -> UsgsEvent:
    try:
        props = data["properties"]
        lon, lat, depth = data["geometry"]["coordinates"][:3]
        event_id = data["id"]
    except (KeyError, TypeError, ValueError) as exc:
        raise UsgsError(f"unexpected USGS GeoJSON: {exc}") from exc
    tensors = (props.get("products") or {}).get("moment-tensor") or []
    for mt in tensors:
        p = mt.get("properties", {})
        try:
            planes = tuple(Plane(float(p[f"nodal-plane-{i}-strike"]), float(p[f"nodal-plane-{i}-dip"]),
                                 float(p[f"nodal-plane-{i}-rake"])) for i in (1, 2))
        except (KeyError, ValueError):
            continue
        src = f"{mt.get('source', '?')} {p.get('derived-magnitude-type', '')}".strip()
        return UsgsEvent(event_id, float(lat), float(lon), float(depth), int(props["time"]), float(props["mag"]),
                         str(props.get("magType", "")), planes, src, EVENT_PAGE.format(id=event_id))
    raise UsgsError(f"{event_id}: no moment tensor with nodal planes in the USGS products "
                    f"(products: {sorted((props.get('products') or {}).keys())})")


def event(event_id: str) -> UsgsEvent:
    return parse(fetch(event_id))


# ---------------------------------------------------------------- nodal-plane geometry (ENU vectors)
def _basis(strike: float, dip: float) -> tuple[np.ndarray, np.ndarray]:
    """(strike unit vector, down-dip unit vector) in east-north-up."""
    phi, dr = np.radians(strike), np.radians(dip)
    s = np.array([np.sin(phi), np.cos(phi), 0.0])
    d = np.cos(dr) * np.array([np.cos(phi), -np.sin(phi), 0.0]) + np.sin(dr) * np.array([0.0, 0.0, -1.0])
    return s, d


def _vectors(p: Plane) -> tuple[np.ndarray, np.ndarray]:
    """(upward fault normal, slip vector of the hanging wall) in east-north-up."""
    s, d = _basis(p.strike, p.dip)
    n = np.cross(s, d)
    n = n if n[2] >= 0 else -n
    rake = np.radians(p.rake)
    return n, np.cos(rake) * s - np.sin(rake) * d


def _plane_from(n: np.ndarray, u: np.ndarray) -> Plane:
    if n[2] < 0:            # keep the normal upward; flipping both keeps the moment tensor
        n, u = -n, -u
    dip = float(np.degrees(np.arccos(np.clip(n[2], -1, 1))))
    strike = float((np.degrees(np.arctan2(n[0], n[1])) - 90.0) % 360.0)
    s, d = _basis(strike, dip)
    rake = float(np.degrees(np.arctan2(-np.dot(u, d), np.dot(u, s))))
    return Plane(strike, dip, rake)


def auxiliary_plane(p: Plane) -> Plane:
    """The other nodal plane of the same double couple (normal and slip vector swapped)."""
    n, u = _vectors(p)
    return _plane_from(u, n)
