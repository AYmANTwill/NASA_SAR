"""Optional phase corrections for GUNW interferograms: ionosphere, troposphere, solid-earth tide.

Setting: NISAR_CORRECTIONS (comma list of iono, tropo, tide, or "none"). Default "iono" = the behaviour before this
module existed (the product's ionospherePhaseScreen is subtracted when present). Troposphere and tide are OFF by
default: turn them on only if backend/noise_report.py shows they lower the noise floor on real data.

Nothing is assumed silently. For every correction the answer's facts record: applied or not and why, the convention
used, the units and where they came from (the raw .h5 attributes when a raw file was kept with --keep-raw, otherwise
"assumed"), whether a processingInformation flag says the product already applied it (then it is NOT applied again),
and for the cubes the terrain height used.

Convention: corrected = unwrappedPhase - screen (ISCE3 / NISAR GUNW: the screens are given in the interferogram's
phase convention, the ionosphere screen is used the same way). The noise report also measures the opposite sign.
Cubes (troposphere, tide) live on metadata/radarGrid with axes heightAboveEllipsoid x yCoordinates x xCoordinates;
they are interpolated at the terrain height of each pixel (Copernicus GLO-30 DEM, a local DEM, or a constant)."""
from __future__ import annotations

import math
import os
from functools import lru_cache
from pathlib import Path

import numpy as np

VALID = ("iono", "tropo", "tide")
DEFAULT_SETTING = "iono"                          # = the behaviour before the setting existed
LONG = "science__LSAR__GUNW__metadata__radarGrid__"
TROPO_KEYS = ("hydrostaticTroposphericPhaseScreen", "wetTroposphericPhaseScreen")
TIDE_KEY = "slantRangeSolidEarthTidesPhase"
AXES = ("heightAboveEllipsoid", "yCoordinates", "xCoordinates")
ATTR_DATASETS = ("unwrappedPhase", "ionospherePhaseScreen", *TROPO_KEYS, TIDE_KEY, "losUnitVectorX", "losUnitVectorY")
GLO30_URL = "https://copernicus-dem-30m.s3.amazonaws.com/{n}/{n}.tif"
MAX_EVAL = 400                                    # cube evaluated on at most ~400x400 points, then upsampled
# Ionosphere: pixels whose ionospherePhaseScreenUncertainty exceeds this (radians) are masked when the screen is
# subtracted. Real files: subtracting lowers the noise 2-40x on 10 of 12 Panama/Morocco pairs (Phase A report).
IONO_UNC_MAX_RAD = float(os.environ.get("NISAR_IONO_UNC_MAX_RAD", "1.0"))
SIGMA_SUBSAMPLE = 4                               # every 4th pixel for the frame-wide robust sigma


# ---------------------------------------------------------------------------------------------------------------------
# Setting
# ---------------------------------------------------------------------------------------------------------------------
def parse_setting(value: str | None) -> tuple[str, ...]:
    """'iono,tropo' -> ('iono', 'tropo'); 'none' or '' -> (); None -> the default. Unknown names fail fast."""
    if value is None:
        value = DEFAULT_SETTING
    names = [v.strip().lower() for v in value.split(",") if v.strip()]
    if names in ([], ["none"]):
        return ()
    bad = [n for n in names if n not in VALID]
    if bad:
        raise ValueError(f"NISAR_CORRECTIONS: unknown correction(s) {bad}; use a comma list of {', '.join(VALID)} or none")
    return tuple(n for n in VALID if n in names)          # canonical order, no duplicates


def active() -> tuple[str, ...]:
    return parse_setting(os.environ.get("NISAR_CORRECTIONS"))


# ---------------------------------------------------------------------------------------------------------------------
# Units and sign (pure functions)
# ---------------------------------------------------------------------------------------------------------------------
def to_radians(screen: np.ndarray, units: str | None, wavelength_m: float) -> tuple[np.ndarray, str]:
    """Screen in radians. 'rad...' kept; metres of line-of-sight delay converted with phase = -4*pi/lambda * d
    (the same convention as displacement = -lambda/(4*pi) * phase). Unknown units: radians assumed, and said."""
    u = (units or "").strip().lower()
    if u.startswith("rad"):
        return screen, "radians"
    if u in ("m", "meter", "meters", "metre", "metres"):
        return screen * (-4 * np.pi / wavelength_m), "metres converted to radians"
    return screen, "radians assumed (units attribute " + (f"'{units}'" if units else "not available") + ")"


def subtract_screen(phase: np.ndarray, screen: np.ndarray, sign: int = 1) -> np.ndarray:
    """phase - sign * screen; NaN in the screen leaves the phase unchanged (as the ionosphere code always did)."""
    return phase - sign * np.nan_to_num(screen)


