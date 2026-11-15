# Exclusion criterion for degenerate pairs (written 2026-11-15 BEFORE looking at any VR with or without exclusions)

Reason: two pairs (T4 F005, T76 F005) have a robust frame sigma of exactly 0.0 rad (`IONO_BUG.md`), which means the unwrapped phase is dominated by one value.
The rule below uses only properties of the unwrapped phase raster, never the fit result, and is not tuned.

A pair is **excluded** from the "with exclusions" runs if either holds, computed on the raw `unwrappedPhase` grid of the product:
1. the **exact-zero fraction** of the finite pixels is at least **0.10**; or
2. the **finite fraction** of the pixels after the coherence >= 0.3 mask and connected component != 0 (the pixels the fit can use) is below **0.01**.

The thresholds (0.10 and 0.01) were fixed here before the diagnosis was run, as round numbers, and will not be changed afterwards.
Variants reported with and without the excluded pairs: A (old code, raw phase), B (fixed code with the per-pair rule), C (forced subtraction).
