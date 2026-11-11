"""Noise floor and confidence rules. Fixed rules, never decided by the language model."""
from __future__ import annotations

import numpy as np


def robust_sigma(values: np.ndarray) -> float:
    v = values[np.isfinite(values)]
    if v.size < 50:
        return float("nan")
    return float(1.4826 * np.median(np.abs(v - np.median(v))))


def confidence(signal: float, sigma: float, coherence_at_point: float, masked_fraction: float,
               evidence_agrees: bool | None) -> tuple[str, list[str]]:
    """Returns ('high' | 'medium' | 'low', reasons)."""
    reasons = []
    if not np.isfinite(signal) or not np.isfinite(sigma) or sigma == 0:
        return "low", ["not enough valid pixels at this point (low coherence)"]
    snr = abs(signal) / sigma
    reasons.append(f"signal = {snr:.1f}× the noise floor")
    if coherence_at_point < 0.3:
        reasons.append(f"low coherence at the point ({coherence_at_point:.2f})")
    if masked_fraction > 0.5:
        reasons.append(f"{masked_fraction:.0%} of the area is masked")
    if evidence_agrees:
        reasons.append("an independent source agrees")
    if snr >= 3 and coherence_at_point >= 0.3 and evidence_agrees:
        return "high", reasons
    if snr >= 3 or (snr >= 2 and coherence_at_point >= 0.3):
        return "medium", reasons
    return "low", reasons
