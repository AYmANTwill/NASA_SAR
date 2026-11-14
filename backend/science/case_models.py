"""CaseStudy contract (docs/CASE_CONTRACT.md), field for field with tools/frontend_contract/case_contract.ts.

Rules enforced here, so a broken case can never be served:
- every Measurement carries an uncertainty (declared at `sigma` standard deviations);
- a finding's `agreement` is the one computed by `agreement()` from its two measurements, never typed by hand;
- a reference value always comes with its source, and the reverse;
- a case is `final` only when it lists no placeholder and every NISAR value has a non-zero uncertainty.
"""
from __future__ import annotations

import math
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer, model_validator

CASE_KIND = {"panama-2026": "earthquake", "venezuela-2026": "earthquake",
             "haouz-flood-2026": "flood", "ionosphere-gps": "method"}
CaseId = Literal["panama-2026", "venezuela-2026", "haouz-flood-2026", "ionosphere-gps"]
CaseKind = Literal["earthquake", "flood", "method"]
Status = Literal["draft", "final"]
AgreementLabel = Literal["agree", "partial", "disagree", "no_reference"]

# Units of the frontend contract (src/api/contract.ts) plus the ones the case studies need ("mm" already exists).
NEW_UNITS = ("Mw", "people", "count", "deg")
Unit = Literal["mm", "cm", "m", "mm/yr", "cm/yr", "mm/yr2", "m3/m3", "dB", "ha", "km2", "percent", "coherence", "km",
               "Mw", "people", "count", "deg"]

AGREE_FACTOR = 2.0       # |nisar - reference| <= 2 sigma  -> agree
PARTIAL_FACTOR = 4.0     # |nisar - reference| <= 4 sigma  -> partial, beyond -> disagree
ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|\+00:00)$")


def _utc(v: str) -> str:
    if not ISO_UTC.match(v):
        raise ValueError(f"expected an ISO 8601 UTC date-time (...Z or ...+00:00), got {v!r}")
    return v


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Lang3(_Strict):
    fr: str = Field(min_length=1)
    en: str = Field(min_length=1)
    ar: str = Field(min_length=1)


class Measurement(_Strict):
    value: float
    uncertainty: float = Field(ge=0)
    unit: Unit
    sigma: float = Field(default=1, gt=0)

    @field_validator("value", "uncertainty")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("must be finite")
        return v

    @property
    def one_sigma(self) -> float:
        return self.uncertainty / self.sigma


class TemplatedText(_Strict):
    template: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    text: dict[Literal["fr", "en", "ar"], str] | None = None

    @model_serializer(mode="wrap")
    def _omit_empty_text(self, handler):
        out = handler(self)
        if out.get("text") is None:
            out.pop("text", None)   # zod: optional, not nullable
        return out


class Source(_Strict):
    name: str = Field(min_length=1)
    url: str = Field(pattern=r"^https?://")


class RasterLayer(_Strict):
    id: str
    kind: Literal["displacement", "velocity", "coherence", "coherence_loss", "soil_moisture", "backscatter_change",
                  "offset"]
    url: str
    bounds: tuple[float, float, float, float]
    unit: Unit
    min: float
    max: float
    palette: Literal["diverging_displacement", "sequential_coherence", "sequential_coherence_loss",
                     "sequential_moisture"]
    sign_convention: Literal["positive_toward_satellite", "positive_away_from_satellite", "positive_up",
                             "positive_east"] | None
    period: dict[Literal["start", "end"], str] | None
    source: str


def agreement(nisar: Measurement, reference: Measurement | None) -> AgreementLabel:
    """agree if |n - r| <= 2·sqrt(σn² + σr²), partial if <= 4·sqrt(...), else disagree (σ = 1-sigma)."""
    if reference is None:
        return "no_reference"
    if nisar.unit != reference.unit:
        raise ValueError(f"cannot compare {nisar.unit} with {reference.unit}")
    diff = abs(nisar.value - reference.value)
    s = math.hypot(nisar.one_sigma, reference.one_sigma)
    if s == 0:
        return "agree" if diff == 0 else "disagree"
    if diff <= AGREE_FACTOR * s:
        return "agree"
    if diff <= PARTIAL_FACTOR * s:
        return "partial"
    return "disagree"


