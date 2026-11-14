# NISAR Pulse — backend

Every feature of the app, working: questions in FR/EN/AR, 7 analysis recipes, uncertainty and
confidence, independent evidence, automatic discovery, event library, watch + alerts, change
classifier (ML), map layers, and an HTTP API for the interface. 30/30 end-to-end checks pass on
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
Expect `30/30 checks passed`. It builds synthetic data in a temp folder; your real data is untouched.

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
- Sign check: open `/events/panama-2026` and compare the displacement map with NASA's / USGS's published
  map of the 9 October earthquake. If the colours are reversed, set `NISAR_LOS_SIGN=-1` and recompute.
- Soil moisture reads `science/LSAR/SME2/grids/soilMoisture` (checked on real files).

## Optional keys (environment variables)
| variable | what for | how to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | the agent classifies unusual questions and writes Arabic with an LLM; without it, rules + templates in FR/EN/AR are used (everything still works) | console.anthropic.com (paid per use) |
| `FIRMS_MAP_KEY` | fire evidence for the deforestation answer | free, firms.modaps.eosdis.nasa.gov/api/map_key |
| `NISAR_OFFLINE=1` | demo mode: no internet calls at all | — |
| `NISAR_MOCK=1` | force fake answers (interface development) | — |

PowerShell: `$env:FIRMS_MAP_KEY="..."` before `uvicorn`.

## What each file does
| file | role |
|---|---|
| `api.py` | HTTP API (FastAPI) |
| `agent.py` | question → type → recipe → evidence → verdict, confidence, alert level |
| `recipes/displacement.py` | sudden motion: phase → cm, masks, stable reference, profile |
| `recipes/timeseries.py` | slow motion: small-baseline inversion, velocity, acceleration, velocity maps |
| `recipes/decompose.py` | ascending + descending → vertical and east-west |
| `recipes/damage.py` | surface change = coherence loss between a before pair and the pair across an event (not a damage measure) |
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