def correct_iono(phase: np.ndarray, iono: np.ndarray, sign: int = 1) -> np.ndarray:
    return subtract_screen(phase, iono, sign)


def uncertainty_mask(unc: np.ndarray | None, max_rad: float = IONO_UNC_MAX_RAD) -> np.ndarray | None:
    """True where the ionosphere screen is too uncertain to be trusted (uncertainty > max_rad)."""
    if unc is None:
        return None
    with np.errstate(invalid="ignore"):
        return np.isfinite(unc) & (unc > max_rad)


def frame_sigma(phase: np.ndarray, exclude: np.ndarray | None = None) -> float:
    """Robust sigma (rad) of the phase over the whole frame (every 4th pixel), excluded pixels left out."""
    from uncertainty import robust_sigma
    sl = (slice(None, None, SIGMA_SUBSAMPLE), slice(None, None, SIGMA_SUBSAMPLE))
    v = phase[sl]
    if exclude is not None:
        v = v[~exclude[sl]]
    v = v[np.isfinite(v)]
    return robust_sigma(v - np.median(v)) if v.size else float("nan")


def keep_raw_phase(sigma_raw: float, sigma_subtracted: float) -> bool:
    """Per pair: keep the raw phase unless subtracting the screen lowers the frame-wide robust sigma."""
    return not (np.isfinite(sigma_subtracted) and np.isfinite(sigma_raw) and sigma_subtracted < sigma_raw)


def correct_tropo(phase: np.ndarray, hydrostatic: np.ndarray, wet: np.ndarray, sign: int = 1) -> np.ndarray:
    return subtract_screen(phase, np.nan_to_num(hydrostatic) + np.nan_to_num(wet), sign)


def correct_tide(phase: np.ndarray, tide: np.ndarray, sign: int = 1) -> np.ndarray:
    return subtract_screen(phase, tide, sign)


# ---------------------------------------------------------------------------------------------------------------------
# Cube interpolation
# ---------------------------------------------------------------------------------------------------------------------
def interp_cube(cube: np.ndarray, heights, ys, xs, h, y, x) -> np.ndarray:
    """Trilinear interpolation of cube[height, y, x] at points (h, y, x); points are clipped to the cube's extent
    (no extrapolation). Axes may be ascending or descending; a single-level axis is used as constant."""
    from scipy.interpolate import RegularGridInterpolator
    axes, data = [], np.asarray(cube, dtype="float64")
    for i, ax in enumerate((heights, ys, xs)):
        ax = np.asarray(ax, dtype="float64").ravel()
        if ax.size > 1 and ax[0] > ax[-1]:
            ax = ax[::-1]
            data = np.flip(data, axis=i)
        axes.append(ax)
    pts = [np.clip(np.asarray(v, dtype="float64"), a.min(), a.max()) for v, a in zip((h, y, x), axes)]
    keep = [i for i, a in enumerate(axes) if a.size > 1]
    if len(keep) < 3:
        data = data.reshape([axes[i].size for i in keep] or [1])
        if not keep:
            return np.full(np.shape(pts[0]), float(data.ravel()[0]))
        axes, pts = [axes[i] for i in keep], [pts[i] for i in keep]
    f = RegularGridInterpolator(axes, data, bounds_error=False, fill_value=None)
    return f(np.stack([p.ravel() for p in pts], axis=-1)).reshape(np.shape(pts[0]))


def eval_grid(prof: dict, max_eval: int = MAX_EVAL):
    """Pixel-centre coordinates (in the raster's CRS) of a decimated grid, and the decimation step."""
    step = max(1, int(math.ceil(max(prof["height"], prof["width"]) / max_eval)))
    rows = np.arange(0, prof["height"], step) + (step / 2)
    cols = np.arange(0, prof["width"], step) + (step / 2)
    cc, rr = np.meshgrid(cols, rows)
    t = prof["transform"]
    return t.c + cc * t.a + rr * t.b, t.f + cc * t.d + rr * t.e, step


def upsample(sub: np.ndarray, shape: tuple, step: int) -> np.ndarray:
    """Bilinear upsampling of a decimated grid back to the full raster shape."""
    if step == 1 and sub.shape == tuple(shape):
        return sub
    from scipy import ndimage
    out = ndimage.zoom(sub, (shape[0] / sub.shape[0], shape[1] / sub.shape[1]), order=1, mode="nearest")
    full = np.empty(shape, dtype=out.dtype)
    h, w = min(shape[0], out.shape[0]), min(shape[1], out.shape[1])
    full[:h, :w] = out[:h, :w]
    full[h:, :w] = out[h - 1:h, :w]
    full[:, w:] = full[:, w - 1:w]
    return full


