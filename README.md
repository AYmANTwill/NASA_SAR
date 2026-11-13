# NISAR Pulse — the radar investigator

**Team The SAR · NASA Space Apps Challenge 2026 · challenge "Dancing with the SARs"**

Point at any place on Earth, ask a question in French, English or Arabic — *"Is the Al Wahda dam
deforming since June?"*, *"Where did the ground move after the Panama earthquake?"* — and NISAR Pulse
answers with what the NASA-ISRO **NISAR** radar satellite measured: a map, a curve, a one-sentence
verdict, an uncertainty, independent evidence, and what the radar cannot tell. It then keeps watching
the place at every new NISAR pass (every 12 days) and raises an alert if the trend changes.

Full project description: [`docs/NISAR_Pulse_v2_project.docx`](docs/NISAR_Pulse_v2_project.docx)

## Repository map
| path | what it is |
|---|---|
| **`download_all.py`** | **the download script** (repo root) — gets the NISAR data from NASA, see below |
| `plan_nisar.json` | the list of files to download, split into 5 parts (must stay next to `download_all.py`) |
| `backend/` | all the analysis code and the HTTP API — [`backend/README.md`](backend/README.md) |
| `docs/API_CONTRACT.md` | the API the interface talks to |
| `docs/inventaire_GUNW_Maroc.csv` | the 429 NISAR interferograms available over Morocco (17 Jun – 21 Oct 2026) |
| `docs/NISAR_Pulse_v2_project.docx` | the project document |
| `tools/make_data_zip.py` | packs the processed data into one zip to share with the team |
| `data/` (created by the script, not in git) | the downloaded, processed data |

---

## The download script — `download_all.py`

### What it does
1. Reads `plan_nisar.json`: **345 NISAR files** chosen and checked on NASA's archive (ASF DAAC) on
   11 Nov 2026, split into **5 parts**.
2. Downloads each file from NASA with the team's Earthdata key (already inside the script — nothing to configure).
3. Keeps only the layers the app uses (phase, coherence, unwrapping quality, ionosphere, viewing
   geometry), saved as compressed GeoTIFFs, then **deletes the raw file** to save disk space.
4. Marks each finished file with a `_DONE` flag, so nothing is ever downloaded twice.

### The 5 parts
| part | files | to download | content |
|---|---|---|---|
| **1 (pilot)** | 25 | 19.9 GB | the 8 pairs around the Panama M7.7 earthquake (9 Oct 2026), Al Wahda dam (1 pair ascending + 1 descending), 15 soil-moisture passes over northern Morocco |
| 2 | 79 | 77.7 GB | Morocco atlas, Panama and Venezuela pre-event pairs, soil moisture (balanced mix) |
| 3 | 79 | 77.7 GB | same, balanced |
| 4 | 84 | 77.7 GB | same, balanced |
| 5 | 78 | 77.7 GB | same, balanced |

The Morocco atlas = 11 NISAR frames, seen from both orbit directions, covering Al Wahda, the Rif,
Casablanca, Khouribga, Ben Guerir and the Haouz. **Part 1 is already done** (Ayman) — get it from the
team data zip instead of downloading it again.

### Install (once)
Python 3.10 or newer, then:
```
python -m pip install requests h5py numpy rasterio pyproj rich
```