class Finding(_Strict):
    id: str = Field(min_length=1)
    label: Lang3
    nisar: Measurement
    reference: Measurement | None
    reference_source: Source | None
    agreement: AgreementLabel

    @model_validator(mode="after")
    def _consistent(self):
        if (self.reference is None) != (self.reference_source is None):
            raise ValueError(f"finding {self.id}: a reference value needs its reference_source, and the reverse")
        expected = agreement(self.nisar, self.reference)
        if self.agreement != expected:
            raise ValueError(f"finding {self.id}: agreement is {self.agreement!r} but the rule gives {expected!r}")
        return self


class Figure(_Strict):
    id: str = Field(min_length=1)
    kind: Literal["map", "chart", "image"]
    title: Lang3
    url: str = Field(min_length=1)
    caption: TemplatedText
    layer: RasterLayer | None = None

    @model_serializer(mode="wrap")
    def _omit_empty_layer(self, handler):
        out = handler(self)
        if out.get("layer") is None:
            out.pop("layer", None)  # zod: optional, not nullable
        return out


class Exposure(_Strict):
    people: Measurement
    buildings: Measurement
    area_km2: Measurement
    source: Source

    @model_validator(mode="after")
    def _units(self):
        for name, unit in (("people", "people"), ("buildings", "count"), ("area_km2", "km2")):
            if getattr(self, name).unit != unit:
                raise ValueError(f"exposure.{name} must be in {unit}")
        return self


class Location(_Strict):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    bbox: tuple[float, float, float, float]
    place: Lang3

    @model_validator(mode="after")
    def _inside(self):
        w, s, e, n = self.bbox
        if not (w < e and s < n and w <= self.lon <= e and s <= self.lat <= n):
            raise ValueError("bbox must be [west, south, east, north] and contain lat/lon")
        return self


class TimelineItem(_Strict):
    label: Lang3
    at: str

    @field_validator("at")
    @classmethod
    def _at_utc(cls, v: str) -> str:
        return _utc(v)


class CaseStudy(_Strict):
    id: CaseId
    kind: CaseKind
    status: Status
    title: Lang3
    date: str
    location: Location
    headline: TemplatedText
    findings: list[Finding]
    figures: list[Figure]
    exposure: Exposure | None
    timeline: list[TimelineItem]
    answer_ids: list[str]
    limits: list[TemplatedText] = Field(min_length=1)
    # Backend-only (the frontend ignores it): JSON paths of values that are placeholders, not computations.
    placeholders: list[str] = Field(default_factory=list)

    @field_validator("date")
    @classmethod
    def _date_utc(cls, v: str) -> str:
        return _utc(v)

    @model_validator(mode="after")
    def _rules(self):
        if CASE_KIND[self.id] != self.kind:
            raise ValueError(f"case {self.id} must have kind {CASE_KIND[self.id]!r}")
        ids = [f.id for f in self.findings]
        if len(ids) != len(set(ids)):
            raise ValueError("finding ids must be unique")
        if self.status == "final":
            if self.placeholders:
                raise ValueError(f"a final case cannot contain placeholders: {self.placeholders}")
            if not self.findings:
                raise ValueError("a final case needs at least one finding")
            for f in self.findings:
                if f.nisar.uncertainty <= 0:
                    raise ValueError(f"final case: finding {f.id} has no uncertainty")
        return self


class CaseSummary(_Strict):
    id: CaseId
    kind: CaseKind
    title: Lang3
    date: str
    status: Status
    thumbnail_url: str | None

    @classmethod
    def of(cls, case: CaseStudy) -> "CaseSummary":
        thumb = next((f.url for f in case.figures if f.kind in ("map", "image")), None)
        return cls(id=case.id, kind=case.kind, title=case.title, date=case.date, status=case.status,
                   thumbnail_url=thumb)
