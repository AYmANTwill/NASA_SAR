# Real-data checks — NISAR Pulse (Phase A)

**Report date: 2026-11-14, updated in the evening.** Phase A was written earlier the same day on branch `results/real-data-checks`
(based on `fa3e0a6`). This update was made on branch `anass/results` (HEAD `c588389`) on the machine that holds the real data
(`D:\project\NASA_SAR\data`). **No code was changed by either pass.** Everything below comes from running the existing code on the
real files, from reading raw `.h5` metadata, or from public web pages where stated. Numbers added in this update come from
script output of 2026-11-14 (`download_all.py status`, `catalog.load()`, `results/noise_with_without_iono_preliminary.csv`,
`results/haouz-flood-2026/gcov_circle_results_draft.json`, raw `.h5` metadata). Sections 2, 4, 6 and 8 were not re-run (marked there). **Sections 4, 5 (Phase 3) and 6 predate the 2026-11-15 ionosphere fix** (`results/panama-2026/IONO_BUG.md`, decision D-011): the code had read the geocoding flags as "phase already corrected", so products with a kept raw `.h5` were processed without the screen.

**Status of the two phases (state on 2026-11-14, evening)**
- Phase A (existing code): done. Panama co-seismic pairs are **now on disk** (section 1); the Panama API call (`POST /ask`) has
  not been made since they arrived.