### Run it
From the repo root (`NASA_SAR\`):
```
python download_all.py run --part 2
```
or click **Run** in VS Code: with no arguments the script asks which part to download.

| command | what it does |
|---|---|
| `python download_all.py run --part N` | downloads part N (1 to 5) into `data\` |
| `python download_all.py status` | table of progress for all 5 parts (finished, partial, remaining, %) |
| `python download_all.py run --part N --workers 3` | fewer parallel downloads (default 5) |
| `python download_all.py run --part N --out E:\nisar_data` | writes the data somewhere else (default `data\` next to the script) |
| `python download_all.py build-plan` | rebuilds `plan_nisar.json` from NASA's archive — **don't**, unless the whole team agrees: everyone must use the same plan |

### What you see while it runs
A progress bar for the whole part (GB done, speed, **time remaining**) and one bar per file being
downloaded. Each finished file prints a line: `✓ GUNW T116 F019 20261008→20261020  2.7 GB → kept 170 MB`.
At the end: a summary, and a log of every file in `data\manifest.csv`.

### Stop and resume
- **Ctrl+C stops cleanly at any time.** What is downloaded is kept.
- **Run the same command again** to resume: finished files are skipped, a half-downloaded file resumes
  from the exact byte where it stopped, a downloaded-but-not-processed file is processed without
  downloading it again.
- A corrupted or unreadable file is deleted automatically and downloaded again on the next run.

### Disk space and time
- Space needed while running: about **3 GB per worker** for the file being processed (≈ 15 GB with 5
  workers) plus what is kept (about 11 GB per part, 3.3 GB for part 1).
- Time: 78 GB takes ~3.5 h at 50 Mbit/s, ~1.7 h at 100 Mbit/s, ~20 min at 500 Mbit/s. Speed depends
  on your connection, not on the number of workers: more than 5–8 does not help.
- Fastest: one team member per part, on different internet connections.

### Where the data goes
```
NASA_SAR\data\
   GUNW\<file name>\     unwrappedInterferogram_HH_unwrappedPhase.tif, ..._coherenceMagnitude.tif,
                         ..._connectedComponents.tif, ..._ionospherePhaseScreen.tif, radar_geometry.npz, _DONE
   SME2\<file name>\     the soil-moisture .h5 file, _DONE
   manifest.csv          log of every file
```
The backend reads this folder directly. Several people's downloads merge by copying their `GUNW\` and
`SME2\` folders into one `data\` (names never collide).

### Morocco plan: `--plan`, `--keep-raw` and two small tools
The Morocco plan (`docs/claude/MOROCCO_PLAN.md`) uses **tiers** instead of the 5 parts: with
`--plan`, "part N" means tier N (1 = Al Haouz + soil moisture at the sites, 2 = full chains of the
frames that cover the sites, 3 = rest of the soil moisture). `plan_nisar.json` is never touched.

```powershell
# 1. Build the plan (ASF metadata only, nothing is downloaded). --dry-run prints the summary only.
python tools/make_morocco_plan.py --dry-run
python tools/make_morocco_plan.py                      # writes plan_morocco.json

# 2. Check it, then download tier 1 keeping the raw .h5 files
$env:EARTHDATA_TOKEN = "<your token>"
python download_all.py status --plan plan_morocco.json
python download_all.py run --plan plan_morocco.json --part 1 --workers 3 --keep-raw --out D:\nisar_data

# 3. Look inside one raw file to check layer names before tier 2
python tools/list_h5_layers.py D:\nisar_data\GUNW\<name>\<name>.h5 iono tropo tide mask
```
- `--keep-raw` keeps each raw `.h5` next to its GeoTIFFs (about 2.3 GB per GUNW). The free-space check
  adds their size.
- Morocco GUNW rows also extract extra layers (ionosphere uncertainty, mask, troposphere and
  solid-earth-tide cubes). **These layer names are not verified on a real file yet.** If one is missing
  the script warns, writes it to `_extra_layers.json` and `_DONE` (`raw_kept_missing_layers`), and
  **keeps the raw `.h5` even without `--keep-raw`**. Fix `EXTRA_LAYERS` / `EXTRA_META_KEYWORDS` in
  `download_all.py` before running tier 2.
- `tools/list_h5_layers.py <file.h5> [keyword ...]` prints every dataset path with shape and dtype,
  optionally filtered by keywords (case-insensitive). Read-only, needs only `h5py`.

### Problems
| message | fix |
|---|---|
| `Erreur 401 : jeton Earthdata invalide ou expiré` | the key expired or was revoked: create a token on urs.earthdata.nasa.gov (profile → Generate Token) and set it with `$env:EARTHDATA_TOKEN="..."` (PowerShell) before running |
| `the following arguments are required` / VS Code shows usage | old version of the script: pull the repo again |
| warning about free disk space | free space or use `--out` towards another drive |
| a file shows `✗ … erreur` | run the same command again; only the failed files are retried |
| part 1 shows 0 % after unzipping the team data | the zip was unzipped in the wrong place: you need `NASA_SAR\data\GUNW`, not `data\data\GUNW` |

---

## Step-by-step: from zero to the running app

**1. Get the code**
```
git clone https://github.com/AYmANTwill/NASA_SAR.git
cd NASA_SAR
```
**2. Install**
```
python -m pip install -r backend\requirements.txt
```
**3. Get the data** — unzip the team data zip into `NASA_SAR\data` (part 1), and/or run the download
script for your part (see above). Check with `python download_all.py status`.

**4. Check everything works** (synthetic data, no internet needed)
```
cd backend
python tests\test_all.py
```
Expected: `30/30 checks passed`.

**5. Compute the demo answers, start the API**
```
python precompute.py
python -m uvicorn api:app --port 8000
```
Open http://localhost:8000/docs and try `/health`, `/events/panama-2026`, `/ask`.
Without internet: `python precompute.py --no-exposure` and set `NISAR_OFFLINE=1`.

**6. Build the interface** — read [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md). Every data endpoint
accepts `?mock=true` and returns a realistic fake answer, so screens can be built before any data is
processed. Map layers are PNG images with bounds: `L.imageOverlay(layer.url, layer.bounds)` in Leaflet.

**7. Share new data** — `python tools\make_data_zip.py` creates `NISAR_Pulse_data.zip` (ignored by git)
to send through a drive or a USB key.

## Before the demo
- [ ] `python backend\tests\test_all.py` → 30/30 on the demo laptop
- [ ] Sign check: compare the `/events/panama-2026` map with NASA's or USGS's published map of the
      9 October 2026 earthquake; if the colours are reversed, set `NISAR_LOS_SIGN=-1` and rerun `precompute.py`
- [ ] `python backend\precompute.py` after the last data merge
- [ ] Offline rehearsal with `NISAR_OFFLINE=1`
- [ ] Optional keys: `FIRMS_MAP_KEY` (free, fire evidence), `ANTHROPIC_API_KEY` (paid, smarter questions and Arabic phrasing)

## Data sources
NISAR L-band products (GUNW, SME2; GCOV and GOFF supported) from the
[ASF DAAC](https://asf.alaska.edu/); USGS earthquake catalogue; Open-Meteo ERA5 archive; NASA FIRMS;
OpenStreetMap (Overpass).
