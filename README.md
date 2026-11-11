# NISAR Pulse — the radar investigator

**Team The SAR · NASA Space Apps Challenge 2026 · challenge "Dancing with the SARs"**

Point at any place on Earth, ask a question in French, English or Arabic — *"Is the Al Wahda dam
deforming since June?"*, *"Where did the ground move after the Panama earthquake?"* — and NISAR Pulse
answers with what the NASA-ISRO **NISAR** radar satellite measured: a map, a curve, a one-sentence
verdict, an uncertainty, independent evidence, and what the radar cannot tell. Then it keeps
watching the place at every new NISAR pass (every 12 days) and raises an alert if the trend changes.

Full project description: [`docs/NISAR_Pulse_v2_project.docx`](docs/NISAR_Pulse_v2_project.docx)

## What is in this repository
| path | what it is |
|---|---|
| `download_all.py`, `plan_nisar.json` | downloads NISAR products from NASA's ASF archive, split into 5 parts, resumable |
| `backend/` | all the analysis code and the HTTP API — details in [`backend/README.md`](backend/README.md) |
| `docs/API_CONTRACT.md` | the API the interface talks to |
| `docs/inventaire_GUNW_Maroc.csv` | the 429 NISAR interferograms available over Morocco (17 Jun – 21 Oct 2026) |
| `tools/make_data_zip.py` | packs the processed data into one zip to share with the team |

The data itself is **not** in git (several GB). Get it from the team's shared zip, or download it (step 3).

## Step-by-step guide

### 1. Get the code
```
git clone https://github.com/AYmANTwill/NASA_SAR.git
cd NASA_SAR
```

### 2. Install (Python 3.10+)
```
cd backend
python -m pip install -r requirements.txt
cd ..
```

### 3. Get the data — choose A or B
**A. From the team zip (fastest).** Unzip the shared data zip into a `data` folder at the repo root so
that `NASA_SAR\data\GUNW` and `NASA_SAR\data\SME2` exist (not `data\data\GUNW`). Check:
```
python download_all.py status
```
Part 1 must show 100 %. If it shows 0 %, the folder is in the wrong place.

**B. Download it yourself.** Create a free NASA Earthdata account (urs.earthdata.nasa.gov), generate a
token (profile → *Generate Token*), then:
```
python download_all.py run --part 1
```
The script asks for the token once and stores it in `.earthdata_token` (ignored by git — never commit it).
You can also set it in the shell: `$env:EARTHDATA_TOKEN="..."` (PowerShell) or `export EARTHDATA_TOKEN=...`.

| part | size to download | content |
|---|---|---|
| 1 (pilot) | 19.9 GB | Panama earthquake pairs, Al Wahda (1 pair per direction), 15 soil-moisture passes |
| 2 – 5 | ~78 GB each | the Morocco atlas (11 frames, ascending + descending), Venezuela, more soil moisture |

Each file is reduced to the layers the app uses and the raw file is deleted, so only a fraction stays on
disk. Ctrl+C stops cleanly; running the same command again resumes exactly where it stopped and never
downloads a finished file twice. Split parts 2–5 between team members, ideally on different internet
connections, then merge everyone's `data\GUNW` and `data\SME2` folders (names never collide).

### 4. Check that everything works
```
cd backend
python tests\test_all.py
```
Expected: `30/30 checks passed` (runs on synthetic data, no internet needed).

### 5. Compute the demo answers, then start the API
```
python precompute.py
python -m uvicorn api:app --port 8000
```
Open http://localhost:8000/docs and try `/health`, `/events/panama-2026`, `/ask`.
Without internet: `python precompute.py --no-exposure` and set `NISAR_OFFLINE=1`.

### 6. Build the interface
Read [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md). Every data endpoint accepts `?mock=true` and returns a
realistic fake answer, so screens can be built before any data is processed. Map layers are PNG images
with bounds: `L.imageOverlay(layer.url, layer.bounds)` in Leaflet.

### 7. Share new data with the team
```
python tools\make_data_zip.py
```
Creates `NISAR_Pulse_data.zip` (ignored by git) to send through a drive or a USB key.

## Before the demo
- [ ] `python tests\test_all.py` → 30/30 on the demo laptop
- [ ] Sign check: compare the `/events/panama-2026` map with NASA's or USGS's published map of the
      9 October 2026 earthquake; if the colours are reversed, set `NISAR_LOS_SIGN=-1` and rerun `precompute.py`
- [ ] `python precompute.py` after the last data merge
- [ ] Offline rehearsal with `NISAR_OFFLINE=1`
- [ ] Optional keys: `FIRMS_MAP_KEY` (free, fire evidence), `ANTHROPIC_API_KEY` (paid, smarter questions and Arabic phrasing)

## Data sources
NISAR L-band products (GUNW, SME2; GCOV and GOFF supported) from the
[ASF DAAC](https://asf.alaska.edu/); USGS earthquake catalogue; Open-Meteo ERA5 archive; NASA FIRMS;
OpenStreetMap (Overpass).
