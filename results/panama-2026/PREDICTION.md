# Sign test: prediction written before any run

Rule (agreed with Ayman): accept LOS_SIGN = +1 only if
(a) ffm_sign gives k > 0 at more than 3 sigma on at least 3 of 4 tracks, and no track has a significant k < 0;
(b) the +1 inversion fits clearly better than -1: variance reduction(+1) - variance reduction(-1) >= 0.10 (VR_MARGIN, backend/science/sign_decision.py:23 and :62); (a) uses SIGNIFICANCE = 3.0 (backend/science/ffm_sign.py:25, :82) and MIN_TRACKS = 3 (sign_decision.py:22, :61); (c) uses strike and dip within 15 degrees and rake within 30 degrees of 288.32/66.22/-16.68 (sign_decision.py:24-26, :36-38);
(c) the kept plane is the left-lateral one (288/66/-17).
Mirror rule: accept -1 if k < 0 at more than 3 sigma on at least 3 tracks, -1 fits better on at least 3 tracks, and the plane is left-lateral.
Otherwise the result is "sign unverified" and we ship with that label.
As coded (differs from the text above): the mirror rule exists (sign_decision.py:64-66), but both (b) and its mirror use one variance reduction pooled over all tracks (the best-plane fit of the pooled tracks, sign_decision.py:59-62), not "track by track" or "on at least 3 tracks"; sigma(k) in (a) is the per-point least-squares error of k with spatial correlation ignored (ffm_sign.py:74-77), the block bootstrap is not used for it.

Prediction (USGS mechanism, left-lateral strike near 295 degrees, left-looking radar):
- T40 and T141 (descending): the NE block moves toward the satellite (positive in our convention), the SW block away.
- T4 and T76 (ascending): the pattern is reversed.
- If +1 is right: k > 0 on all four tracks, with the flip carried by each track's own look vector.

Plausibility check only, not part of the decision: fitted Mw within about 0.2 of the USGS Mw 7.7. No parameter is adjusted to reach it.

Known weak points: T141 was inconclusive earlier (20 and 2 percent valid pixels); only the largest connected component per track is kept; the ionosphere screen is subtracted (run with and without if the code allows).

## Addendum, before the final decision
- Thresholds as coded in science/sign_decision.py: at least 3 tracks with k > 0 at more than 3 sigma and none significantly < 0;
  pooled VR(+1) - VR(-1) >= 0.10 (pooled, not per track); best plane within 15 degrees (strike, dip) and 30 degrees (rake)
  of 288/66/-17; mirrored rule for -1. The code was merged before the Phase 3 runs (check the merge commit date).
- Rule (a) as coded counts pair-frames; tracks and geometries are reported too.
- The text above said (b) track by track; the code is pooled, and the code was applied.
- sigma(k) was a plain least-squares sigma until the block bootstrap lands: (a) is unreliable until then.
- Final verdict: sign unverified (REPORT section 5).