def _epsg(crs) -> int | None:
    if crs is None:
        return None
    if hasattr(crs, "to_epsg"):
        return crs.to_epsg()
    s = str(crs)
    return int(s.split(":")[-1]) if s.upper().startswith("EPSG:") else None


def cube_on_grid(cube, heights, ys, xs, cube_epsg, prof: dict, terrain_h) -> np.ndarray:
    """Cube interpolated onto the GUNW raster grid at the terrain height. terrain_h: a constant (metres) or an array on
    the decimated grid of eval_grid()."""
    X, Y, step = eval_grid(prof)
    epsg = _epsg(prof.get("crs"))
    if cube_epsg and epsg and int(cube_epsg) != int(epsg):
        from pyproj import Transformer
        X, Y = Transformer.from_crs(epsg, int(cube_epsg), always_xy=True).transform(X, Y)
    H = np.broadcast_to(np.asarray(terrain_h, dtype="float64"), X.shape)
    sub = interp_cube(cube, heights, ys, xs, H, Y, X)
    return upsample(sub, (prof["height"], prof["width"]), step).astype("float32")


# ---------------------------------------------------------------------------------------------------------------------
# Terrain height
# ---------------------------------------------------------------------------------------------------------------------
def glo30_tiles(west: float, south: float, east: float, north: float) -> list[str]:
    """Public Copernicus GLO-30 tile URLs (AWS open data, no credentials) covering a lon/lat box."""
    out = []
    for lat in range(math.floor(south), math.floor(north) + 1):
        for lon in range(math.floor(west), math.floor(east) + 1):
            n = (f"Copernicus_DSM_COG_10_{'N' if lat >= 0 else 'S'}{abs(lat):02d}_00_"
                 f"{'E' if lon >= 0 else 'W'}{abs(lon):03d}_00_DEM")
            out.append(GLO30_URL.format(n=n))
    return out


def _dem_on_grid(sources: list[str], prof: dict) -> np.ndarray:
    """DEM resampled onto the decimated grid of eval_grid()."""
    import rasterio
    from rasterio.merge import merge
    from rasterio.transform import Affine
    from rasterio.warp import Resampling, reproject
    X, _, step = eval_grid(prof)
    t = prof["transform"]
    dst_t = Affine(t.a * step, t.b, t.c, t.d, t.e * step, t.f)
    srcs = [rasterio.open(s) for s in sources]
    try:
        mosaic, mt = merge(srcs)
        crs = srcs[0].crs
    finally:
        for s in srcs:
            s.close()
    dst = np.full(X.shape, np.nan, dtype="float32")
    reproject(mosaic[0].astype("float32"), dst, src_transform=mt, src_crs=crs, dst_transform=dst_t,
              dst_crs=prof["crs"], resampling=Resampling.bilinear, dst_nodata=np.nan)
    return dst


def terrain_height(prof: dict) -> tuple[object, str]:
    """Cached per grid and per setting (the DEM is fetched once per frame). See _terrain_height."""
    key = (str(prof["crs"]), tuple(prof["transform"])[:6], prof["width"], prof["height"],
           os.environ.get("NISAR_DEM"), os.environ.get("NISAR_OFFLINE"), os.environ.get("NISAR_CORRECTION_HEIGHT_M"))
    return _terrain_cached(key, prof)


_TERRAIN: dict = {}


def _terrain_cached(key, prof):
    if key not in _TERRAIN:
        if len(_TERRAIN) >= 16:
            _TERRAIN.clear()
        _TERRAIN[key] = _terrain_height(prof)
    return _TERRAIN[key]


