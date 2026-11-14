"""Ionosphere case: noise of each NISAR pair before / after the ionospheric correction, as a chart.

Input: results/noise_with_without_iono_*.csv (Anass, real GUNW pairs), one row per pair:
    track,frame,direction,ref,sec,sigma_raw_cm,sigma_minus_iono_cm,sigma_plus_iono_cm,iono_median_rad,
    iono_p5_p95_rad,valid_px
sigma_* is the robust spread (cm) of the unwrapped phase over the whole frame; "minus" is the correction as the code
applies it, "plus" the opposite sign (a check of the sign of the correction).

A row with sigma_raw_cm <= 0 cannot be a measured spread (a constant raw field): it is left out and counted.
No error bar is drawn: the pixels are spatially correlated, so sigma/sqrt(2n) over pixels would be far too small;
the spread between pairs is what the chart shows.
"""
from __future__ import annotations

import csv
import math
import statistics
from dataclasses import dataclass
from pathlib import Path

COLUMNS = ("track", "frame", "direction", "ref", "sec", "sigma_raw_cm", "sigma_minus_iono_cm",
           "sigma_plus_iono_cm", "valid_px")
RAW_COLOR, CORRECTED_COLOR = "#eb6834", "#2a78d6"          # dataviz reference palette, slots 2 and 1 (validated)
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class NoiseCsvError(ValueError):
    """The CSV does not have the documented columns or values."""


@dataclass(frozen=True)
class PairNoise:
    track: int
    frame: int
    direction: str          # "A" | "D"
    ref: str                # YYYYMMDD
    sec: str
    raw: float              # cm
    minus: float            # cm, correction applied as in the code
    plus: float             # cm, correction with the opposite sign
    valid_px: int

    @property
    def label(self) -> str:
        d = lambda s: f"{int(s[6:8])} {MONTHS[int(s[4:6]) - 1]}"
        return f"T{self.track} F{self.frame} {self.direction} · {d(self.ref)} → {d(self.sec)}"


def _row(r: dict, line: int) -> PairNoise:
    try:
        p = PairNoise(int(r["track"]), int(r["frame"]), r["direction"].strip(), r["ref"].strip(), r["sec"].strip(),
                      float(r["sigma_raw_cm"]), float(r["sigma_minus_iono_cm"]), float(r["sigma_plus_iono_cm"]),
                      int(r["valid_px"]))
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise NoiseCsvError(f"line {line}: {exc}") from exc
    if p.direction not in ("A", "D") or not (len(p.ref) == len(p.sec) == 8 and (p.ref + p.sec).isdigit()):
        raise NoiseCsvError(f"line {line}: direction must be A/D and dates YYYYMMDD")
    if not all(math.isfinite(v) and v >= 0 for v in (p.raw, p.minus, p.plus)):
        raise NoiseCsvError(f"line {line}: sigma values must be finite and >= 0")
    return p


def read(path: Path) -> list[PairNoise]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise NoiseCsvError(f"{path.name}: missing columns {missing}")
        rows = [_row(r, i) for i, r in enumerate(reader, start=2)]
    if not rows:
        raise NoiseCsvError(f"{path.name}: no pair")
    return rows


def split_valid(rows: list[PairNoise]) -> tuple[list[PairNoise], list[PairNoise]]:
    """(rows with a measured raw spread, rows left out because sigma_raw_cm <= 0)."""
    return [r for r in rows if r.raw > 0], [r for r in rows if r.raw <= 0]


def summary(rows: list[PairNoise]) -> dict:
    """Numbers quoted in the caption, all computed from the valid rows."""
    ok, bad = split_valid(rows)
    if not ok:
        raise NoiseCsvError("no pair with a measured raw spread")
    return {"n_pairs": len(ok), "n_left_out": len(bad),
            "n_lower_after": sum(r.minus < r.raw for r in ok),
            "n_plus_higher": sum(r.plus > r.raw for r in ok),
            "median_raw_cm": round(statistics.median(r.raw for r in ok), 2),
            "median_after_cm": round(statistics.median(r.minus for r in ok), 2)}


def render(rows: list[PairNoise], path: Path) -> Path:
    """Dumbbell chart, one row per pair: raw spread -> spread after the correction (log scale, cm)."""
    import matplotlib
    import matplotlib.ticker
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ok = sorted(split_valid(rows)[0], key=lambda r: r.raw)
    fig, ax = plt.subplots(figsize=(8.0, 0.42 * len(ok) + 1.6), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    y = list(range(len(ok)))
    ax.hlines(y, [min(r.raw, r.minus) for r in ok], [max(r.raw, r.minus) for r in ok], color=GRID, lw=2, zorder=1)
    ax.scatter([r.raw for r in ok], y, s=90, color=RAW_COLOR, edgecolor=SURFACE, linewidth=1.2, zorder=3,
               label="Raw phase")
    ax.scatter([r.minus for r in ok], y, s=26, color=CORRECTED_COLOR, edgecolor=SURFACE, linewidth=0.8, zorder=3,
               label="After ionospheric correction")
    ax.set_xscale("log")
    lo = min(min(r.raw, r.minus) for r in ok)
    hi = max(max(r.raw, r.minus) for r in ok)
    ticks = [t for t in (0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500) if lo / 1.5 <= t <= hi * 1.5]
    ax.set_xticks(ticks, [f"{t:g}" for t in ticks])
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_yticks(y, [r.label for r in ok], fontsize=8, color=INK_2)
    ax.set_xlabel("Spread of the unwrapped phase over the frame (cm, log scale)", fontsize=8.5, color=INK_2)
    ax.tick_params(axis="x", labelsize=8, colors=INK_2)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.set_title("NISAR pairs: noise before and after the ionospheric correction", loc="left", fontsize=10,
                 color=INK, pad=22)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, fontsize=8, labelcolor=INK_2,
              handletextpad=0.3, borderaxespad=0.2)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path
