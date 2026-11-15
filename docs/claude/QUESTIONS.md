# Open questions for the team

> Kept by Claude Code, updated at every phase STOP. Answer in the "Answer" column; I move answered rows to "Closed".
> Last update: 2026-11-14, step 2 and 4 of the iono work.

## Open

| # | Phase | Question | Why it matters | Needed from | Answer |
|---|---|---|---|---|---|
| Q1 | 4 | Commit `backend/cases/out/` (fit JSON, sign JSON, fit PNG, 0.7 MB) and `backend/cases/figures/` (1.9 MB) too, or only the 4 case JSONs? | `out/` is the Panama fit evidence; figures carry the case maps. | Anass | |
| Q2 | 4 | Who fixes the generator problems in `backend/science/` (off limits to me)? (a) Haouz headline "Flooded area mapped by NISAR", finding id `flooded_area`, km² unit; (b) placeholder findings with value 0.0 (Panama `mw` is even labelled `disagree` against USGS 7.7); (c) no "provisional / CRID P05023" label in any case file. | (a) breaks the "candidate surface-change area" rule. Do not commit the case JSONs before it is fixed. | Teammate (science/) | |
| Q3 | 4, 6 | USGS event id of the 24 June 2026 Venezuela mainshock? | Without it the Venezuela case stays a draft (no date, map or bbox). | Anass | |
| Q5 | 4, 6 | Run `validate_gps.py --auto` now so `results/gps/` exists and the `ionosphere-gps` case fills in? (Phase 6.2, a noise check, not a sign test.) | The GPS case is empty without it. | Anass | |
| Q6 | 4 | Do `science.exposure_run` and the `*_exposure.json` files need the network (OSM)? Are they wanted for the freeze? | All four cases list the exposure file as missing. | Anass / teammate | |
| Q9 | 3 | The T141 F085 `2000` and `4000` pairs share a name, so 7 rows show for 8 pairs, and F085 reaches 232 to 262 cm (98th percentile), which looks like unwrapping offsets. Keep both variants in the inversion? | F085 dominates the pooled variance reduction. | Teammate | |
| Q10 | 3 | Sign verdict is INCONCLUSIVE. Ship Panama with the "sign unverified" label (as PREDICTION.md says)? | `NISAR_LOS_SIGN_VERIFIED` stays unset until a human decides. | Anass + teammate | |
| Q11 | earlier | Write `tools/data_report.py` from scratch, or will you place your existing script in `tools/`? | The data-inventory task is blocked: the script does not exist. | Anass | |
| Q12 | earlier | Revoke the Earthdata token and remove it from `download_all.py` (STATUS H1)? | The token is in the history of a branch that is on GitHub. | Anass | |
| Q13 | earlier | Download `plan_panama.json` part 3 (23 pre-event rows, 38.8 GB) or `plan_validation.json` part 2, with `--out D:\project\NASA_SAR\data`? Phase 4 says all downloads are finished, so probably not needed. | Only if the pre-event pairs matter for noise models. | Anass | |
| Q14 | earlier | The Earthquake Insights post and Eric Fielding's note are second-hand and unverified (REPORT section 5). Can someone open them and confirm the sign description? | They are the only published sign reference for track 141. | Anass | |

| Q15 | 5 | 33 of 103 GUNW products still use the fallback 0.2384 m (no kept `.h5`, and the downloader does not store `centerFrequency` in `radar_geometry.npz`). Add it to the downloader's short metadata and re-extract, or accept the 1.5 to 2.3 % error for those products? | Affects displacement scale for those products; Panama co-seismic pairs are fine. | Anass (I may not edit `download_all.py`) | |
| Q16 | 5 | `config.FRINGE_CM` (11.92 cm) is stale and still used by `discoveries.py` (off by default). Leave it, or make it per product? Outside my edit list. | Only matters if discoveries are re-enabled. | Teammate | |

| Q19 | 2 | T4 F005 (64 % exact zeros in the unwrapped phase) and T76 F005 (80 %) are degenerate (`results/panama-2026/zero_sigma_diagnosis.json`). Should the Panama fit, the case files and the sign test exclude pairs by the written criterion (`EXCLUSION_CRITERION.md`: zero fraction >= 0.10 or usable fraction < 0.01)? That removes T4 entirely and leaves T76 with F006 only (one ascending geometry). Why these two pairs are mostly zero is unexplained (unwrapping failure? filled values?). | Without them the T76 lean towards -1 disappears (VR difference -0.131 to -0.006). | Anass + teammate | |
| Q18 | 2 to 4 | Doc corrections done (REPORT, DECISIONS D-011, STATUS). Still NOT approved: re-run `precompute.py` and regenerate the case files (cached answers and `backend/cases/*.json` predate the iono fix). Approve? | Cached answers may change for products with a kept raw .h5. | Anass | |
| Q20 | 5 | The Panama limits (5 items, fr/en/ar) are in `results/panama-2026/limits_panama.json`. The Panama case limits are written by `backend/science/` (off limits to me): who adds them (or lets the generator read this file)? | They are required for the final Panama case. | Teammate | |

## Closed

| # | Question | Answer |
|---|---|---|
| C1 | Commit PREDICTION.md before any run (Phase 1) | Done by Anass, 2026-11-14. |
| C2 | Is the 5-bootstrap Phase 2 run needed? | Skipped on request; Phase 3 ran with 50 bootstraps. |
| C4 | Haouz findings.json (Q4) | Written 2026-11-14 (T1): 9 findings, validated by `science.cases --dry-run`; case stays draft (no map with a layer, no exposure file). |
| C5 | Per-track sign comparison (Q7) | Done (T2): `results/panama-2026/per_track_sign.md`. Descending T141/T40 favour +1 by 0.013/0.015, ascending T4/T76 favour -1 by 0.038/0.131; mostly small differences. |
| C6 | Q8 and Q17 (ionosphere flag bug) | Fixed in `corrections.already_applied` (geocoding flags ignored, test added). Analysis in `results/panama-2026/IONO_BUG.md`; the statements listed there still need editing, and `precompute.py` needs a re-run (your OK). |
| C3 | Wavelength decision (REPORT section 8, item 8) | Superseded by the merged `recipes/wavelength.py`; reviewed in Phase 5 (`wavelength_review.md`). |

## Notes on rules applied
- Rule 6 (long runs): I ran the 12-minute fits myself because Anass said "execute the commands yourself".
- No `NISAR_LOS_SIGN_VERIFIED` or `NISAR_CORRECTIONS` was set; `NISAR_LOS_SIGN` only inline for the −1 run.
