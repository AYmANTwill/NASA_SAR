# NISAR Pulse — backend

Every feature of the app, working: questions in FR/EN/AR, 7 analysis recipes, uncertainty and
confidence, independent evidence, automatic discovery, event library, watch + alerts, change
classifier (ML), map layers, and an HTTP API for the interface. 196/196 end-to-end checks pass on
synthetic NISAR-shaped data (`python tests/test_all.py`).

## Folder layout
```
NASA_SAR\
   download_all.py, plan_nisar.json
   data\          written by download_all.py or unzipped from the shared data zip (GUNW\, SME2\, manifest.csv)
   backend\       this folder
```
The backend reads `..\data` by default. Elsewhere: set `NISAR_DATA`.

## Step by step

**1. Install (once)**
```
cd NASA_SAR\backend
python -m pip install -r requirements.txt
```

**2. Check everything works (no data, no internet needed)**
```
python tests\test_all.py
```
Expect `196/196 checks passed`. It builds synthetic data in a temp folder; your real data is untouched.

**3. Start the API (works even with no data: mock answers)**
```
python -m uvicorn api:app --port 8000
```
Open http://localhost:8000/docs to try every endpoint. The interface contract is in `docs/API_CONTRACT.md`.

**4. When the pilot (part 1) has finished downloading**
```
python precompute.py
```
Computes the Panama, Venezuela, Al Wahda, Ben Guerir and Gharb answers plus the discoveries, and
stores them in `cache\`. Use `--no-exposure` without internet. Restart the API: `/health` now shows
the real products and mock mode turns off by itself.

**5. Calibrate on the first real files (15 minutes, important)**
- Layer names were checked on real part-1 files (11 Nov 2026): they match.
- Sign check: `python sign_check.py --data D:\nisar_validation` renders the Panama co-seismic maps and links the USGS
  mechanism (strike-slip: opposite lobes, not an uplift). The documented convention (ARIA-tools, MintPy prep_nisar) gives
  `NISAR_LOS_SIGN=1`; a human sets `NISAR_LOS_SIGN_VERIFIED=1` after the check, then recomputes. See the main README,
  section "Validation", for every real-data command and its output.
- Soil moisture reads `science/LSAR/SME2/grids/soilMoisture` (checked on real files).

## Optional keys (environment variables)
| variable | what for | how to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | the agent classifies unusual questions and writes Arabic with an LLM; without it, rules + templates in FR/EN/AR are used (everything still works) | console.anthropic.com (paid per use) |
| `FIRMS_MAP_KEY` | fire evidence for the deforestation answer | free, firms.modaps.eosdis.nasa.gov/api/map_key |
| `NISAR_OFFLINE=1` | demo mode: no internet calls at all | — |
| `NISAR_MOCK=1` | force fake answers (interface development) | — |
| `NISAR_LOS_SIGN_VERIFIED=1` | say that the LOS sign was checked on real data (STATUS H4). While unset, every signed line-of-sight answer says "sign unverified", has confidence low and no alert | after the Panama check |
| `NISAR_DISCOVERIES_ENABLED=1` | turn the automatic discoveries back on. Off by default: the zones were not physical. `/discoveries` then returns an empty list and the reason | — |
| `NISAR_DISCOVERIES_MODE=consistent` | the SAFE discoveries mode: a zone must be in >= 3 independent pairs of one geometry, same sign, not concentrated in one pair (see `discoveries.py`). Off when unset | — |
| `NISAR_CORRECTIONS` | phase corrections: `iono` (default, the previous behaviour), any of `iono,tropo,tide`, or `none`. Turn on only what `noise_report.py` recommends | — |
| `NISAR_DEM` / `NISAR_CORRECTION_HEIGHT_M` | terrain height for the troposphere/tide cubes: `glo30` (public Copernicus tiles, default when online), a local DEM path, or `none` (then the constant, default 0 m) | — |
| `NISAR_IONO_UNC_MAX_RAD` | ionosphere pixels whose screen uncertainty is above this are masked (default 1.0 rad) | — |
| `NISAR_FLAT_PHASE_SIGMA_RAD` / `NISAR_MIN_PAIR_COHERENCE` | pair quality filter: flat phase below 0.001 rad, median coherence below 0.15 = rejected and listed | — |

PowerShell: `$env:FIRMS_MAP_KEY="..."` before `uvicorn`.

## What each file does
| file | role |
|---|---|
| `api.py` | HTTP API (FastAPI) |
| `agent.py` | question → type → recipe → evidence → verdict, confidence, alert level |
| `recipes/displacement.py` | sudden motion: phase → cm, masks, stable reference, profile |
| `recipes/timeseries.py` | slow motion: small-baseline inversion, velocity, acceleration, velocity maps |
| `recipes/decompose.py` | ascending + descending → vertical and east-west |
| `recipes/damage.py` | surface change = coherence loss between a before pair and the pair across an event, in a 5 km circle, against a baseline pair and the frame background (not a damage measure) |
| `recipes/backscatter.py` | flood and deforestation from GCOV |
| `recipes/soil_moisture.py` | NISAR SME2 soil moisture |
| `recipes/offsets.py` | large displacements from GOFF |
| `uncertainty.py` | noise floor and confidence rules |
| `evidence.py` | USGS, Open-Meteo, FIRMS, OpenStreetMap |
| `discoveries.py` | scans every geometry, lists moving zones |
| `events.py` / `precompute.py` | event library, computed in advance |
| `watch.py` | watches, next passes, alerts FR/EN/AR |
| `ml_classifier.py` / `train_classifier.py` | change classifier (XGBoost) |
| `catalog.py` | index of downloaded products |
| `mock.py` | fake answers for the interface |
| `recipes/corrections.py` | optional ionosphere / troposphere / solid-earth-tide corrections (`NISAR_CORRECTIONS`) |
| `quality.py` | pair quality filter (flat phase, median coherence < 0.15) |
| `noise_report.py` | noise floor per correction set → `results_out/noise_report.{json,md}` |
| `validate_gps.py` | NISAR vs NGL GNSS stations → `results_out/gps_<STA>.{json,md,png}` |
| `sign_check.py` | helper for the line-of-sight sign decision → `results_out/sign_check.{md,png}` |

## Data each feature needs
| feature | works with the pilot (part 1)? |
|---|---|
| Panama earthquake (sudden motion, ascending + descending) | yes |
| Damage proxy | needs a pre-event pair (parts 2–5) |
| Al Wahda slow motion | 1 pair per geometry in the pilot = a 12-day change, low confidence; real trend after parts 2–5 |
| Soil moisture | yes (15 SME2 files) |
| Discoveries | yes on the pilot pairs; velocity maps after parts 2–5 |
| Flood / deforestation / classifier | needs GCOV files (not in the download plan yet) |
| Watch, next passes | yes |
