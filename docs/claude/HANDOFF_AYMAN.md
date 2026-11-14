# Handoff: Ayman's science and API work (session of 14 Nov 2026)

Branch `ayman/science` (origin/main merged in). Gates on 14 Nov: `test_all.py` 196/196, `test_science.py` 84/84
(~3 min), `tools/frontend_contract` 85/85 incl. two final cases built by the tests. Not yet run on real NISAR data
(the GUNW pairs are on Anass's machine A).

## Done, and where
| what | files | commit |
|---|---|---|
| Repo consolidation: PRs #1 and #2 merged, frontend imported with `git subtree` | `frontend/`, `docs/FRONTEND_INTEGRATION.md` | 8eb7fe6, 36b23cb, fda2e37 |
| CaseStudy contract, models, `/api/cases` routes, 4 draft fixtures | `docs/CASE_CONTRACT.md`, `backend/science/case_models.py`, `case_store.py`, `backend/cases/*.json`, `backend/api_v2.py` | 5dddc75 |
| Contract check of `/api/cases`: frontend schema + strict rules; `NISAR_DEMO=1` refuses drafts | `tools/frontend_contract/validate.ts`, `case_contract.ts`, `backend/tests/dump_cases_contract.py` | d40973b |
| Okada (1985) in numpy, checked against Table 2 | `backend/science/okada.py` | 17666c5 |
| USGS nodal planes (cached), uniform-slip inversion, Jacobian + bootstrap σ | `science/usgs.py`, `science/invert_fault.py` | 40a6c8d |
| Panama runner: GUNW → tracks → fit → findings + data/model/residual PNG | `science/panama_fault.py` | 49a01bd |
| Exposure: people, buildings, area with a spread | `science/exposure.py`, `science/exposure_run.py` | 2ed9295 |
| Sign test against the USGS finite-fault model; variance reduction per track | `science/ffm_sign.py` | 700a32b |
| Case assembly, figure route, input formats | `science/cases.py`, `case_store.figure_path`, CASE_CONTRACT.md "Inputs" | 6a5b4b6 |
| A map with a layer + full timeline for every case | `science/case_layers.py` | d07911d |
| Sign decision rule, largest connected component, stage timing, linear ramps | `science/sign_decision.py` | 0409bf2 |
| Noise covariance from pre-event pairs, generalised least squares, Monte Carlo σ | `science/noise_cov.py` | e6f44ef |
| Wavelength λ = c / centerFrequency (proposal for Anass, branch `ayman/wavelength`) | `recipes/wavelength.py`, `recipes/displacement.py`, `tests/test_wavelength.py` | c41e315 |

## Decisions
- **Case contract:** CASE_CONTRACT.md is the source (pydantic in the backend, zod in the frontend). Dates are ISO UTC;
  `exposure.source` is `{name, url}`; new units `Mw`, `people`, `count`, `deg`. A case is `final` only with no
  placeholder, ≥ 1 map with a layer, a full timeline, and a non-zero σ on every finding.
- **Agreement rule:** S = sqrt(σn² + σr²) (1-sigma). `agree` if |n − r| ≤ 2S, `partial` if ≤ 4S, else `disagree`;
  `no_reference` without a reference. Recomputed on both sides, never typed by hand.
- **Sign decision rule:** +1 needs finite-fault k > 0 at > 3σ on ≥ 3 tracks with none < 0 at 3σ, AND VR(+1) − VR(−1)
  ≥ 0.10, AND best plane = left-lateral 288/66/−17 (±15° strike/dip, ±30° rake). −1 by the mirrored rule, otherwise
  "undecided". Written to `cases/out/<case>_sign.json`.
- **Okada / inversion:** ν = 0.25. Strike, dip and rake fixed per nodal plane; the lower RMS wins. Bounds: top-edge
  centre ±100 km along and across, length 5–400 km, width 3–80 km, top depth 0–40 km, slip 0.01–20 m. Ramps solved
  linearly; 6 starts. μ = 30 GPa, Mw = 2/3 (log10 M0 − 9.1). Coherence ≥ 0.3, largest connected component, ~1500
  block means per track, ionospheric correction requested. Stable only if σ(Mw) ≤ 0.15, no parameter at a bound,
  ≥ 80 % of the bootstrap fits converge and VR ≥ 0.5; otherwise "magnitude not estimated" with the reason. USGS
  reference Mww 7.7 ± 0.1.
- **Finite-fault model:** 295/60/−16, 55 × 33.6 km, centre 7.54 N 80.769 W (surface projection of the plane centre),
  top depth assumed 0 km (`--ffm-top-depth`).
- **Exposure:** earthquake zone |LOS| > 10 cm, spread from the threshold at ±1σ of the noise; flood zone = mask, ±1-pixel
  edge. WorldPop 100 m (or a GHSL raster in `data/aux/pop/`); OSM Overpass buildings in 0.25° tiles; all cached in
  `data/aux/`.

## Known limits
- Uniform slip on one rectangle. The Mw σ from noise is small at Mw 7.7; the model error (μ, uniform slip) dominates
  and is not quantified.
- One mean line-of-sight vector per track (`decompose.los_vector`); the incidence angle varies across the swath.
- The finite-fault sign test depends on the given centre being right: a fault 16 km away gave "inconclusive" in the
  tests.
- `recipes/decompose.py:los_vector` swallows exceptions silently. `watch.py:82` sends no User-Agent. Both are
  Anass's files.
- Downloads don't keep `centerFrequency`: without the raw `.h5`, the wavelength falls back to the config value.

## Open tasks
1. **Wavelength from centerFrequency** (λ = c/f, config fallback with a warning). Done on `ayman/wavelength`; waiting
   for Anass's review and merge (`recipes/displacement.py` is his). Follow-up: store `centerFrequency` in
   `radar_geometry.npz` (`download_all.py`).
2. **Connected components:** largest one kept per track. Done in `science/panama_fault.py:largest_component`
   (0409bf2). A per-component offset is not done.
3. **ffm_sign JSON and decision rule:** done in `science/sign_decision.py` → `cases/out/panama-2026_sign.json`.
   Needs Anass's real run: `NISAR_LOS_SIGN=1 python -m science.panama_fault --boot 5`.
4. **api_v2 fixes from Houssam's notes** (open, `backend/api_v2.py`): numbers as Measurement params; no
   `uncertainty: 0`; fill `tracks`; omit layers without a PNG; list the precomputed library events; User-Agent on
   Overpass (`evidence.py` already has one: check where Houssam saw it missing).
5. **Ionosphere case:** a before/after chart per pair from Anass's noise CSV (open, `science/cases.py` `build_iono`,
   input `results/noise_with_without_iono_*.csv`).
6. **Noise covariance from the Panama pre-event pairs:** done in `science/noise_cov.py` (e6f44ef), on by default
   (`--no-noise-cov`). Needs the `plan_validation.json` part 2 pairs on machine A.
7. **Sunday: "Use of AI" README section** (open, `README.md`).

## Inputs still missing for final cases
- Anass: `cases/out/panama-2026*.json` (panama_fault, exposure_run); `results/haouz-flood-2026/findings.json` with
  `products`, `date` and a backscatter-change raster, plus `flood_mask.tif`; `results/venezuela-2026/findings.json`.
- Houssam: `results/gps/gps_none/` and `results/gps/gps_iono/`.
- Ayman: the USGS id of the Venezuela mainshock (`--venezuela-event`). `python -m science.cases --dry-run` lists what
  is still missing.