def _terrain_height(prof: dict) -> tuple[object, str]:
    """(height, source). NISAR_DEM: a local DEM file, 'glo30' (public Copernicus tiles, needs internet), or 'none'.
    Default: 'glo30' unless NISAR_OFFLINE=1. Any failure falls back to the constant NISAR_CORRECTION_HEIGHT_M
    (default 0 m above the ellipsoid) and the source says so."""
    const = float(os.environ.get("NISAR_CORRECTION_HEIGHT_M", "0"))
    fallback = f"constant {const:g} m above the ellipsoid (NISAR_CORRECTION_HEIGHT_M)"
    choice = os.environ.get("NISAR_DEM") or ("none" if os.environ.get("NISAR_OFFLINE", "0") == "1" else "glo30")
    if choice == "none":
        return const, fallback + "; no DEM used"
    try:
        if choice == "glo30":
            import rasterio.transform as rt
            from rasterio.warp import transform_bounds
            b = transform_bounds(prof["crs"], "EPSG:4326", *rt.array_bounds(prof["height"], prof["width"], prof["transform"]))
            urls = glo30_tiles(*b)
            h = _dem_on_grid(["/vsicurl/" + u for u in urls], prof)
            src = (f"Copernicus GLO-30 DEM ({len(urls)} tile(s); geoid heights used as ellipsoid heights, "
                   "a few tens of metres off: negligible for the cubes)")
        else:
            h = _dem_on_grid([choice], prof)
            src = f"local DEM {Path(choice).name}"
        if not np.isfinite(h).any():
            raise ValueError("DEM has no valid value over the frame")
        return np.where(np.isfinite(h), h, np.nanmedian(h)), src
    except Exception as e:                            # noqa: BLE001 - any DEM problem: documented constant
        return const, f"{fallback}; DEM unavailable ({type(e).__name__})"


# ---------------------------------------------------------------------------------------------------------------------
# Attributes and "already applied" flags (raw .h5 kept with --keep-raw)
# ---------------------------------------------------------------------------------------------------------------------
def _text(v) -> str:
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    if isinstance(v, np.ndarray) and v.size == 1:
        return _text(v.ravel()[0])
    return str(v)


def raw_h5(folder: Path) -> Path | None:
    hits = sorted(Path(folder).glob("*.h5"))
    return hits[0] if hits else None


@lru_cache(maxsize=64)
def product_attributes(folder: str) -> dict:
    """{"source": file name or None, "datasets": {name: {path, description, units}}, "flags": {path: value}}.
    Flags = scalar entries and attributes under processingInformation whose name mentions iono / tropo / tide."""
    h5p = raw_h5(Path(folder))
    out = {"source": None, "datasets": {}, "flags": {}}
    if h5p is None:
        return out
    import h5py
    try:
        with h5py.File(h5p, "r") as h5:
            def visit(name, obj):
                base = name.split("/")[-1]
                if isinstance(obj, h5py.Dataset) and base in ATTR_DATASETS and base not in out["datasets"]:
                    out["datasets"][base] = {"path": name, "description": _text(obj.attrs.get("description", "")),
                                             "units": _text(obj.attrs.get("units", "")) or None}
                if "processingInformation" in name and any(k in base.lower() for k in ("iono", "tropo", "tide")):
                    if isinstance(obj, h5py.Dataset) and obj.size == 1:
                        out["flags"][name] = _text(obj[()])
                    for k, v in obj.attrs.items():
                        out["flags"][f"{name}@{k}"] = _text(v)
            h5.visititems(visit)
        out["source"] = h5p.name
    except Exception as e:                           # noqa: BLE001 - unreadable raw file: attributes unknown, said
        out["error"] = f"{type(e).__name__}: {e}"
    return out


_TRUE = {"true", "1", "yes", "applied", "enabled", "on"}


def already_applied(name: str, attrs: dict) -> bool | None:
    """True if a processingInformation flag or the unwrappedPhase description says this correction was already
    applied to the unwrapped phase; False if the raw file was read and nothing says so; None when nothing was read."""
    desc = ((attrs.get("datasets") or {}).get("unwrappedPhase") or {}).get("description", "").lower()
    if name in desc and any(w in desc for w in ("corrected", "applied", "removed")):
        return True
    hits = [v for k, v in (attrs.get("flags") or {}).items()
            if name in k.lower() and any(w in k.lower() for w in ("applied", "apply", "enabled"))]
    if any(v.strip().lower() in _TRUE for v in hits):
        return True
    return None if attrs.get("source") is None else False


# ---------------------------------------------------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------------------------------------------------
def _npz(folder: Path) -> dict | None:
    f = Path(folder) / "radar_geometry.npz"
    if not f.exists():
        return None
    with np.load(f) as z:
        return {k: z[k] for k in z.files}


def _key(z: dict, name: str) -> str | None:
    if name in z:
        return name
    return next((k for k in z if k.endswith("__" + name)), None)


def _base(name: str, attrs: dict, dataset: str) -> dict:
    d = (attrs.get("datasets") or {}).get(dataset) or {}
    return {"applied": False, "dataset": dataset, "convention": "subtracted from unwrappedPhase",
            "description": d.get("description") or None, "units_attribute": d.get("units"),
            "attributes_from": attrs.get("source") or "not available (no raw .h5 kept: download with --keep-raw)",
            "already_applied_flag": already_applied(name, attrs)}


