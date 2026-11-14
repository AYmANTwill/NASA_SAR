# Real-data checks — NISAR Pulse (Phase A)

Branch `results/real-data-checks`, based on `origin/feat/surface-change-baseline-discoveries-off` (commit `fa3e0a6`).
Run on 2026-11-14 on the machine that holds the real data (`D:\project\NASA_SAR\data`, 153 GB). **No code was changed.**
Everything below comes from running the existing code on the real files, plus public web pages where stated.

**Status of the two phases**
- Phase A (existing code): done, except the Panama API call, because **no Panama pair is downloaded** (see section 1).
- Phase B (Ayman's scripts): **not started**. `git fetch origin` shows no `origin/feat/validation-corrections` yet, and there is no `plan_validation.json`. Sections 6 and 7 are empty on purpose; section 5 is "undetermined".

---

## 1. Data inventory

Folder: `D:\project\NASA_SAR\data` (next to `download_all.py`). Catalog: **78 products = 53 GUNW + 25 SME2**. No GCOV, no GOFF.

| Type | Track/frame, direction | Products | First date → last date | Spans (days) |
|---|---|---|---|---|
| GUNW | T023/F072 D | 8 | 2026-06-27 → 2026-10-13 | 12, 24 |
| GUNW | T023/F073 D | 8 | 2026-06-27 → 2026-10-13 | 12, 24 |
| GUNW | T044/F017 A | 9 | 2026-06-17 → 2026-10-15 | 12, 24 |
| GUNW | T044/F018 A | 9 | 2026-06-17 → 2026-10-15 | 12, 24 |
| GUNW | T095/F071 D | 9 | 2026-06-20 → 2026-10-18 | 12, 24 |
| GUNW | T095/F073 D | **2** | 2026-09-24 → 2026-10-18 | 12 |
| GUNW | T116/F019 A | 8 | 2026-06-22 → 2026-10-20 | 12, 36 |
| SME2 | T015/F019 A | 2 | 2026-10-01 → 2026-10-13 | – |
| SME2 | T023/F071 D, F072 D, F073 D | 2, 2, 4 | 2026-10-01 → 2026-10-13 | – |
| SME2 | T044/F017 A, F018 A | 3, 3 | 2026-09-21 → 2026-10-15 | – |
| SME2 | T095/F071 D, F073 D | 3, 3 | 2026-09-24 → 2026-10-18 | – |
| SME2 | T116/F019 A | 3 | 2026-09-26 → 2026-10-20 | – |

All products are CRID `P05023` (provisional). Full listing: `results/inventory.txt`.

**Downloader status** (`results/status_plan_nisar.txt`, `results/status_plan_morocco.txt`)
- `plan_morocco.json`: tier 1 = 31/31 files (16.3 GB) done, tier 2 = 47/47 (111.4 GB) done, **tier 3 = 0/432 SME2 files** (32.7 GB left).
- `plan_nisar.json` (Panama + Atlas plan): part 1 shows 8 of 25 done and parts 2–5 31–46 % done. These are probably file-name matches with the Morocco plan: none of the files on disk is a Panama pair (checked in the catalog and in `manifest.csv`, see below).

**Raw `.h5` files kept: yes.** 53 GUNW `.h5` (125.2 GB) and 25 SME2 `.h5` (2.4 GB); `data/_tmp` is empty. The whole data folder is 153.4 GB.

**Panama co-seismic pairs of 9 Oct 2026: NOT present.** No folder matches track 141 frames 84/85, track 4 frames 5/6 or any Panama product; the manifest only lists Morocco files.
- `plan_nisar.json` holds 31 Panama rows (52.1 GB). The co-seismic ones are **8 pairs, 13.3 GB, all in part 1**, on four tracks (not only 141 and 4):
  T4/F005 + F006 (30 Sep → 12 Oct), T40/F084 + F085 (2 → 14 Oct), T76/F005 + F006 (5 → 17 Oct), T141/F084 + F085 (27 Sep → 9 Oct).
- Phase B's `plan_validation.json` is the planned way to fetch them.

## 2. Tests

`cd backend && python tests/test_all.py` → **151/151 checks passed**, 0 failures (`results/tests_output.txt`).
Synthetic data only: they check the logic, not the physics.

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

**What these mean** (confirmed in the official product specification, NASA SDS L2_GUNW Rev B, JPL D-102272, 9 Nov 2023, text extracted from the PDF):
- The four `...CorrectionApplied = 'True'` flags are in the **geocoding** group: the spec says that group holds "Boolean flags indicating the corrections that have been applied while geocoding the pixel offsets layers ... i.e., wet and dry troposphere correction, slant range and azimuth ionosphere corrections". They concern **geolocation of the offsets, not the interferometric phase**.
- Spec, verbatim: "the estimated ionospheric phase screen is included as a layer in the product but **not applied by default**" ("Due to the variable quality of estimated phase screens in different modes").
- Spec, verbatim: "lookup tables for external phase corrections (e.g., solid Earth tides, ECMWF hydrostatic and wet delays). These phase corrections, when available, are **not applied to the data** but are available to users for application in post-processing workflows."
- Spec: "the current (secondary) and the immediately preceding in time L1_RSLC product (reference)": the secondary is the **later** acquisition. The LOS unit vector is "the vector from the target to the sensor".
- **The sign of the unwrapped phase is not stated** in the file attributes or in the spec text (no mention of "conjugate", "toward" or "away"). NISAR is left-looking.

## 4. Precompute results (`python precompute.py`, run on the real data, about 2 minutes, rc 0)

One line per event. **Failed steps: none for all five** (see section 8 for the OpenStreetMap step that reports "ok" while unavailable). Details and all reasons: `results/precompute_events.md`; full cached answers: `results/events/*.json`; console output: `results/precompute_output.txt`.

| Event | Type | Confidence | Alert | Verdict (short) |
|---|---|---|---|---|
| haouz-flood-2026-10-10 (Asni) | surface_change | low | yellow | 3→15 Oct, 12 d: mean coherence loss within 5 km 0.15, excess 0.12 over the frame mean (0.03): **borderline**, just above the 0.11 level (1 % of no-event circles), below 0.15; 2.69 km² lost more than 0.3 (0.04 km² in the previous pair). Not enough to say the surface changed. |
| haouz-soil-moisture | soil_moisture | low | none | 18 Oct: 0.174 m³/m³ (−0.027 vs the mean of 7 passes), **within the product's uncertainty (0.028)**. |
| gharb-soil-moisture | soil_moisture | low | none | 20 Oct: 0.219 m³/m³ (+0.025 vs the mean of 6 passes), **within the product's uncertainty (0.028)**. |
| ben-guerir-mine (status: **not validated**) | surface_change | low | none | latest pass 3→15 Oct vs the one before: loss 0.03 vs 0.04 frame mean (excess −0.01): no clear local change. Mine centroid, no polygon. |
| al-wahda-surroundings | slow_motion | low | none | "Uncorrected line-of-sight change, sign unverified": 20 Jun → 18 Oct (9 pairs, 120 d), 43.4 mm cumulative (noise per pair ± 29.8 mm); no rate (< 365 d); ionosphere screen subtracted (not validated), troposphere not corrected; chain crosses the 27 Jul–10 Aug data gap through 1 pair; reference in the point's connected component. |

Evidence steps: Open-Meteo worked in all five (rain context). **OpenStreetMap was "unavailable" in all five** (HTTP 406, section 8). USGS earthquakes: not called (precision "day" events).

## 5. Sign check

**Conclusion: UNDETERMINED. `NISAR_LOS_SIGN_VERIFIED` was not set.**

*What our Panama map shows:* nothing, because no Panama pair is on disk (section 1). The API call to `POST /ask` for Panama was therefore not made, and there are no displacement PNG layers to screenshot.

*What the published references show:*
- **USGS event page** `us6000u18k` (https://earthquake.usgs.gov/earthquakes/eventpage/us6000u18k): M 7.7 Mww, 2026-10-09 17:56:05.537 UTC, "10 km WSW of Pitaloza Arriba, Panama", 7.6069 N 80.7566 W, depth 10 km. Listed products: shakemap, finite-fault, moment-tensor, losspager, dyfi, ground-failure, oaf. **No InSAR product.**
- **USGS moment tensor** (Mww, centroid depth 13.5 km): nodal plane 1 strike 25.21°, dip 74.77°, rake −155.3°; nodal plane 2 strike 288.32°, dip 66.22°, rake −16.68°. Both rakes are close to 0° or ±180°, so the mechanism is **strike-slip**, not thrust.
- **No NASA/JPL/ASF/OPERA displacement map or NISAR interferogram of this earthquake was found** (web search). The Eos Landslide Blog post about the event (landslides, Sentinel-2) says nothing about InSAR. A published NISAR line-of-sight page exists for a **different** event, the M7.5 Venezuela earthquake (https://topex.ucsd.edu/VNZ_7.5/index.html); it could serve as a second reference if Venezuela pairs are downloaded (the plan has none).

*Why undetermined:*
1. We have no Panama data yet, and no published map of this event to compare with, so "same lobes, opposite colours" cannot be judged either way.
2. The product spec does not state the phase sign, so the convention cannot be read from the documentation.
3. The mechanism is strike-slip, so the expected pattern is **four lobes of alternating line-of-sight sign** with little vertical motion; horizontal motion flips sign between ascending and descending, vertical motion does not. This gives a *shape* test (quadrants across the fault) and an ascending-versus-descending consistency test, but the absolute polarity needs a published map or a forward model (for example Okada with the USGS finite-fault slip, or a GNSS displacement).
4. Note for the team: the synthetic Panama test data (`backend/tests/make_synthetic.py:83`) assume 25 cm uplift + 15 cm east, which is not what a strike-slip event produces; this is fine for testing logic but must not be used as evidence for the sign.

*Related, already measurable (not the ground-motion sign):* the code subtracts the ionosphere screen from the phase. Section 6 shows that **subtracting reduces the noise and adding increases it**, so the screen and the unwrapped phase share a sign convention. That does not tell whether positive phase means "toward" or "away" for the ground.

## 6. Noise report

**Phase B not run** (Ayman's `noise_report.py` is not available yet). Preliminary result with the *existing* code, whole frame, robust sigma of the unwrapped phase in cm (coherence ≥ 0.3, connected component ≠ 0), 12-day pairs, two pairs per frame (`results/noise_with_without_iono_preliminary.csv`):

| Frame | Pair | raw | minus iono (what the code does) | plus iono (wrong sign) | iono median (rad) |
|---|---|---|---|---|---|
| 44/17 A | 3→15 Oct | 3.12 | 2.21 | 4.84 | −7.6 |
| 44/17 A | 28 Aug→9 Sep | 6.36 | 1.83 | 13.69 | +14.1 |
| 23/73 D | 1→13 Oct | **96.36** | 2.62 | 196.95 | −28.3 |
| 23/73 D | 26 Aug→7 Sep | **0.00** | 6.13 | 7.21 | −24.5 |
| 95/71 D | 6→18 Oct | 11.57 | 1.92 | 22.21 | −6.6 |
| 95/71 D | 31 Aug→12 Sep | 5.97 | 2.98 | 9.88 | +16.2 |
| 116/19 A | 8→20 Oct | 2.65 | 2.65 | 2.26 | +5.1 |
| 116/19 A | 2→14 Sep | 5.92 | 2.50 | 9.69 | +7.3 |
| 95/73 D | 24 Sep→6 Oct | 24.9 | 3.89 | 52.06 | +36.0 |
| 95/73 D | 6→18 Oct | **55.3** | 3.24 | 108.01 | −62.2 |
| 44/18 A | 3→15 Oct | 3.61 | 3.39 | 5.88 | −5.6 |
| 44/18 A | 28 Aug→9 Sep | 8.69 | 1.53 | 15.31 | +19.1 |

- Subtracting the ionosphere screen gives the **lowest sigma in 10 of 12 pairs** (by a factor of 2 to 40; the worst raw cases are 96 cm and 55 cm). The two others: 116/19 8→20 Oct, where the screen is almost flat and all three variants are within 0.4 cm; and 23/73 26 Aug→7 Sep, a defective pair with flat raw phase (sigma 0.00). Adding the screen (wrong sign) is worse than the raw phase in 11 of 12 pairs, so the screen and the phase share a sign convention. The correction is needed on this dataset.
- Troposphere and solid-Earth tides: **not measured here** (the code does not use them; they are lookup cubes without a DEM-height pick in the existing code). That is for Ayman's script.
- 23/73 26 Aug→7 Sep: the unwrapped phase itself is flat (sigma 0.00) and the coherence is 0.03–0.09 over the whole area: a defective pair (the 7 Sep acquisition of track 23). The same applies to 7 Sep → 19 Sep.

## 7. GPS validation

**Phase B not run.** Needs Ayman's `validate_gps.py` and Panama (or another) pairs near a GNSS station; with the current data no station is known to be inside the Morocco frames.

## 8. Problems found in the code (nothing was fixed)

| # | File:line | Problem | Suggested fix |
|---|---|---|---|
| 1 | `backend/evidence.py:112` | The Overpass request sends **no User-Agent**. On the real run every event gets "OpenStreetMap unreachable (406 Client Error: Not Acceptable for url: https://overpass-api.de/api/interpreter)", so the exposure (buildings, roads, dams, quarries) is always empty. The calls at lines 38, 65, 88 also send none (they work today). | `requests.post(..., headers={"User-Agent": "<generic app name>/1.0"})`; use the same header for all outside calls. |
| 2 | `backend/agent.py:340` | `steps.run("what is exposed (OpenStreetMap)", ...)` records the step as `ok: true` because `evidence.exposure` returns `{"status": "unavailable"}` instead of raising. So "failed steps" is empty even when a source failed (all five events here). | In `Steps.run` or after the call, mark `ok: false` when the returned dict has `status == "unavailable"` (and keep the error text). |
| 3 | `backend/recipes/displacement.py:24-29` | The ionosphere screen is subtracted from every pair by default. The product spec says the screen is "not applied by default" because its quality varies. Section 6 shows the subtraction is necessary here (noise 96 → 2.6 cm), but the screen and the unwrapped phase are unwrapped separately, so they can disagree by whole fringes locally. Earlier check at the centres of the top automatic-discovery zones (2 km median, now disabled): zone 3 raw −3.6 cm, screen −71.5 cm, corrected +66.6 cm; zone 4 raw −65.8, screen +130.4, corrected −200.4; zone 6 raw −36.7, screen −92.2, corrected +46.1. The screen's own uncertainty layer says ±1–7 cm there. This is the likely reason the discoveries were not physical. | Do not change silently: record a decision (subtract / mask where the screen is extreme or its uncertainty is high / choose per pair by noise). Ayman's noise report is the right tool to decide. |
| 4 | `backend/tests/make_synthetic.py:83` (+ `events.py` Panama fixture) | Synthetic Panama = 25 cm uplift + 15 cm east. The real USGS mechanism is **strike-slip** (section 5). | Keep for logic tests, but document it, and build the real sign test on a quadrant (four-lobe) pattern. |
| 5 | repo root | An untracked file named `how --stat --oneline -1` (a typo from a git command) sits next to `README.md`. A `git add .` would commit it. | Delete it (it is not tracked). |
| 6 | `backend/recipes/damage.py` + data | Frame T023/F073 cannot give a usable baseline: its pairs that contain the 7 Sep 2026 acquisition are defective (flat phase / coherence 0.03–0.09). T095/F073 has only 2 pairs, so it can never have a baseline. The recipe handles both (not usable), but the surface-change answers therefore rest on **one geometry (044/017)** only. | Download more T095/F073 history and re-acquire or skip the 7 Sep T023 pairs when choosing baselines; nothing to fix in code. |
| 7 | `download_all.py status` (default plan) | With no `--plan`, it reports the Panama/Atlas plan (`plan_nisar.json`) and shows "part 1: 8 finished", although none of those 8 is a Panama pair (they are file-name matches with the Morocco plan). Confusing, not a bug in the data. | Say in the output which plan was read, or warn when a data folder was built from another plan. |

## 9. Anything surprising

- **Panama is not on disk at all**, although the pilot plan is "Panama co-seismic + Al Wahda + soil moisture": the data folder was built from the Morocco plan only. The sign check, the Panama API call and the GPS check all depend on it (13.3 GB for the 8 co-seismic pairs).
- The 8 co-seismic Panama pairs in `plan_nisar.json` are on **four tracks** (4, 40, 76, 141), not only 141 and 4.
- **The raw phase is dominated by the ionosphere** in this period: whole-frame sigma up to 96 cm (23/73, 1→13 Oct) and 55 cm (95/73, 6→18 Oct) before the screen is subtracted, 2–6 cm after. The screen medians range from −62 to +36 rad.
- NISAR is **left-looking**; the code already handles this (`recipes/decompose.py:20-22`).
- In this file the `...CorrectionApplied = 'True'` flags look reassuring, but they only describe geolocation of the pixel offsets (spec text above). No tropospheric or tidal correction is applied to the phase, and the code does not apply them either.
- The 2026-07-27 → 08-10 data gap is crossed by exactly **one** bridging pair in each Al Wahda series, and in both the reference shares the point's connected component.
- Both geometries at Al Wahda disagree in sign (+43.4 mm for 95/71, −20.0 mm for 116/19) with 29–30 mm noise per pair: the answer is noise, as the verdict says.
- The `.h5` raw files were all kept (125 GB for GUNW), so layers can be re-extracted without downloading again.
- Open-Meteo rain: 37.9 mm over the Haouz flood window (max 13.4 mm on 2026-10-09), 59.7 mm in the 30 days before the Haouz soil-moisture date.
