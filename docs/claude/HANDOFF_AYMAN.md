# Handoff: Ayman's science and API work (session of 14 Nov 2026)

Branch `ayman/science` (origin/main merged in). Gates on 14 Nov:
- `python backend/tests/test_all.py`: 196/196;
- `python backend/tests/test_science.py`: 84/84 (about 3 min);
- `tools/frontend_contract` against `frontend/src/api/contract.ts`: 85/85, including two complete final cases built by
  the tests.
Nothing below has run on real NISAR data yet: the GUNW pairs are on Anass's machine A.

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
- **Case contract:** CASE_CONTRACT.md is the source. The backend validates with pydantic, the frontend with zod.
  - Dates are ISO UTC. `exposure.source` is `{name, url}`.
  - New units: `Mw`, `people`, `count`, `deg`.
  - A case is `final` only when `placeholders` is empty, it has at least one map with a layer and a full timeline, and
    every finding has a non-zero σ.
- **Agreement rule:** S = sqrt(σn² + σr²) with 1-sigma values. `agree` if |n − r| ≤ 2S, `partial` if ≤ 4S, otherwise
  `disagree`; `no_reference` if there is no reference. It is recomputed on both sides, never typed by hand.
- **Sign decision rule:**
  - +1 needs all three: USGS finite-fault model k > 0 at > 3σ on ≥ 3 tracks with none < 0 at 3σ; variance reduction(+1)
    − VR(−1) ≥ 0.10; and the best plane is the left-lateral 288/66/−17 (within ±15° in strike and dip, ±30° in rake).
  - −1 follows the mirrored rule; anything else is "undecided".
  - Written to `cases/out/<case>_sign.json`.
- **Okada / inversion settings:**
  - Elastic half-space with ν = 0.25. Strike, dip and rake fixed from each nodal plane in turn; the lower RMS wins.
  - Free parameters and bounds: along and across position of the top-edge centre ±100 km, length 5–400 km, width
    3–80 km, top depth 0–40 km, slip 0.01–20 m. The per-track ramp is solved linearly.
  - 6 starting points. μ = 30 GPa and Mw = 2/3 (log10 M0 − 9.1).
  - Masks: coherence ≥ 0.3 and the largest connected component per track. About 1500 block means per track. The
    ionospheric correction is requested.
  - Stable only if: bootstrap σ(Mw) ≤ 0.15, no parameter at a bound, ≥ 80 % of the bootstrap fits converge, VR ≥ 0.5.
    Otherwise the case says "magnitude not estimated" with the reason.
  - USGS reference: Mww 7.7 with σ 0.1.
- **Finite-fault model:** strike 295°, dip 60°, rake −16°, 55 × 33.6 km, centre at 7.54 N, 80.769 W, taken as the
  surface projection of the fault-plane centre. The top depth is assumed to be 0 km (`--ffm-top-depth`).
- **Exposure:**
  - Earthquake zone |LOS| > 10 cm; the spread comes from the threshold at ±1σ of the noise. Flood zone = the mask, with
    a ±1-pixel edge.
  - Population: WorldPop 100 m by default, or a GHSL raster placed in `data/aux/pop/`. Buildings: OSM Overpass in 0.25°
    tiles. Every download is cached under `data/aux/`.

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
4. **api_v2 fixes from Houssam's notes** (open, `backend/api_v2.py`):
   - numbers as Measurement params;
   - no `uncertainty: 0`;
   - fill `tracks`;
   - omit layers without a PNG;
   - list the precomputed library events;
   - User-Agent on Overpass (`evidence.py` already has one: check where Houssam saw it missing).
5. **Ionosphere case:** a before/after chart per pair from Anass's noise CSV (open, `science/cases.py` `build_iono`,
   input `results/noise_with_without_iono_*.csv`).
6. **Noise covariance from the Panama pre-event pairs:** done in `science/noise_cov.py` (e6f44ef), on by default
   (`--no-noise-cov`). Needs the `plan_validation.json` part 2 pairs on machine A.
7. **Sunday: "Use of AI" README section** (open, `README.md`).

## Inputs still missing for final cases
- Anass:
  - `cases/out/panama-2026*.json` (panama_fault, exposure_run);
  - `results/haouz-flood-2026/findings.json` with `products`, `date` and a backscatter-change raster, plus
    `flood_mask.tif`;
  - `results/venezuela-2026/findings.json`.
- Houssam: `results/gps/gps_none/` and `results/gps/gps_iono/`.
- Ayman: the USGS id of the Venezuela mainshock (`--venezuela-event`). Then run
  `python -m science.cases --dry-run` to see what is still missing.
