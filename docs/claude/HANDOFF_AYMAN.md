# Handoff: Ayman's science and API work (updated 14 Nov 2026, 17:45)

Branch `ayman/science` (origin/main merged in). Gates: `test_all.py` 196/196, `test_science.py` 101/101 (~3 min),
`tools/frontend_contract` 83/83 routes + 2/2 final cases (also with `NISAR_DEMO=1`). Not yet run on real NISAR data
(the GUNW pairs are on Anass's machine A).

## Done, and where
| what | files | commit |
|---|---|---|
| Repo consolidation: PRs #1 and #2 merged, frontend imported with `git subtree` | `frontend/`, `docs/FRONTEND_INTEGRATION.md` | 8eb7fe6, 36b23cb, fda2e37 |
| CaseStudy contract, models, `/api/cases` routes, 4 draft fixtures | `docs/CASE_CONTRACT.md`, `science/case_models.py`, `case_store.py`, `backend/cases/*.json`, `api_v2.py` | 5dddc75 |
| Contract check of `/api/cases`; `NISAR_DEMO=1` refuses drafts | `tools/frontend_contract/`, `tests/dump_cases_contract.py` | d40973b |
| Okada (1985) in numpy, checked against Table 2 | `science/okada.py` | 17666c5 |
| USGS nodal planes (cached), uniform-slip inversion, Jacobian + bootstrap σ | `science/usgs.py`, `science/invert_fault.py` | 40a6c8d |
| Panama runner: GUNW → tracks → fit → findings + data/model/residual PNG | `science/panama_fault.py` | 49a01bd |
| Exposure: people, buildings, area with a spread | `science/exposure.py`, `science/exposure_run.py` | 2ed9295 |
| Sign test against the USGS finite-fault model; variance reduction per track | `science/ffm_sign.py` | 700a32b |
| Case assembly, figure route, input formats; a map + full timeline per case | `science/cases.py`, `science/case_layers.py` | 6a5b4b6, d07911d |
| Sign decision rule, stage timing, linear ramps | `science/sign_decision.py` | 0409bf2 |
| Noise covariance from pre-event pairs, generalised least squares, Monte Carlo σ | `science/noise_cov.py` | e6f44ef |
| Panama sign verdict (`sign_check`) → a limit; a sign opposite to the run's keeps the case a draft | `science/cases.py:sign_part` | 1a7a4c7 |
| One offset per connected component (inversion, sign test, noise model); `flipped` keeps the noise model | `science/panama_fault.py:component_blocks`, `invert_fault.ramp_design` | 735da2c |
| api_v2: no Measurement without its σ, tracks / acquisitions / period from the facts, no layer without its PNG, no English error in FR / AR, Overpass timeout 90 s | `api_v2.py`, `evidence.py` | 276a701 |
| Ionosphere case: before / after noise chart per NISAR pair from Anass's CSV | `science/iono_chart.py`, `science/cases.py:iono_chart_part` | fad19c3 |
| Wavelength λ = c / centerFrequency (proposal, branch `ayman/wavelength`) | `recipes/wavelength.py`, `recipes/displacement.py` | c41e315 |

## Decisions
- **Case contract:** CASE_CONTRACT.md is the source (pydantic in the backend, zod in the frontend). Dates ISO UTC;
  `exposure.source` is `{name, url}`; units `Mw`, `people`, `count`, `deg` added. `final` only with no placeholder,
  ≥ 1 map with a layer, a full timeline, and a non-zero σ on every finding.
- **Agreement rule:** S = sqrt(σn² + σr²) (1-sigma). `agree` if |n − r| ≤ 2S, `partial` if ≤ 4S, else `disagree`;
  `no_reference` without a reference. Recomputed on both sides, never typed by hand.
- **Sign decision rule:** +1 needs finite-fault k > 0 at > 3σ on ≥ 3 tracks with none < 0 at 3σ, AND VR(+1) − VR(−1)
  ≥ 0.10, AND best plane = left-lateral 288/66/−17 (±15° strike/dip, ±30° rake). −1 mirrored, else "undecided".
- **Okada / inversion:** ν = 0.25, μ = 30 GPa, Mw = 2/3 (log10 M0 − 9.1). Strike/dip/rake fixed per nodal plane, lower
  RMS wins. Bounds: centre ±100 km, length 5–400 km, width 3–80 km, top 0–40 km, slip 0.01–20 m; 6 starts. Ramp per
  track = one offset per connected component (≥ 20 blocks, largest always kept) + east/north gradient, solved
  linearly. Coherence ≥ 0.3, ~1500 block means per track. Stable only if σ(Mw) ≤ 0.15, no parameter at a bound,
  ≥ 80 % of the bootstrap fits converge and VR ≥ 0.5. USGS reference Mww 7.7 ± 0.1.
- **Finite-fault model:** 295/60/−16, 55 × 33.6 km, centre 7.54 N 80.769 W (surface projection), top depth 0 km.
- **Exposure:** earthquake zone |LOS| > 10 cm, spread from the threshold at ±1σ; flood zone = mask ±1 pixel. WorldPop
  100 m (or GHSL in `data/aux/pop/`); OSM buildings in 0.25° tiles; cached in `data/aux/`.
- **api_v2 `uncertainty: 0`:** only through `value_only()` = a noise floor (it is a σ), an exact count, or an external
  reference given without one; the frontend then prints the value alone.
- **Left as is (team decision, 14 Nov):** the 4 Moroccan sites stay out of `/api/library` (kind enum has no "site");
  the decimal point in `agent.template` prose stays (numbers passed as params are formatted by the frontend).

## Known limits
- Uniform slip on one rectangle; the model error (μ, uniform slip) dominates the Mw σ and is not quantified.
- One mean line-of-sight vector per track; the incidence angle varies across the swath.
- The sign test depends on the finite-fault centre: a fault 16 km away gave "inconclusive" in the tests.
- Vertical / east-west metrics are not sent until `decompose.combine` returns its σ (the old ×1.5 factor was removed).
- Noise chart: no error bar (correlated pixels); the current CSV is preliminary and a limit says so.
- `recipes/decompose.py:los_vector` swallows exceptions; `watch.py:82` sends no User-Agent (Anass's files).

## Open tasks
1. **Anass:** merge `ayman/wavelength` (merges cleanly into main: test_wavelength 6/6, test_all 196/196); store
   `centerFrequency` in `radar_geometry.npz`. In `decompose.combine`, return `sigma_east` / `sigma_up` =
   σ_los · sqrt(diag((MᵀM)⁻¹)) with its 2×2 matrix M (api_v2 already reads them).
2. **Anass, real Panama run:** `NISAR_LOS_SIGN=1 python -m science.panama_fault --boot 5` (sign verdict, component
   offsets and noise model on real data; needs the `plan_validation.json` part 2 pre-event pairs).
3. **Sunday: "Use of AI" README section** (`README.md`).

## Inputs still missing for final cases
- Anass: `cases/out/panama-2026*.json` (panama_fault, exposure_run); `results/haouz-flood-2026/findings.json` with
  `products`, `date` and a backscatter-change raster, plus `flood_mask.tif`; `results/venezuela-2026/findings.json`;
  the final `results/noise_with_without_iono_*.csv` (preliminary one on `results/real-data-checks`).
- Houssam: `results/gps/gps_none/` and `results/gps/gps_iono/`.
- Venezuela mainshock: `--venezuela-event us6000t7zp` (USGS Mww 7.5, 2026-06-24 22:05:04 UTC, 10.5955 N 67.2205 W;
  a Mww 7.2 `us6000t7zc` came 32 s earlier near San Felipe). `python -m science.cases --dry-run` lists what is missing.
- Figures: `cases.py` renders them into `backend/cases/figures/<id>/` (Anass's machine, committed); the API serves
  them from there without any NISAR data (checked: 200 image/png, 404 for a missing file or a traversal).
