"""Index of the NISAR products already downloaded (built from the data folder)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

import rasterio
from rasterio.warp import transform_bounds

from config import DATA_DIR


def _d(s: str) -> date:
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def parse_name(name: str) -> dict:
    p = name.split("_")
    stamps = [s for s in p if len(s) == 15 and s[8] == "T"]
    ref = stamps[0] if stamps else ""
    sec = stamps[2] if len(stamps) >= 4 else ref
    return dict(level=p[3], track=int(p[5]), direction="ascending" if p[6] == "A" else "descending",
                frame=int(p[7]), ref=ref, sec=sec, span_days=(_d(sec) - _d(ref)).days if ref else 0)


# layer key -> file-name suffix written by download_all.py, per product level
LAYER_FILES = {
    "GUNW": {"phase": "unwrappedPhase.tif", "coherence": "coherenceMagnitude.tif",
             "conncomp": "connectedComponents.tif", "iono": "ionospherePhaseScreen.tif"},
    "GCOV": {"hh": "HHHH.tif", "hv": "HVHV.tif", "vv": "VVVV.tif"},
    "GOFF": {"along": "alongTrackOffset.tif", "range": "slantRangeOffset.tif",
             "peak": "correlationSurfacePeak.tif"},
}
MAIN_LAYER = {"GUNW": "phase", "GCOV": "hh", "GOFF": "along"}


@dataclass(eq=False)
class Product:
    name: str
    folder: Path
    level: str
    track: int
    frame: int
    direction: str
    ref: str
    sec: str
    span_days: int
    bbox: tuple
    files: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return f"{self.level}_T{self.track:03d}_F{self.frame:03d}_{self.ref[:8]}_{self.sec[:8]}"

    @property
    def geometry(self) -> tuple:
        return (self.track, self.frame)

    def covers(self, lat: float, lon: float) -> bool:
        return self.bbox[0] <= lon <= self.bbox[2] and self.bbox[1] <= lat <= self.bbox[3]

    def summary(self) -> dict:
        return dict(id=self.id, level=self.level, track=self.track, frame=self.frame,
                    direction=self.direction, ref=self.ref, sec=self.sec,
                    span_days=self.span_days, bbox=self.bbox, layers=sorted(self.files))


def _pick(folder: Path, suffix: str):
    """Prefer frequency A and the unwrapped-interferogram grid (real GUNW files also hold a
    full-resolution wrappedInterferogram coherence that the recipes do not use)."""
    hits = sorted(folder.glob(f"*{suffix}"), key=lambda p: (p.name.startswith("freqB_"),
                                                             p.name.startswith("wrappedInterferogram")))
    return hits[0] if hits else None


def _sme2_bbox(h5_path: Path):
    """Footprint of an SME2 file from its coordinate datasets."""
    import h5py
    from pyproj import Transformer
    with h5py.File(h5_path, "r") as h5:
        xs, ys, epsg = [], [], None
        def visit(name, obj):
            nonlocal epsg
            if isinstance(obj, h5py.Dataset):
                base = name.split("/")[-1]
                if base == "xCoordinates":
                    xs.append(obj[()])
                elif base == "yCoordinates":
                    ys.append(obj[()])
                elif base == "projection":
                    epsg = int(obj.attrs.get("epsg_code", obj[()]))
        h5.visititems(visit)
    if not xs or not ys:
        return None
    x, y = xs[0], ys[0]
    if epsg in (None, 4326):
        return float(x.min()), float(y.min()), float(x.max()), float(y.max())
    t = Transformer.from_crs(epsg, 4326, always_xy=True)
    lon, lat = t.transform([x.min(), x.max(), x.min(), x.max()], [y.min(), y.min(), y.max(), y.max()])
    return min(lon), min(lat), max(lon), max(lat)


@lru_cache(maxsize=1)
def load() -> list[Product]:
    out = []
    for level in ["GUNW", "GCOV", "GOFF", "SME2"]:
        level_dir = DATA_DIR / level
        if not level_dir.exists():
            continue
        for folder in level_dir.iterdir():
            if not folder.is_dir() or not (folder / "_DONE").exists():
                continue
            try:
                meta = parse_name(folder.name)
            except Exception:
                continue
            files, bbox = {}, None
            if level in LAYER_FILES:
                for k, suf in LAYER_FILES[level].items():
                    f = _pick(folder, suf)
                    if f:
                        files[k] = f
                if MAIN_LAYER[level] not in files:
                    continue
                with rasterio.open(files[MAIN_LAYER[level]]) as src:
                    if src.crs:
                        bbox = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
            else:
                h5 = next(folder.glob("*.h5"), None)
                if not h5:
                    continue
                files["h5"] = h5
                try:
                    bbox = _sme2_bbox(h5)
                except Exception:
                    bbox = None
            out.append(Product(name=folder.name, folder=folder, files=files,
                               bbox=tuple(round(v, 4) for v in bbox) if bbox else (-180, -90, 180, 90),
                               **{k: meta[k] for k in ["level", "track", "frame", "direction", "ref", "sec",
                                                       "span_days"]}))
    return sorted(out, key=lambda p: (p.level, p.track, p.frame, p.ref))


def refresh():
    load.cache_clear()
    return load()


def find(lat: float, lon: float, level: str = "GUNW") -> list[Product]:
    return sorted([p for p in load() if p.level == level and p.covers(lat, lon)],
                  key=lambda p: p.sec, reverse=True)


def straddling(products: list[Product], event: str) -> list[Product]:
    return [p for p in products if p.ref <= event <= p.sec]


def before(products: list[Product], event: str) -> list[Product]:
    return [p for p in products if p.sec < event]


def by_id(pid: str) -> Product | None:
    return next((p for p in load() if p.id == pid), None)
