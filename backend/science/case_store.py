"""Reads and validates the case studies in backend/cases/<id>.json (drafts now, finals from science/cases.py)."""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from pydantic import ValidationError

from science.case_models import CASE_KIND, CaseStudy, CaseSummary

log = logging.getLogger(__name__)
CASES_DIR = Path(os.environ.get("NISAR_CASES", Path(__file__).resolve().parents[1] / "cases"))
ORDER = tuple(CASE_KIND)  # panama, venezuela, haouz, ionosphere


class CaseFileError(RuntimeError):
    """A case file exists but does not satisfy the contract."""


def load(case_id: str, cases_dir: Path | None = None) -> CaseStudy | None:
    """The validated case, None if there is no file for this id. Raises CaseFileError if the file is invalid."""
    if case_id not in CASE_KIND:
        return None
    path = (cases_dir or CASES_DIR) / f"{case_id}.json"
    if not path.is_file():
        return None
    try:
        case = CaseStudy.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, ValidationError) as exc:   # JSONDecodeError is a ValueError
        raise CaseFileError(f"{path.name}: {exc}") from exc
    if case.id != case_id:
        raise CaseFileError(f"{path.name}: id is {case.id!r}, expected {case_id!r}")
    return case


def load_all(cases_dir: Path | None = None) -> tuple[list[CaseStudy], list[str]]:
    """(valid cases in the fixed order, error messages for the invalid files). Invalid files are logged."""
    cases, errors = [], []
    for cid in ORDER:
        try:
            case = load(cid, cases_dir)
        except CaseFileError as exc:
            log.error("invalid case file: %s", exc)
            errors.append(str(exc))
            continue
        if case is not None:
            cases.append(case)
    return cases, errors


def summaries(cases_dir: Path | None = None) -> list[dict]:
    cases, _ = load_all(cases_dir)
    return [CaseSummary.of(c).model_dump(mode="json") for c in cases]


def to_json(case: CaseStudy) -> dict:
    return case.model_dump(mode="json")


FIGURE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,120}\.(png|jpg|jpeg|webp)$")
MEDIA = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}


def figure_path(case_id: str, name: str, cases_dir: Path | None = None) -> Path | None:
    """The figure file of a case, or None (unknown case, unsafe name, missing file, or outside the folder)."""
    if case_id not in CASE_KIND or not FIGURE_NAME.match(name) or ".." in name:
        return None
    folder = ((cases_dir or CASES_DIR) / "figures" / case_id).resolve()
    path = (folder / name).resolve()
    return path if path.parent == folder and path.is_file() else None
