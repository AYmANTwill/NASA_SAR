---
name: science-check
description: SAR/InSAR correctness checklist for NISAR Pulse. Use before writing or reviewing any change to backend/recipes/*, uncertainty.py, config.py constants, agent.py (run_sudden, run_slow, assess, templates), discoveries.py or evidence.py, and whenever a change affects a number, unit, sign, threshold, confidence level, alert colour or verdict sentence.
allowed-tools: Read, Grep, Glob
---

# Science check

Go through the items that apply. For each, answer **OK / RISK / N/A** with file:line.
A RISK on items 1–4 blocks the demo.

1. **Units**: phase rad → LOS cm (`LOS_SIGN · (−λ/4π) · φ · 100`, λ = 0.2384 m, 1 rad ≈ 1.90 cm);
   series in mm; velocity in mm/yr (days / 365.25); backscatter dB = 10·log10(power); areas from
   projected pixel size in metres, not degrees.
2. **Sign**: any change to `LOS_SIGN` or the conversion needs real-data evidence and a decision
   record. Check STATUS.md for whether the sign was verified on Panama.
3. **Event timing**: pairs must satisfy `ref ≤ event ≤ sec` with the exact UTC time, not midnight.
   No fallback to non-straddling pairs; return a no-data answer instead.
4. **Numbers in text**: every number in a verdict comes from recipe facts; LLM output passes the
   number guard; a renamed fact key is updated in every template.
5. **Masks**: coherence ≥ `COHERENCE_MIN`, connected component ≠ 0, NaN never treated as zero.
   Point and reference should share a connected component (known gap: a 2π jump ≈ 11.9 cm).
6. **Reference and noise**: the reference area must plausibly be stable (not inside a large
   earthquake field). Per-pixel MAD understates the error of a 2 km window average; do not raise
   confidence because of it.
7. **LOS vs components**: never call LOS "vertical". Decomposition ignores north–south motion and
   needs both geometries over the same period; say "approximate" when nominal vectors are used.
8. **Time series**: the pair network must be connected; flag short records before reporting mm/yr or
   acceleration; mixing beta/provisional/validated products can create a fake trend.
9. **Evidence**: corroboration must test the measurement, not co-occurrence (a nearby quake or
   50 mm of rain does not confirm a displacement value). Exposure is context, not confidence.
10. **Labels**: provenance (real / cached-real / synthetic / mock) and maturity (SME2 provisional)
    stay visible in the response.
11. **Tests**: synthetic data reuse the same formulas, so tests cannot catch sign or geometry errors.
    Name what would actually validate the change (published map, GNSS, independent product).

End with **OK** or **RISKS FOUND**, and the smallest fix for each RISK.
