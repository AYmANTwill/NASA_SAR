# NISAR Pulse — Status

> Rewritten by `/end-session`. Read by `/start-session`. Keep under ~80 lines.
> Issue IDs H/M/L come from `PROJECT_DEEP_DIVE.md` §13; S = science review of 2026-11-12; new IDs below were found on 2026-11-14.

## Snapshot
- Updated: 2026-11-14
- HEAD: `cbf5346` on `results/real-data-checks` (on top of `a231e36`, `e598020` "claude setup" and `fa3e0a6` = pushed `feat/surface-change-baseline-discoveries-off`). Uncommitted: D-008…D-010 and this file.
- Tests: 151/151 (`python tests/test_all.py`, re-run 2026-11-14 during `/demo-check`; no `.py` changed since). Synthetic data: logic only, not physics.
- Real data (checked 2026-11-14): 78 products on disk = 53 GUNW + 25 SME2, all Morocco, CRID P05023; raw `.h5` kept (125 GB). **No Panama pair on disk.** Tier 1+2 of `plan_morocco.json` done, tier 3 (432 SME2) not started.
- `precompute.py` was run on the real data: 5 events, no failed step; cached answers are newer than the last code change. `LOS_SIGN` is unverified. Nothing is validated against an independent source.
- `/demo-check` 2026-11-14: **NO-GO** (token not revoked: H1; sign unverified: H4). No UI in the repository to check labels or the offline rehearsal.

## Goal until the hackathon (14–15 Nov 2026)
One real, verified NISAR result shown end to end in a simple UI, with honest provenance and limits.

## Next (ordered)
1. Revoke the Earthdata token and remove it from `download_all.py` (H1). It is in the history of a branch that is now on GitHub.
2. Decide how to publish `results/real-data-checks` (it contains the "claude setup" commit) and merge `feat/surface-change-baseline-discoveries-off` after review.
3. Download the 8 Panama co-seismic pairs (13.3 GB, tracks 4, 40, 76, 141) and run the sign check (H4). Phase B: merge Ayman's `feat/validation-corrections` (noise report, GPS, sign check) when it exists.
4. Implement D-009: define "well determined" from the noise report, then mask elsewhere in `displacement.los_cm` (I1). Measure the D-008 null on more geometries.
5. Fix `evidence.py:112` (no User-Agent → OpenStreetMap 406) and mark unavailable sources as failed steps (E1, E2).
6. Re-run `precompute.py` after every merge; build the minimal map UI.
7. Decide D-005, D-006, D-007 (D-008…D-010 are recorded).

## In progress
- Phase B of the real-data checks (waits for Ayman's branch).

## Done recently
- 2026-11-14: D-008 (surface-change reference), D-009 (ionosphere screen policy, criteria open), D-010 (discoveries off) recorded; `/demo-check` run: NO-GO.
- 2026-11-14: real-data checks, phase A (`results/REPORT.md`): inventory, spec flags, precompute, ionosphere noise.
- 2026-11-14: signed LOS answers say "sign unverified" (low, no alert); discoveries off by default; soil-moisture uncertainty rule; mine marked not validated.
- 2026-11-13/14: surface change v2: 5 km circle, baseline pair, frame background, three bands (0.11 / 0.15), usability rules; precompute UTF-8.
- 2026-11-13: Morocco backend: CRID series, event windows, `surface_change`, 12-month rate rule, gazetteer, events library.

## Known issues
| ID | Sev | Where | Issue |
|---|---|---|---|
| H1 | high | `download_all.py:805` | Earthdata token hard-coded and in git history (now also on GitHub) |
| H4 | high | `config.LOS_SIGN` | sign not verified on real data; Panama not downloaded; spec does not state the phase sign |
| I1 | high | `recipes/displacement.py:24-29` | ionosphere screen subtracted everywhere; D-009 says mask where not well determined (not implemented) |
| E1 | med | `evidence.py:112` | Overpass call has no User-Agent → HTTP 406; exposure always empty |
| E2 | med | `agent.py:340` | an unavailable source is recorded as `ok: true`; "failed steps" never shows it |
| G1 | med | data | only frame 044/017 gives a usable baseline (023/073 defective on 7 Sep; 095/073 has 2 pairs) |
| S2 | med | `displacement.referenced`, `uncertainty` | noise = per-pixel MAD; understates window error |
| S3 | med | `displacement.los_cm` | only component 0 masked; reference-component check is reported, not corrected |
| S5 | med | `agent.assess` | rain ≥50 mm counted as "agrees" for slow motion; fixed only for surface change |
| M1 | med | `soil_moisture.py` | latest date from last file, value from last valid file; baseline mixes tracks; quality flag unused |
| M2 | med | `raster.render_png` callers | PNG named by product only; overwritten per request |
| M3 | med | `watch.py` | `watches.json` not atomic / not locked |
| M12 | low | `requirements.txt` | `rich` added; still unpinned |
| X1 | low | repo root | untracked file `how --stat --oneline -1` (typo); never `git add .` |
Closed: H2 (`max([])`), H3 (whole-word router), S1 (event windows), M5 (no fallback), S4 (12-month rule), M4 (latest mode) — fixed in code and tested on synthetic data only.

## Open questions
- Has the token been revoked? Who owns it?
- Publish `results/real-data-checks` as is, or a results-only branch?
- `backend/cache/discoveries.json` still holds the old non-physical zones (the API ignores it while discoveries are off): delete it?
- Margins 0.11 / 0.15 come from one geometry and one season: keep, or measure on more data?
- OSM quarry polygon for the Ben Guerir mine (the event stays "not validated" until then).
- GCOV for Morocco (844 granules): needs a decision record.
- Who builds the UI, and with what?
