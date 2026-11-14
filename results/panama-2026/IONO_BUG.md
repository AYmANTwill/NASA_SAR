# The ionosphere "already applied" bug (found 2026-11-14, fixed in `corrections.already_applied`)

## The bug
`backend/recipes/corrections.py` `already_applied(name, attrs)` decides whether a correction was already applied to the unwrapped
phase. Besides the `unwrappedPhase` description it looked at the processing flags: any flag whose name contains the correction
name (`"iono"`) and `"applied"` and whose value is true. The four geocoding flags match:
`parameters/geocoding/azimuthIonosphericCorrectionApplied` and `rangeIonosphericCorrectionApplied` (and the two tropospheric ones for `"tropo"`),
all `'True'`, described in the file as "applied to improve geolocation" (`results/h5_attributes.txt:76-81`; the spec says they concern the
geocoding of the pixel offsets, REPORT section 3, line 129). `"iono"` is a substring of `"ionospheric"`.
Result: for every product with a kept raw `.h5` (all 8 Panama co-seismic pairs, and the Morocco products kept with `--keep-raw`) the code
returned "the product says the ionosphere is already corrected: not applied again" and used the **raw phase**. Products without a raw
`.h5` (no flags read) were corrected. The treatment depended on whether the `.h5` was kept, not on the product.
NASA's spec (REPORT line 130) says the screen is "not applied by default": the products are **not** corrected.

## The fix
`corrections.py:323-326`: flags whose path contains `/geocoding/` are ignored. Test: `backend/tests/test_iono_flags.py`
(`test_geocoding_flags_do_not_count`, 6/6). All test files after the fix: `test_all` 196/196, `test_science` 101/101,
`test_wavelength` 6/6, `test_decompose` 5/5, `test_iono_flags` 6/6 (synthetic checks).
On the real product T40 F084 the screen is now applied: frame sigma 40.9 → 6.2 rad.

## Before / after on the Panama sign test (`sensitivity_iono.py`, `sensitivity_iono.md`, `sensitivity_iono_{A,B,C}.json`)
Variants: **A** = the old code (raw phase, reproduced: it equals `per_track_sign.md`); **B** = the fixed code with its per-pair `keep_raw_phase` rule;
**C** = forced subtraction. No bootstrap, no noise model; the pooled VR here (0.93 to 0.96) is higher than the 0.82 of Phase 3, which used noise models.
- **B keeps the raw phase in 5 of the 7 distinct pair ids** (the two T141 F085 variants share one id; subtracting did not lower the frame-wide robust sigma) and applies the screen in only 2 (T40 F084: 40.9 → 6.2 rad; T141 F084: 21.0 → 4.4 rad). In all five kept-raw pairs the subtraction makes the sigma *larger*: T141 F085 10.7 → 27.6, T40 F085 14.1 → 22.8, T76 F006 2.2 → 2.7, T4 F005 0.0 → 8.9, T76 F005 0.0 → 12.7 rad (T4 F005 and T76 F005 have a raw sigma of 0.0, which I did not explain; the pair has almost no coherent pixels).
- The uncertainty layer is absent in all eight products (not extracted), so the uncertainty mask is not applied; the valid fraction is the same in the three variants (2.0 % to 18.3 % of the pixels).
- **Decision inputs, pooled (A / B / C):** decision undecided / undecided / undecided; ffm k > 0 at 3σ on 6 / 6 / 6 pair-frames, none negative in any;
  VR(+1) − VR(−1) = 0.0066 / 0.0049 / 0.0232 (rule needs 0.10); best plane left-lateral in all three. **No decision input changes the verdict.**
  The ffm k/σ moves for T40 F084 (14.1 / 15.5 / 15.5) and T40 F085 (9.9 / 9.9 / 51.8), and T141 F084 (59.2 / 61.8 / 61.8).
- **Per track (best plane, VR(+1) − VR(−1)):** T141 +0.013 / +0.012 / +0.013; T4 −0.038 / −0.038 / −0.037; T76 −0.131 / −0.131 / −0.140; T40 +0.015 / +0.034 / **+0.189** (C: forced subtraction on F085, where it raises the sigma). Ramp-only VR (offsets and ramp, no fault) per track A / B / C: T141 0.963 / 0.963 / 0.953; T4 0.597 / 0.597 / 0.574; T40 0.813 / 0.626 / 0.284; T76 0.624 / 0.624 / 0.365.
- Reading: the earlier result (INCONCLUSIVE sign) does not depend on the bug. Only T40 changes visibly; the descending-lean-+1 / ascending-lean-−1 pattern of `per_track_sign.md` is the same in all three variants.

## Statements that must change (not edited yet)
`results/REPORT.md`
- line 8: "Sections 2, 4, 6 and 8 were not re-run": keep, and add that section 4 (precompute) and section 6 were produced before this fix.
- line 153 ("Precompute was run on the earlier tree"): the cached answers (`results/events/*.json`, `backend/cache/`) predate `corrections.py`'s flag logic. They subtracted the screen everywhere (older tree). With the current fixed code a re-run gives, per pair, raw or subtracted (`keep_raw_phase`); the answers can change. Re-run `precompute.py` (needs your OK) before quoting them.
- line 151 (al-wahda row): "ionosphere screen subtracted (not validated)" was true of the old tree only; re-check after a re-run.
- lines 165-166 (Phase 3 sign check on two frames: "ionosphere screen subtracted"): that earlier check used `los_cm`; for these products the screen was in fact **not** subtracted (the bug). Reword: "raw phase".
- line 179 (Phase 3): "these products say the ionosphere is already corrected": **wrong**. Replace with: the code misread the geocoding flags; the products are not corrected; see this file.
- line 177-178 (ffm_sign "with ionosphere"): the "iono" run was in fact the raw phase. Say so.
- line 202 ("the code subtracts the ionosphere screen"): true of the old tree and, after the fix, only where `keep_raw_phase` allows (2 of 7 Panama pair ids).
- line 208 (section 6 table header "minus iono (what the code does)"): the CSV was computed by forcing the subtraction, independent of the bug; but the header should read "minus iono (forced subtraction)".
- line 241 (section 8, item 3, `displacement.py:24-29`): that code no longer exists there; the logic is in `corrections.py` (`_apply_iono`, `already_applied`). Reword to the per-pair rule and the fixed flag logic.
- line 253 (section 9): "whole-frame sigma up to 96 cm … 2–6 cm after" came from the forced subtraction; state it.

`docs/claude/DECISIONS.md`
- lines 120-125 (D-009 context and option A "subtract everywhere (today)"): the current behaviour is "subtract unless the sigma does not drop" (`keep_raw_phase`), which keeps the raw phase in 5 of 7 Panama pair ids; the criterion D-009 leaves open is partly implemented.
- lines 128-129 (consequences, Al Wahda +43.4/−20.0 mm with the screen, +29.6/+71.4 mm without): re-check after a `precompute.py` re-run.

`docs/claude/STATUS.md`
- line 41 (I1) and line 21 (Next 4): "screen subtracted everywhere" / `displacement.py:24-29` are out of date. Replace by the `corrections.py` rule and this bug.

`docs/claude/QUESTIONS.md`
- Q8 (cause of "no with/without test") and Q17: close with this file.

## Not done
No `precompute.py`, no re-run of the Phase 4 case files, no edit of the statements above.