- Phase B (Ayman's scripts): the files `backend/noise_report.py`, `backend/sign_check.py`, `backend/validate_gps.py`,
  `backend/recipes/corrections.py`, `plan_validation.json` and `plan_venezuela.json` are **now present in this tree, but none was
  run** (no `results_out/` folder exists). Sections 6 and 7 therefore still hold only the preliminary result of the existing code.
- Sign check (section 5): a check on the two track-141 frames was run on 2026-11-14 and is **INCONCLUSIVE**. `NISAR_LOS_SIGN_VERIFIED` was not set.

---

## 1. Data inventory

Folder: `D:\project\NASA_SAR\data` (next to `download_all.py`). Catalog (`catalog.load()`, 2026-11-14 evening):
**153 products = 62 GUNW + 9 GCOV + 82 SME2**. No GOFF. The data folder is **202.5 GB**.
*(At the time of Phase A this was 78 products = 53 GUNW + 25 SME2, 153.4 GB. Phase A's table is replaced by the one below.)*

| Type | Track/frame, direction | Products | First date → last date | Spans (days) |
|---|---|---|---|---|
| GUNW | T004/F005 A, F006 A (Panama) | 1, 1 | 2026-09-30 → 2026-10-12 | 12 |
| GUNW | T040/F084 D, F085 D (Panama) | 1, 1 | 2026-10-02 → 2026-10-14 | 12 |
| GUNW | T076/F005 A, F006 A (Panama) | 1, 1 | 2026-10-05 → 2026-10-17 | 12 |
| GUNW | T141/F084 D (Panama) | 1 | 2026-09-27 → 2026-10-09 | 12 |
| GUNW | T141/F085 D (Panama) | **2** (two configurations of the same pair) | 2026-09-27 → 2026-10-09 | 12 |
| GUNW | T023/F072 D | 8 | 2026-06-27 → 2026-10-13 | 12, 24 |
| GUNW | T023/F073 D | 8 | 2026-06-27 → 2026-10-13 | 12, 24 |
| GUNW | T044/F017 A | 9 | 2026-06-17 → 2026-10-15 | 12, 24 |
| GUNW | T044/F018 A | 9 | 2026-06-17 → 2026-10-15 | 12, 24 |
| GUNW | T095/F071 D | 9 | 2026-06-20 → 2026-10-18 | 12, 24 |
| GUNW | T095/F073 D | **2** | 2026-09-24 → 2026-10-18 | 12 |
| GUNW | T116/F019 A | 8 | 2026-06-22 → 2026-10-20 | 12, 36 |
| GCOV | T044/F017 A | 5 (full + partial) | 2026-09-21 → 2026-10-15 | – |
| GCOV | T023/F073 D | 4 (full + partial) | 2026-10-01 → 2026-10-13 | – |
| SME2 | T015/F019 A | 9 | 2026-06-27 → 2026-10-13 | – |
| SME2 | T023/F071 D, F072 D, F073 D | 2, 9, 19 | 2026-06-27 → 2026-10-13 | – |
| SME2 | T044/F017 A, F018 A | 11, 10 | 2026-06-17 → 2026-10-15 | – |
| SME2 | T095/F071 D, F073 D | 10, 3 | 2026-06-20 → 2026-10-18 | – |
| SME2 | T116/F019 A | 9 | 2026-06-22 → 2026-10-20 | – |

All products in the plans are CRID `P05023` (provisional). Phase A's full listing (78 products): `results/inventory.txt`, not regenerated.
The GCOV products (HH and HV, frequency A) were analysed in `results/haouz-flood-2026/` (draft, section 9).

**Downloader status** (`python download_all.py status --plan <plan> --out D:\project\NASA_SAR\data`, 2026-11-14 evening)

| Plan | Part | Files | Size | Done |
|---|---|---|---|---|
| `plan_morocco.json` | 1 / 2 / 3 | 31 / 47 / 432 | 16.3 / 111.4 / 32.7 GB | 31 / 47 / **56** (27.7 GB left) |
| `plan_validation.json` | 1 (Panama co-seismic) / 2 (pre-event) | 8 / 8 | 13.3 / 13.4 GB | 8 / **0** |
| `plan_panama.json` | 1 / 2 / 3 | 2 / 7 / 23 | 3.3 / 11.1 / 38.8 GB | 2 / 7 / **0** |
| `plan_demo_extra.json` | 1 (GCOV) / 2 (SME2) | 9 / 76 | 17.1 / 7.0 GB | 9 / 76 |
| `plan_venezuela.json` | 1 / 2 | 7 / 7 | 16.1 / 16.0 GB | **0** / **0** |
| `plan_nisar.json` | 1 | 25 | 19.9 GB | 25 (it was 8 at Phase A) |

**Raw `.h5` files kept: yes** (`find` over the data folder): 62 GUNW (139.7 GB), 9 GCOV (17.1 GB), 82 SME2 (7.5 GB).

**Panama co-seismic pairs of 9 Oct 2026: PRESENT** (they were absent when Phase A ran). All **8 pairs of `plan_validation.json` part 1** are on disk, on
four tracks: T4/F005 + F006 (30 Sep → 12 Oct), T40/F084 + F085 (2 → 14 Oct), T76/F005 + F006 (5 → 17 Oct), T141/F084 + F085 (27 Sep → 9 Oct), plus the
second configuration of T141/F085 (`4000`; the first is `2000`). Not on disk: the pre-event Panama pairs (`plan_validation.json` part 2, `plan_panama.json`
part 3) and all of Venezuela. The sign check so far used only T141/F084 and F085 (section 5). Details: `docs/claude/panama_inventory.md`.

## 2. Tests

`cd backend && python tests/test_all.py` → **151/151 checks passed**, 0 failures (`results/tests_output.txt`, run on 2026-11-14 on the earlier tree).
**Not re-run on the current tree** (branch `anass/results`, which now contains Phase B files). Synthetic data only: they check the logic, not the physics.

## 3. Real-file attributes

File: `NISAR_L2_PR_GUNW_032_044_A_017_033_2000_SH_20261003T054606_20261003T054641_20261015T054606_20261015T054641_P05023_N_F_J_001.h5`
(T044 F017 ascending, 3 → 15 Oct 2026, product version 1.0.11, product specification version 1.5.0).
Layer listing: `results/h5_layers_listing.txt`. The complete attribute dump (42 KB, including all processing parameters) is `results/h5_attributes.txt`. The important parts, word for word:

```
== .../grids/frequencyA/unwrappedInterferogram/HH/unwrappedPhase   shape (4311, 4383) float32
   @_FillValue = nan
   @description = 'Unwrapped interferogram between HH layers'
   @grid_mapping = 'projection'
   @max_value = 11.569757461547852   @mean_value = -1.8023937940597534   @min_value = -9.34555721282959
   @sample_stddev = 1.7464157342910767
   @units = 'radians'
== .../metadata/radarGrid/losUnitVectorX   shape (20, 702, 713) float32
   @description = 'East component of the line-of-sight (LOS) unit vector, defined from the target to the sensor, expressed in the east-north-up (ENU) coordinate system with its origin at the target location'
   @long_name = 'LOS unit vector X'   @units = '1'   @valid_max = 1.0   @valid_min = -1.0
== .../metadata/radarGrid/losUnitVectorY   (same, with 'North component ...')
== .../grids/frequencyA/unwrappedInterferogram/HH/ionospherePhaseScreen   shape (4311, 4383) float32
   @description = 'Ionosphere phase screen'
   @max_value = -5.7657856941223145   @mean_value = -7.5504279136657715   @min_value = -9.166746139526367
   @sample_stddev = 0.7486429214477539   @units = 'radians'
== .../ionospherePhaseScreenUncertainty
   @description = 'Uncertainty of the ionosphere phase screen'
   @max_value = 3.364774227142334   @mean_value = 0.6521791219711304   @min_value = 0.273283451795578   @units = 'radians'
== .../metadata/radarGrid/wetTroposphericPhaseScreen   shape (20, 702, 713) float64
   @description = 'Wet component of the troposphere phase screen'   @units = 'radians'
== .../metadata/radarGrid/hydrostaticTroposphericPhaseScreen   (same, 'Hydrostatic component of the troposphere phase screen')
== .../metadata/radarGrid/slantRangeSolidEarthTidesPhase   shape (20, 702, 713) float64
   @description = 'Solid Earth tides phase along slant range direction'   @units = 'radians'
```

Processing flags (`metadata/processingInformation/parameters/geocoding`):
```
azimuthIonosphericCorrectionApplied       = 'True'  'Flag to indicate if the azimuth ionospheric correction is applied to improve geolocation'
hydrostaticTroposphericCorrectionApplied  = 'True'  'Flag to indicate if the hydrostatic tropospheric correction is applied to improve geolocation'
rangeIonosphericCorrectionApplied         = 'True'  'Flag to indicate if the range ionospheric correction is applied to improve geolocation'
wetTroposphericCorrectionApplied          = 'True'  'Flag to indicate if the wet tropospheric correction is applied to improve geolocation'
ionosphere/highBandBandwidth = nan   ionosphere/lowBandBandwidth = nan
```
`metadata/processingInformation/algorithms/ionosphereEstimation`:
```
ionosphereAlgorithm   = 'Range split-spectrum with sub-band interferograms from the main band and the difference of the main and side band of the input RSLCs'
ionosphereFilling     = 'nearest'
ionosphereFiltering   = 'Iterative gaussian filter with 1 filtering'
ionosphereOutliers    = ['coherence', 'subswath_mask']
unwrappingErrorCorrection = 'True'
```
`identification`: `lookDirection = 'Left'`, `orbitPassDirection = 'Ascending'`, `referenceZeroDopplerStartTime = 2026-10-03T05:46:06`, `secondaryZeroDopplerStartTime = 2026-10-15T05:46:06`, `productVersion = '1.0.11'`, `compositeReleaseId = 'P05023'`.

**Which specification the quotes come from.** All quotes below are from **NASA SDS L2_GUNW Rev B (JPL D-102272, 9 Nov 2023)**, text extracted from the PDF.
The file itself reports **product specification version 1.5.0** (see above), so Rev B may not be the version that matches the files.
**A Rev E (Nov 2024) exists and was not read.** Treat every statement below as "Rev B says", not as "the files follow".

**What these mean** (from Rev B):
- The four `...CorrectionApplied = 'True'` flags are in the **geocoding** group: the spec says that group holds "Boolean flags indicating the corrections that have been applied while geocoding the pixel offsets layers ... i.e., wet and dry troposphere correction, slant range and azimuth ionosphere corrections". They concern **geolocation of the offsets, not the interferometric phase**.
- Spec, verbatim: "the estimated ionospheric phase screen is included as a layer in the product but **not applied by default**" ("Due to the variable quality of estimated phase screens in different modes").
- Spec, verbatim: "lookup tables for external phase corrections (e.g., solid Earth tides, ECMWF hydrostatic and wet delays). These phase corrections, when available, are **not applied to the data** but are available to users for application in post-processing workflows."
- Spec: "the current (secondary) and the immediately preceding in time L1_RSLC product (reference)": the secondary is the **later** acquisition. The LOS unit vector is "the vector from the target to the sensor".
- **The sign of the unwrapped phase is not stated** in the file attributes or in the Rev B text (no mention of "conjugate", "toward" or "away"). NISAR is left-looking.

**Convention by derivation (not a verification).** Per the tool documentation (ISCE3; reported to me, **not re-read in this session**), the interferogram is formed with the
reference time conjugated against the secondary. With the usual propagation phase φ = −4π·range/λ, that gives
φ_ref − φ_sec = +4π·(range_sec − range_ref)/λ: **positive phase = range increase = ground moving away from the satellite**. The code's
`d = −λ/(4π)·φ` (`recipes/displacement.py:31`, `LOS_SIGN = 1`) then makes positive = toward the satellite, consistent with this derivation.
This is a derivation from a convention, **not a verification on this earthquake**: it has not been tested against a map or a GNSS value (section 5).

## 4. Precompute results (`python precompute.py`, run on the real data, about 2 minutes, rc 0)

One line per event. **Failed steps: none for all five** (see section 8 for the OpenStreetMap step that reports "ok" while unavailable). Details and all reasons: `results/precompute_events.md`; full cached answers: `results/events/*.json`; console output: `results/precompute_output.txt`.

| Event | Type | Confidence | Alert | Verdict (short) |
|---|---|---|---|---|
| haouz-flood-2026-10-10 (Asni) | surface_change | low | yellow | 3→15 Oct, 12 d: mean coherence loss within 5 km 0.15, excess 0.12 over the frame mean (0.03): **borderline**, just above the 0.11 level (1 % of no-event circles), below 0.15; 2.69 km² lost more than 0.3 (0.04 km² in the previous pair). Not enough to say the surface changed. |
| haouz-soil-moisture | soil_moisture | low | none | 18 Oct: 0.174 m³/m³ (−0.027 vs the mean of 7 passes), **within the product's uncertainty (0.028)**. |
| gharb-soil-moisture | soil_moisture | low | none | 20 Oct: 0.219 m³/m³ (+0.025 vs the mean of 6 passes), **within the product's uncertainty (0.028)**. |
| ben-guerir-mine (status: **not validated**) | surface_change | low | none | latest pass 3→15 Oct vs the one before: loss 0.03 vs 0.04 frame mean (excess −0.01): no clear local change. Mine centroid, no polygon. |
| al-wahda-surroundings | slow_motion | low | none | "Uncorrected line-of-sight change, sign unverified": 20 Jun → 18 Oct (9 pairs, 120 d), 43.4 mm cumulative (noise per pair ± 29.8 mm); no rate (< 365 d); ionosphere screen subtracted on the earlier tree (not validated; after the 2026-11-15 fix a re-run keeps the raw phase on the pairs where subtracting does not lower the sigma, so the figures can change), troposphere not corrected; chain crosses the 27 Jul–10 Aug data gap through 1 pair; reference in the point's connected component. |

Precompute was run on the earlier tree and **not re-run** since. It predates the 2026-11-15 `already_applied` fix and the `NISAR_IONO_GUARD` option, so the cached answers (`results/events/*.json`, `backend/cache/`) may change on a re-run (needs approval).

Evidence steps: Open-Meteo worked in all five. The rain is **ERA5 reanalysis via Open-Meteo, one grid cell, context only**: it is modelled, not a gauge,
and its daily totals are cut at UTC midnight (`backend/evidence.py:65-66`, `timezone="UTC"`). For the Haouz flood window (3 to 15 Oct) the total and the peak day (9 Oct, the day before the
flood) are in `results/events/haouz-flood-2026-10-10.json`. **Source of the flood itself:** Hespress, "Haut-Atlas : de violentes crues éclair frappent Al Haouz",
Sunday 11 Oct 2026, 16:05 (https://fr.hespress.com/491813-haut-atlas-de-violentes-crues-eclair-frappent-al-haouz.html), which places the storms on Saturday 10 Oct in the communes of Asni and
Moulay Brahim and says the road to Imlil was cut (page opened on 2026-11-14). The code itself cites no source for the flood date. **OpenStreetMap was "unavailable" in all five** (HTTP 406, section 8). USGS earthquakes: not called (precision "day" events).

## 5. Sign check

**Conclusion: INCONCLUSIVE on our own data. `NISAR_LOS_SIGN_VERIFIED` was not set** (recommended value for now: unset / 0).

**What was run (2026-11-14, evening).** The sign check on the two track-141 descending frames (T141/F084 and F085, 27 Sep → 9 Oct 2026), using the repo's `displacement.los_cm`
(sign +1, ionosphere screen requested but, because of the flag bug, most likely not applied (raw phase), coherence ≥ 0.3 and connected component ≠ 0 kept), the USGS finite-fault geometry (below), and the median LOS on coherent pixels at least
10 km from the rupture, on each side of the fault. It used a scratchpad script (`sign141.py`); its output was **not saved in `results/`**, so the numbers below are from that run, not from a file here.
*Phase B's `sign_check.py` was not run.*

**Why it is inconclusive:**
1. **The fault sits at the frame edges.** The finite-fault centre (7.54 N) is at the south end of F084 and the north end of F085, so neither frame holds the rupture cleanly.
2. **Almost no coherent pixels:** valid pixels were **20 %** (F084) and **2 %** (F085), mostly sea or low-coherence forest. In F084, 52,159 of the 53,329 usable pixels at least 10 km from the rupture lie on the NE side, so there is no across-fault contrast to test.
3. **The far-field values are not physical:** the far-field reference median (≥ 60 km) was −33.0 cm in F084 and +72 cm in F085; F085's side medians are about ±1 m with a scatter of up to 76 cm. These look like arbitrary offsets between unwrapped components or unwrapping errors, not ground motion.
4. After referencing, F084's NE side is +0.6 cm (no signal). The expected sign cannot be confirmed or refuted from these two frames.

**Phase 3 (all 8 co-seismic pairs, T4, T40, T76, T141; files in `results/panama-2026/`).** Verdict: **INCONCLUSIVE.** `NISAR_LOS_SIGN_VERIFIED` was not set.
- **Independent test (USGS finite fault run forward with Okada, `ffm_sign_iono.json`, `ffm_sign_console.txt`; this "iono" run actually used the raw phase, variant A of `ffm_by_variant.md`).** k > 0 at more than 3σ on 6 of 7 pair-frames: T76 F006 (+33.0σ), T76 F005 (+14.5σ), T40 F085 (+9.9σ), T40 F084 (+14.1σ), T141 F085 (+11.3σ), T141 F084 (+59.2σ); T4 F005 is inconclusive (+2.9σ). None is negative. This agrees with +1, but k varies from 0.12 to 51.7 between frames (a scale-free ratio, so only its sign is used), and σ(k) ignores spatial correlation (`ffm_sign.py:74-77`), so the significances are overstated. Its partial correlation r is only 0.08 to 0.83 (0.24 to 0.35 for 4 of 7 frames).
- **Inversion (`fault/sign_plus/`, `fault/sign_minus/`, 50 bootstraps each, `sign_decision.json`).** Pooled variance reduction VR(+1) = 0.824 and VR(−1) = 0.818: a difference of 0.006 against the required 0.10, so **the inversion does not tell the signs apart**. With +1 the fit is flagged unstable (parameters at a search bound: top depth, slip) and keeps the plane 25/75/−155 (not the left-lateral 288/66/−17); Mw 7.51 ± 0.04. With −1 the fit is stable, keeps the left-lateral plane, Mw 6.95 ± 0.04 (marked "disagree" with the USGS Mw 7.7). The RMS of the residuals is about 25 cm for both. The three rules of `sign_decision.py`: (a) met, (b) not met, (c) not met → "undecided". These fits used the raw phase (variant A). Without a noise model, for the three ionosphere variants (`sensitivity_iono.md`), the pooled VR(+1) − VR(−1) is 0.0066 (A raw), 0.0049 (B fixed code) and 0.0232 (C forced subtraction): still undecided.
- **The ionosphere with/without comparison was not possible at first, because of a code bug, not because the products are corrected.** The code read the geocoding flags ("applied to improve geolocation") as "phase already corrected" and skipped the screen, so both `ffm_sign` runs used the raw phase and gave identical numbers (`ffm_sign_iono.json` = `ffm_sign_noiono.json`). The bug is fixed; the comparison now exists as variants A (raw), B (fixed code, per-pair guard) and C (forced subtraction, `NISAR_IONO_GUARD=off`) in `ffm_by_variant.md`, `sensitivity_iono.md` and `ffm_rule_a_recount.md`. The sign verdict is undecided in all three.
- **Two degenerate pairs and the recount of rule (a) (2026-11-15).** T76 F005 has 79.9 % exact zeros in its finite unwrapped phase and T4 F005 64.2 % (`zero_sigma_diagnosis.json`; 99.85 % and 100 % of those zeros lie inside connected components > 0, so the component mask does not remove them; cause unknown). They are excluded only as a data-quality sensitivity analysis (`EXCLUSION_CRITERION.md`; the thresholds were chosen knowing which pairs they would catch; any cutoff between 0.09 and 0.64 gives the same set). Without them the per-track T76 lean towards −1 disappears (VR difference −0.131 → −0.006, A and B). Rule (a) is still met in A, B and C, on 3 tracks and 3 geometries (T40 and T141 descending, T76 ascending; 5 pair ids, 6 pair-frames), and rules (b) and (c) are not. The LOS vectors were checked (`los_check.md`): east sign as expected on every pair, a forward-model check of the code chain, not an observation of the sign.
- **Why it stays inconclusive:** the maps (`sign_check.png`) hold very few coherent pixels per frame; the pooled variance reduction is dominated by T141 F085 (0.97 per track, 98th percentile |LOS| 232 to 262 cm, an implausible value that suggests unwrapping offsets); three frames have negative per-track VR with +1 (T76 F006, T4 F005, T141 F084: −0.36, −0.01, −0.27). The predicted ascending/descending reversal (PREDICTION.md) is not tested separately by the code; the test pools tracks.
- The T141 F085 `2000` and `4000` variants share a name in the output, so 7 rows appear for 8 pairs.
- The run was launched with `NISAR_LOS_SIGN` unset (for `ffm_sign`, `sign_check.py` and the +1 run) and inline `=-1` for the −1 run. The 5-bootstrap run of Phase 2 was skipped on request. `python -m science.sign_decision` has no command-line entry; the decision JSON is the one written by `panama_fault`.

*What is still not done:* a decision by a human; a per-track (not pooled) ascending-versus-descending comparison.

*What the published references show:*
- **USGS origin** (product `origin`, event page `us6000u18k`, https://earthquake.usgs.gov/earthquakes/eventpage/us6000u18k): M 7.7 Mww, 2026-10-09 17:56:05.537 UTC, "10 km WSW of Pitaloza Arriba, Panama", **epicentre 7.6069 N, 80.7566 W, depth 10 km ("operator assigned")**. Listed products: shakemap, finite-fault, moment-tensor, losspager, dyfi, ground-failure, oaf. **No InSAR product.**
- **USGS moment tensor** (product `moment-tensor`, `us_6000u18k_mww`, reviewed; centroid depth 13.5 km as in the Phase A run): nodal plane 1 strike 25.21°, dip 74.77°, rake −155.3°; nodal plane 2 strike 288.32°, dip 66.22°, rake −16.68°. Both rakes are close to 0° or ±180°, so the mechanism is **strike-slip**, not thrust.
- **USGS finite fault** (product `finite-fault`, `us6000u18k_1`, reviewed): centre **7.54 N, 80.769 W, depth 12.647 km**, strike 295°, dip 60°, rake −16°, length 55 km, width 33.6 km, maximum slip 11.06 m. Its strike matches nodal plane 2; a rake near 0° on that plane is left-lateral (derived from the rake, not stated in the product). The code's point for Panama (`backend/config.py:74`, 7.59 N, −80.77) matches none of these exactly.
- **Published interferogram (a blog, not an official product).** The Earthquake Insights post of 10 Oct 2026 (Hubbard & Bradley) shows the COMET LiCSAR NISAR interferogram of **2026-09-27 → 2026-10-09 on track 141 descending**. As reported to the team, its sign description is: **north/northeast of the fault the ground moved toward the satellite, south/southwest away from it.**
  The same source reports that Eric Fielding said an **official NISAR map was coming**. **I could not open this post or confirm Fielding's note** (a web search on 2026-11-14 returned nothing for them), so both are second-hand.
  This replaces Phase A's statement "no published map". It is not an official NASA/JPL/ASF/OPERA product; none was found.
- A published NISAR line-of-sight page exists for a **different** event, the M7.5 Venezuela earthquake (https://topex.ucsd.edu/VNZ_7.5/index.html); it could serve as a second reference. Venezuela is not on disk (section 1).

*What is still undetermined:*
1. Our own maps do not yet show the published pattern or its opposite, so "same lobes, opposite colours" cannot be judged (above).
2. The product spec (Rev B) does not state the phase sign; section 3 gives a derivation of the convention, not a verification.
3. **Expected pattern:** the published two-lobe pattern for this geometry (T141 descending): north/northeast toward the satellite, south/southwest away. *Phase A expected four lobes of alternating sign for a strike-slip event; that expectation is replaced by the published two-lobe pattern for this look direction.* Horizontal motion changes sign between ascending and descending; vertical motion does not. An ascending-versus-descending consistency test is still useful, and the absolute polarity needs a map or a forward model (for example Okada with the USGS finite-fault slip, or a GNSS displacement).
4. Note for the team: the synthetic Panama test data (`backend/tests/make_synthetic.py:83`) assume 25 cm uplift + 15 cm east, which is not what a strike-slip event produces; this is fine for testing logic but must not be used as evidence for the sign.
5. An asc/desc decomposition into vertical and east-west is **approximate and assumes no north-south motion**, and LOS is not vertical. For a nearly pure strike-slip event the assumption is poor; do not report "uplift" or "subsidence" from it.

*Related, already measurable (not the ground-motion sign):* the code subtracts the ionosphere screen from the phase only where it lowers the frame-wide sigma (2 of the 7 Panama pair ids; the earlier tree subtracted everywhere, and, between the corrections module and the 2026-11-15 fix, the flag bug skipped it on all kept-.h5 products, `IONO_BUG.md`). Section 6 shows that **subtracting reduces the frame-wide variance and adding increases it in 11 of 12 pairs**, so the screen and the unwrapped phase share a sign convention. That does not tell whether positive phase means "toward" or "away" for the ground.

## 6. Noise report

**Phase B not run** (Ayman's `noise_report.py` is now in the tree but was not run). Preliminary result with the *existing* code, whole frame, robust sigma of the unwrapped phase in cm (coherence ≥ 0.3, connected component ≠ 0), 12-day pairs, two pairs per frame (`results/noise_with_without_iono_preliminary.csv`):

| Frame | Pair | raw | minus iono (forced subtraction, not what the per-pair guard does) | plus iono (wrong sign) | iono median (rad) | raw ÷ minus-iono |
|---|---|---|---|---|---|---|
| 44/17 A | 3→15 Oct | 3.12 | 2.21 | 4.84 | −7.6 | 1.41 |
| 44/17 A | 28 Aug→9 Sep | 6.36 | 1.83 | 13.69 | +14.1 | 3.48 |
| 23/73 D | 1→13 Oct | **96.36** | 2.62 | 196.95 | −28.3 | 36.78 |
| 23/73 D | 26 Aug→7 Sep | **0.00** | 6.13 | 7.21 | −24.5 | not defined (defective pair) |
| 95/71 D | 6→18 Oct | 11.57 | 1.92 | 22.21 | −6.6 | 6.03 |
| 95/71 D | 31 Aug→12 Sep | 5.97 | 2.98 | 9.88 | +16.2 | 2.00 |
| 116/19 A | 8→20 Oct | 2.65 | 2.65 | 2.26 | +5.1 | 1.00 |
| 116/19 A | 2→14 Sep | 5.92 | 2.50 | 9.69 | +7.3 | 2.37 |
| 95/73 D | 24 Sep→6 Oct | 24.9 | 3.89 | 52.06 | +36.0 | 6.40 |
| 95/73 D | 6→18 Oct | **55.3** | 3.24 | 108.01 | −62.2 | 17.07 |
| 44/18 A | 3→15 Oct | 3.61 | 3.39 | 5.88 | −5.6 | 1.06 |
| 44/18 A | 28 Aug→9 Sep | 8.69 | 1.53 | 15.31 | +19.1 | 5.68 |

The last column is computed by script from `results/noise_with_without_iono_preliminary.csv` (2026-11-14); the other columns are that file, rounded.

- Subtracting the ionosphere screen gives the **lowest sigma in 10 of 12 pairs**. The per-pair ratios raw ÷ minus-iono run from **1.00 to 36.78** (not "2 to 40"): 1.00, 1.06 and 1.41 in three pairs, between 2.00 and 6.40 in six pairs, and 17.07 and 36.78 in the two worst raw cases (55 and 96 cm). The two pairs where it is not the lowest: 116/19 8→20 Oct (ratio 1.00, the screen is almost flat, plus-iono is lower by 0.39 cm) and 23/73 26 Aug→7 Sep (a defective pair with flat raw phase, sigma 0.00). Adding the screen (wrong sign) is worse than the raw phase in 11 of 12 pairs, so the screen and the phase share a sign convention.
- **Conclusion: subtracting the screen reduces the frame-wide variance. Local validity is not demonstrated (see section 8, item 3).** A smaller whole-frame sigma does not show that the correction is right at a given point (the screen and the phase are unwrapped separately and can disagree by whole fringes locally).
- **Limits of this table:** (1) the screen has an **arbitrary offset** (its median ranges from −62 to +36 rad), so only its spatial variation is meaningful, not its level; (2) the **valid-pixel masks differ per pair** (`valid_px` in the CSV runs from 836,966 to 9,343,937), so sigmas are computed on different areas and are not strictly comparable; (3) the sigma is the whole-frame robust sigma, which does not measure the error at a site.
- Troposphere and solid-Earth tides: **not measured here** (the code does not use them; they are lookup cubes without a DEM-height pick in the existing code). That is for Ayman's script.
- 23/73 26 Aug→7 Sep: the unwrapped phase itself is flat (sigma 0.00) and the coherence is 0.03–0.09 over the whole area: a defective pair (the 7 Sep acquisition of track 23). The same applies to 7 Sep → 19 Sep.

## 7. GPS validation

**Phase B not run.** `backend/validate_gps.py` is now in the tree but was not run, and no GNSS data file was read. It needs Panama (or other) pairs near a GNSS station; the Panama co-seismic pairs are on disk (section 1), but with the current data no station is known to be inside the Morocco frames.

## 8. Problems found in the code (nothing was fixed)

| # | File:line | Problem | Suggested fix |
|---|---|---|---|
| 1 | `backend/evidence.py:112` | The Overpass request sends **no User-Agent**. On the real run every event gets "OpenStreetMap unreachable (406 Client Error: Not Acceptable for url: https://overpass-api.de/api/interpreter)", so the exposure (buildings, roads, dams, quarries) is always empty. The calls at lines 38, 65, 88 also send none (they work today). | `requests.post(..., headers={"User-Agent": "<generic app name>/1.0"})`; use the same header for all outside calls. |
| 2 | `backend/agent.py:340` | `steps.run("what is exposed (OpenStreetMap)", ...)` records the step as `ok: true` because `evidence.exposure` returns `{"status": "unavailable"}` instead of raising. So "failed steps" is empty even when a source failed (all five events here). | In `Steps.run` or after the call, mark `ok: false` when the returned dict has `status == "unavailable"` (and keep the error text). |
| 3 | `backend/recipes/corrections.py` (`_apply_iono`, `already_applied`; formerly `displacement.py:24-29`) | On the earlier tree the ionosphere screen was subtracted from every pair; since D-011 the default subtracts it only where it lowers the frame-wide sigma (`keep_raw_phase`), and the geocoding-flag bug is fixed (`IONO_BUG.md`). The product spec says the screen is "not applied by default" because its quality varies. Section 6 shows the subtraction reduces the frame-wide variance (96 → 2.6 cm in the worst pair); it does not show that the correction is valid locally, and the screen and the unwrapped phase are unwrapped separately, so they can disagree by whole fringes locally. Earlier check at the centres of the top automatic-discovery zones (2 km median, now disabled): zone 3 raw −3.6 cm, screen −71.5 cm, corrected +66.6 cm; zone 4 raw −65.8, screen +130.4, corrected −200.4; zone 6 raw −36.7, screen −92.2, corrected +46.1. The screen's own uncertainty layer says ±1–7 cm there. This is the likely reason the discoveries were not physical. | Do not change silently: record a decision (subtract / mask where the screen is extreme or its uncertainty is high / choose per pair by noise). Ayman's noise report is the right tool to decide. |
| 4 | `backend/tests/make_synthetic.py:83` (+ `events.py` Panama fixture) | Synthetic Panama = 25 cm uplift + 15 cm east. The real USGS mechanism is **strike-slip** (section 5). | Keep for logic tests, but document it, and build the real sign test on the two-lobe pattern published for track 141 descending (section 5). |
| 5 | repo root | An untracked file named `how --stat --oneline -1` (a typo from a git command) was next to `README.md`. **Deleted on 2026-11-14.** | None. |
| 6 | `backend/recipes/damage.py` + data | Frame T023/F073 cannot give a usable baseline: its pairs that contain the 7 Sep 2026 acquisition are defective (flat phase / coherence 0.03–0.09). T095/F073 has only 2 pairs, so it can never have a baseline. The recipe handles both (not usable), but the surface-change answers therefore rest on **one geometry (044/017)** only. | Download more T095/F073 history and re-acquire or skip the 7 Sep T023 pairs when choosing baselines; nothing to fix in code. |
| 7 | `download_all.py status` (default plan) | With no `--plan`, it reports the Panama/Atlas plan (`plan_nisar.json`) and showed "part 1: 8 finished" at Phase A, although none of those 8 was a Panama pair (file-name matches with the Morocco plan). Confusing, not a bug in the data. | Say in the output which plan was read, or warn when a data folder was built from another plan. |
| 8 | `backend/config.py:14` (`WAVELENGTH_M = 0.2384`), `config.py:21` (`FRINGE_CM`) | **Found on 2026-11-14, not fixed.** The code's wavelength (comment: centre frequency ~1.257 GHz) matches neither mode in the raw files: `grids/frequencyA/centerFrequency` is **1239 MHz with rangeBandwidth 40 MHz** (name field `4000`; T141/F084 and F085 `4000`) and **1229 MHz with 20 MHz** (name field `2000`; T141/F085 `2000` and T044/F017 3→15 Oct). That is λ = 0.24196 m and 0.24393 m, fringes of 12.10 cm and 12.20 cm, against 11.92 cm in the code. The code's scale is **1.47 % low for 40 MHz products and 2.27 % low for 20 MHz products** (script: `c/f`, 2026-11-14). Only 4 files were read; the other products were not checked. | Not changed (no code edits in this pass). Decision needed: read the centre frequency per file, or use one value per mode. Scales every displacement in cm, not the signs. |

## 9. Anything surprising

- **Panama was not on disk when Phase A ran** (the data folder had been built from the Morocco plan only). **It is now**: the 8 co-seismic pairs (13.3 GB) plus a second configuration of T141/F085 (section 1). The first sign check used only T141/F084 and F085 and is inconclusive (section 5); the Panama API call and the GPS check have not been run.
- The 8 co-seismic Panama pairs are on **four tracks** (4, 40, 76, 141), not only 141 and 4.
- **Wavelength.** The code uses 0.2384 m (fringe 11.92 cm, `config.py:14,21`). The published fringe spacing is 12.1 to 12.2 cm depending on the mode, and the raw files give 12.10 cm (1239 MHz, 40 MHz mode) and 12.20 cm (1229 MHz, 20 MHz mode), so the code's scale is 1.47 % and 2.27 % low (section 8, item 8). The centre frequency has to be checked **per file**: it differs between modes, and the name field `2000` / `4000` matched 20 / 40 MHz in the 4 files read (not checked on the others).
- **The raw phase is dominated by the ionosphere** in this period: whole-frame sigma up to 96 cm (23/73, 1→13 Oct) and 55 cm (95/73, 6→18 Oct) before the screen is subtracted, 2–6 cm after (forced subtraction, as measured in section 6). The screen medians range from −62 to +36 rad.
- NISAR is **left-looking**; the code already handles this (`recipes/decompose.py:20-22`).
- In this file the `...CorrectionApplied = 'True'` flags look reassuring, but they only describe geolocation of the pixel offsets (spec text above). No tropospheric or tidal correction is applied to the phase, and the code does not apply them either.
- The 2026-07-27 → 08-10 data gap is crossed by exactly **one** bridging pair in each Al Wahda series, and in both the reference shares the point's connected component.
- Both geometries at Al Wahda disagree in sign (+43.4 mm for 95/71, −20.0 mm for 116/19) with 29–30 mm noise per pair: the answer is noise, as the verdict says.
- The `.h5` raw files were all kept (139.7 GB for GUNW, 62 products, see section 1), so layers can be re-extracted without downloading again.
- Rain, **ERA5 reanalysis via Open-Meteo, one grid cell, context only** (modelled, not a gauge; daily totals are cut at UTC midnight): 37.9 mm over the Haouz flood window 2026-10-03 → 2026-10-15, with the **peak day on 2026-10-09 (13.4 mm), the day before the flood of 10 Oct**; 59.7 mm in the 30 days before the Haouz soil-moisture date (`results/events/*.json`, `results/precompute_events.md`). The flood is sourced to the Hespress article of 11 Oct 2026 (section 4), not to the rain figure.
- **GCOV on 44/17 and 23/73 (draft, `results/haouz-flood-2026/`).** HH and HV, frequency A, linear power (file attribute `units = "1"`). On 44/17, over the storm interval 3 → 15 Oct, the 5 km circle means changed by +1.13 dB (HH) and +0.69 dB (HV) at Asni, +1.12 and +0.76 dB at Moulay Brahim, −0.02 and +0.01 dB at Imlil (`gcov_circle_results_draft.json`). Against a null of 2,000 random circles in the baseline interval (21 Sep → 3 Oct), Asni and Moulay Brahim are borderline: HH just outside the 2.5–97.5 % range, HV just inside. **Verdict for all three sites: no clear change.** 23/73 has no baseline pair and is not usable. The nearest GCOV pass after the storm day is 13 Oct 19:20 UTC (2.8 days after the end of 10 Oct, on 23/73, which has no baseline); the nearest usable one is 15 Oct on 44/17 (about 4.2 days after), backscatter also responds to soil moisture and vegetation, and the GCOV and coherence results use the same radar passes, so they are not independent. Not a flood map; "candidate surface-change area" is the most the data support.
