"""Youkaoui's water outputs (backend/water/, branch youkaoui/water): the 5th case and the Haouz open-water part.

backend/water/outputs/
  reservoir_case.json     a full CaseStudy, id "bin-el-ouidane-2026", kind "method" (docs/CASE_CONTRACT.md)
  haouz_open_water.json   {"findings": [Finding], "figures": [Figure]} added to the Haouz case
  rasters/, figures/      images served at /api/water/rasters/<file> and /api/water/figures/<file>

Every input is optional: absent → the 5th case is not served and Haouz is unchanged, with no error. A file that
breaks the contract stops the build (never patched silently). The no-0.0 rule applies: a finding without its σ is
left out and said in the limits (science.cases.finalize / split_computed).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import ValidationError

from science.case_models import CaseStudy, Figure, Finding
from science.case_store import FIGURE_NAME

WATER_DIR = Path(os.environ.get("NISAR_WATER", Path(__file__).resolve().parents[1] / "water" / "outputs"))
RESERVOIR_ID = "bin-el-ouidane-2026"
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


def _check_urls(figures: list[dict], where: str) -> None:
    for f in figures:
        urls = [f.get("url", "")] + ([f["layer"]["url"]] if f.get("layer") else [])
        for u in urls:
            if not u.startswith(URL_PREFIX) and not u.startswith("/api/cases/"):
                raise WaterInputError(f"{where}: figure {f.get('id')} url {u!r} is not served ({URL_PREFIX}...)")


def reservoir_case(water_dir: Path | None = None) -> dict | None:
    """The raw 5th case (a CaseStudy dict) or None when the file is absent."""
    path = (water_dir or WATER_DIR) / "reservoir_case.json"
    data = _read(path)
    if data is None:
        return None
    if data.get("id") != RESERVOIR_ID:
        raise WaterInputError(f"{path}: id must be {RESERVOIR_ID!r}, got {data.get('id')!r}")
    try:
        CaseStudy.model_validate({**data, "status": "draft"})
    except ValidationError as exc:
        raise WaterInputError(f"{path}: {exc}") from exc
    _check_urls(data.get("figures", []), path.name)
    return data


def haouz_open_water(water_dir: Path | None = None) -> tuple[list[dict], list[dict]]:
    """(findings, figures) for the Haouz case, ([], []) when the file is absent. Findings get the
    'persistent open water (U-Net)' label; their agreement is checked by the Finding model."""
    path = (water_dir or WATER_DIR) / "haouz_open_water.json"
    data = _read(path)
    if data is None:
        return [], []
    try:
        findings = []
        for f in data.get("findings", []):
            fid = f["id"] if str(f["id"]).startswith("open_water") else f"open_water_{f['id']}"
            findings.append(Finding.model_validate({**f, "id": fid, "label": OPEN_WATER_LABEL}).model_dump(mode="json"))
        figures = [Figure.model_validate(f).model_dump(mode="json", exclude_none=True) for f in data.get("figures", [])]
    except (ValidationError, KeyError, TypeError) as exc:
        raise WaterInputError(f"{path}: {exc}") from exc
    _check_urls(figures, path.name)
    return findings, figures
