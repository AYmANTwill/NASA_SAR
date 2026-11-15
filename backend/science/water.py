"""Youkaoui's water outputs (backend/water/, branch youkaoui/water): the 5th case and the Haouz open-water part.

backend/water/outputs/
  reservoir_case.json     a full CaseStudy, id "bin-el-ouidane-2026", kind "method" (docs/CASE_CONTRACT.md)
  haouz_open_water.json   {"findings": [Finding], "figures": [Figure]} added to the Haouz case
  rasters/, figures/      images served at /api/water/rasters/<file> and /api/water/figures/<file>

Every input is optional: absent → the 5th case is not served and Haouz is unchanged, with no error. A file that
breaks the contract is never patched silently: in production (STRICT false) the 5th case, the Haouz water extras or
the raster index are skipped with a logged warning, so one bad file never stops the API or the other cases; the tests
set STRICT (or NISAR_WATER_STRICT=1) and such a file raises. The no-0.0 rule applies: a finding without its σ is
left out and said in the limits (science.cases.finalize / split_computed).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from pydantic import ValidationError

from science.case_models import CaseStudy, Figure, Finding
from science.case_store import FIGURE_NAME

WATER_DIR = Path(os.environ.get("NISAR_WATER", Path(__file__).resolve().parents[1] / "water" / "outputs"))
RESERVOIR_ID = "bin-el-ouidane-2026"
STRICT = os.environ.get("NISAR_WATER_STRICT", "") == "1"
BACKGROUND_LAYERS = ("optical_before", "optical_after")     # optical 2026 images drawn under the water layers
log = logging.getLogger(__name__)
SERVED = ("rasters", "figures")
URL_PREFIX = "/api/water/"
OPEN_WATER_LABEL = {"fr": "Eau libre permanente (U-Net)", "en": "Persistent open water (U-Net)",
                    "ar": "المياه المفتوحة الدائمة (U-Net)"}


class WaterInputError(RuntimeError):
    """A water output exists but does not have the documented format."""


def water_path(kind: str, name: str, water_dir: Path | None = None) -> Path | None:
    """The served file, or None (unknown folder, unsafe name, missing file, or outside the folder)."""
    if kind not in SERVED or not FIGURE_NAME.match(name) or ".." in name:
        return None
    folder = ((water_dir or WATER_DIR) / kind).resolve()
    path = (folder / name).resolve()
    return path if path.parent == folder and path.is_file() else None


def _read(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise WaterInputError(f"{path}: invalid JSON ({exc})") from exc


PACKAGE_PREFIX = "water/outputs/"          # the package writes urls relative to backend/


def served_url(url: str, where: str) -> str:
    """'water/outputs/figures/x.png' -> '/api/water/figures/x.png' (same for rasters/); served urls pass as they are.
    Anything else stops the build: the frontend could not load it."""
    if url.startswith(URL_PREFIX) or url.startswith("/api/cases/"):
        return url
    if url.startswith(PACKAGE_PREFIX):
        kind, _, name = url[len(PACKAGE_PREFIX):].partition("/")
        if kind in SERVED and FIGURE_NAME.match(name):
            return f"{URL_PREFIX}{kind}/{name}"
    raise WaterInputError(f"{where}: url {url!r} is not under {PACKAGE_PREFIX}{{figures,rasters}}/ nor {URL_PREFIX}")


def _param_lists(obj):
    """A copy where every TemplatedText param that is a list (the frontend's TemplateParam has no array) becomes
    scalars, values unchanged: strings joined ("P05023, P05036"), a [low, high] number pair -> <key>_low / <key>_high.
    Reported to Youkaoui in docs/claude/WATER_NOTES.md (backend/water/ is vendored, never edited here)."""
    if isinstance(obj, list):
        return [_param_lists(v) for v in obj]
    if not isinstance(obj, dict):
        return obj
    out = {k: _param_lists(v) for k, v in obj.items()}
    if "template" in out and isinstance(out.get("params"), dict):
        params = {}
        for k, v in out["params"].items():
            if isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
                params[f"{k}_low"], params[f"{k}_high"] = v
            elif isinstance(v, list):
                params[k] = ", ".join(str(x) for x in v)
            else:
                params[k] = v
        out["params"] = params
    return out


def _served(figures: list[dict], where: str) -> list[dict]:
    """The figures with served urls (new dicts, the input is not changed)."""
    out = []
    for f in figures:
        g = {**f, "url": served_url(f.get("url", ""), where)}
        if f.get("layer"):
            g["layer"] = {**f["layer"], "url": served_url(f["layer"].get("url", ""), where)}
        out.append(g)
    return out


def reservoir_case(water_dir: Path | None = None) -> dict | None:
    """The raw 5th case (a CaseStudy dict) or None when the file is absent."""
    path = (water_dir or WATER_DIR) / "reservoir_case.json"
    data = _read(path)
    if data is None:
        return None
    if data.get("id") != RESERVOIR_ID:
        raise WaterInputError(f"{path}: id must be {RESERVOIR_ID!r}, got {data.get('id')!r}")
    data = _param_lists({**data, "figures": _served(data.get("figures", []), path.name)})
    try:
        CaseStudy.model_validate(data)
    except ValidationError as exc:
        raise WaterInputError(f"{path}: {exc}") from exc
    return data


def raster_index(water_dir: Path | None = None) -> dict | None:
    """outputs/raster_index.json with served layer urls (/api/water/rasters/...), None when absent. The layers are
    RGBA PNG images in EPSG:4326 with [west, south, east, north] bounds, not RasterLayer (no water palette). Every
    layer has a role: "background" for the optical images (drawn under the water, never the default basemap),
    "overlay" for the water layers, unless the package gives one."""
    path = (water_dir or WATER_DIR) / "raster_index.json"
    data = _read(path)
    if data is None:
        return None
    try:
        layers = [{**lay, "url": served_url(lay["url"], path.name),
                   "role": lay.get("role") or ("background" if lay["id"] in BACKGROUND_LAYERS else "overlay")}
                  for lay in data.get("layers", [])]
    except (KeyError, TypeError) as exc:
        raise WaterInputError(f"{path}: {exc}") from exc
    return {**data, "layers": layers}


def haouz_open_water(water_dir: Path | None = None) -> tuple[list[dict], list[dict], list[dict]]:
    """(findings, figures, limits) for the Haouz case, ([], [], []) when the file is absent. The package's own label
    is kept ('persistent open water (U-Net)' when it has none); numbers are taken as they are and the agreement is
    checked by the Finding model. Limits are {fr, en, ar} texts, wrapped as TemplatedText."""
    path = (water_dir or WATER_DIR) / "haouz_open_water.json"
    data = _read(path)
    if data is None:
        return [], [], []
    data = _param_lists(data)
    try:
        findings = []
        for f in data.get("findings", []):
            fid = f["id"] if str(f["id"]).startswith("open_water") else f"open_water_{f['id']}"
            findings.append(Finding.model_validate({**f, "id": fid, "label": f.get("label") or OPEN_WATER_LABEL})
                            .model_dump(mode="json"))
        figures = [Figure.model_validate(f).model_dump(mode="json", exclude_none=True)
                   for f in _served(data.get("figures", []), path.name)]
        limits = [lim if "template" in lim else {"template": "backend.water_limit", "params": {}, "text": lim}
                  for lim in data.get("limits", [])]
    except (ValidationError, KeyError, TypeError) as exc:
        raise WaterInputError(f"{path}: {exc}") from exc
    return findings, figures, limits


def skip_or_raise(what: str, exc: Exception, raise_as: type[Exception] | None = None) -> None:
    """Production: log and skip `what`. STRICT (tests): raise (as `raise_as` when given)."""
    if STRICT:
        if raise_as is not None:
            raise raise_as(str(exc)) from exc
        raise exc
    log.warning("water: %s skipped: %s", what, exc)