def _apply_iono(p, phase, attrs, wavelength_m, sign):
    """Subtracts the ionosphere screen, masks the pixels where its uncertainty is above IONO_UNC_MAX_RAD, and keeps
    the raw phase for a pair where subtracting does not lower the frame-wide robust sigma. sign -1 (the noise
    report's convention test) forces the subtraction."""
    r = _base("iono", attrs, "ionospherePhaseScreen")
    if r["already_applied_flag"]:
        return phase, {**r, "reason": "the product says the ionosphere is already corrected: not applied again"}
    if "iono" not in p.files:
        return phase, {**r, "reason": "no ionospherePhaseScreen layer in this product"}
    import raster
    iono, _ = raster.read(p.files["iono"])
    if iono.shape != phase.shape:
        return phase, {**r, "reason": f"ionospherePhaseScreen shape {iono.shape} differs from the phase {phase.shape}"}
    scr, units = to_radians(iono, r["units_attribute"], wavelength_m)
    unc = raster.read(p.files["iono_unc"])[0] if "iono_unc" in p.files else None
    mask = uncertainty_mask(unc if unc is not None and unc.shape == phase.shape else None)
    sub = correct_iono(phase, scr, sign)
    s_raw, s_sub = frame_sigma(phase, mask), frame_sigma(sub, mask)
    info = {"units": units, "sign": sign, "frame_sigma_raw_rad": None if not np.isfinite(s_raw) else round(s_raw, 4),
            "frame_sigma_subtracted_rad": None if not np.isfinite(s_sub) else round(s_sub, 4),
            "uncertainty_layer": "present" if mask is not None else "absent (not extracted for this product)",
            "uncertainty_max_rad": IONO_UNC_MAX_RAD,
            "uncertainty_masked_fraction": None if mask is None else round(float(mask.mean()), 4)}
    if sign == 1 and keep_raw_phase(s_raw, s_sub):
        return phase, {**r, **info, "kept_raw": True,
                       "reason": f"kept the raw phase: subtracting the screen did not lower the robust sigma "
                                 f"({info['frame_sigma_raw_rad']} -> {info['frame_sigma_subtracted_rad']} rad)"}
    if mask is not None:
        sub = np.where(mask, np.nan, sub)
    return sub, {**r, **info, "kept_raw": False, "applied": True, "reason": "applied"}


def _apply_cube(name, p, phase, prof, attrs, wavelength_m, sign, z, height):
    keys_wanted = TROPO_KEYS if name == "tropo" else (TIDE_KEY,)
    r = _base(name, attrs, keys_wanted[0])
    if r["already_applied_flag"]:
        return phase, {**r, "reason": f"the product says the {name} correction is already applied: not applied again"}
    keys = [_key(z, k) for k in keys_wanted] if z else [None]
    axes = [_key(z, k) for k in AXES] if z else [None]
    if None in keys or None in axes:
        return phase, {**r, "reason": "radar_geometry.npz lacks the cube or its axes (download with extra_layers, e.g. "
                                      "plan_validation.json or plan_morocco.json, or run download_all.py rebuild-npz)"}
    pk = _key(z, "projection")
    epsg = int(np.asarray(z[pk]).ravel()[0]) if pk else None
    hz, yz, xz = (z[k] for k in axes)
    screens = [to_radians(cube_on_grid(z[k], hz, yz, xz, epsg, prof, height[0]), r["units_attribute"], wavelength_m)
               for k in keys]
    out = (correct_tropo(phase, screens[0][0], screens[1][0], sign) if name == "tropo"
           else correct_tide(phase, screens[0][0], sign))
    return out, {**r, "applied": True, "reason": "applied", "sign": sign, "units": screens[0][1],
                 "height_source": height[1], "height_m_median": round(float(np.nanmedian(height[0])), 1),
                 "cube_epsg": epsg}


def apply(p, phase: np.ndarray, prof: dict, names: tuple, wavelength_m: float, signs: dict | None = None):
    """Returns (corrected phase, {name: report}). The input phase is never modified. signs: {name: -1} adds the
    screen instead of subtracting it (used by the noise report to test the convention)."""
    signs = signs or {}
    attrs = product_attributes(str(p.folder)) if names else {}
    report, z, height = {}, None, None
    for name in names:
        sign = int(signs.get(name, 1))
        if name == "iono":
            phase, report[name] = _apply_iono(p, phase, attrs, wavelength_m, sign)
            continue
        if z is None:
            z = _npz(p.folder) or {}
        if height is None and z:
            height = terrain_height(prof)
        phase, report[name] = _apply_cube(name, p, phase, prof, attrs, wavelength_m, sign, z, height)
    return phase, report
