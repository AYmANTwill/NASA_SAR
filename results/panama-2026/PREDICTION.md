# Sign test: prediction written before any run

Rule (agreed with Ayman): accept LOS_SIGN = +1 only if
(a) ffm_sign gives k > 0 at more than 3 sigma on at least 3 of 4 tracks, and no track has a significant k < 0;
(b) the +1 inversion fits clearly better than -1, track by track (threshold as coded in science/sign_decision.py: FILL IN after reading it);
(c) the kept plane is the left-lateral one (288/66/-17).
Mirror rule: accept -1 if k < 0 at more than 3 sigma on at least 3 tracks, -1 fits better on at least 3 tracks, and the plane is left-lateral.
Otherwise the result is "sign unverified" and we ship with that label.

Prediction (USGS mechanism, left-lateral strike near 295 degrees, left-looking radar):
- T40 and T141 (descending): the NE block moves toward the satellite (positive in our convention), the SW block away.
- T4 and T76 (ascending): the pattern is reversed.
- If +1 is right: k > 0 on all four tracks, with the flip carried by each track's own look vector.

Plausibility check only, not part of the decision: fitted Mw within about 0.2 of the USGS Mw 7.7. No parameter is adjusted to reach it.

Known weak points: T141 was inconclusive earlier (20 and 2 percent valid pixels); only the largest connected component per track is kept; the ionosphere screen is subtracted (run with and without if the code allows).
