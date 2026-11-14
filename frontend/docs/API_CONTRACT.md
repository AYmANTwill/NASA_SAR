# NISAR Pulse API contract (v2)

For the FastAPI team. The frontend is ready to plug in: point it at your server and every screen works. The source of truth is [`src/api/contract.ts`](../src/api/contract.ts) (zod schemas). Your Pydantic models should match it field for field. Any response that does not match is rejected by the UI and shown as an explicit "contract" error, never patched with a guessed value.

Synthetic examples of every payload live in [`src/__fixtures__/`](../src/__fixtures__/). They validate against the schemas (`npm test`) and are the quickest way to see what a valid response looks like.

## Wiring

| Setting | Default | Meaning |
|---|---|---|
| `VITE_API_MODE` | `http` | `http`: talk to FastAPI. `fixtures`: synthetic data with a "test data" banner. |
| `VITE_API_BASE` | `/api` | Base URL of the API (same origin recommended). |
| `VITE_API_PROXY` | `http://127.0.0.1:8000` | Dev only: Vite proxies `/api` to this address. |

Run `npm run dev:api` with FastAPI listening on port 8000. In production, serve the frontend and the API from the same origin (or enable CORS for the frontend origin).

## Non-negotiable rules

1. **Every measurement carries its uncertainty**: `Measurement = {value, uncertainty, unit, sigma}`. `uncertainty` is required. `sigma` says how many σ it represents (default 1).
2. **Confidence (`high|medium|low`) and watch level (`yellow|orange|red`) are computed by your fixed rules.** The UI displays them and never recomputes them.
3. **No free prose from the LLM.** Every sentence is a `TemplatedText = {template, params, text?}`. The UI translates `template` into FR, AR and EN and inserts the formatted `params`. Numbers therefore always come from your code. `text` is an optional per-language fallback for a template the frontend does not know yet.
4. **Every answer has at least one `limits` item** ("What the radar cannot tell here").
5. **"Stable within noise" is a first-class answer**: `stable_in_noise: true`, with a verdict like `verdict.stable_in_noise`.
6. **Fukuzono is an indication, never a forecast**: `indication = {method: "inverse_velocity", window, caveat}`.

### Template parameters

| Param shape | Rendered as |
|---|---|
| `"text"` | as is |
| `12.5` | number, localized |
| `{value, uncertainty, unit, sigma}` | `12.5 ± 0.4 mm/yr`, rounded to the uncertainty |
| `{date: "2026-10-09"}` | localized long date |
| `{term: "recipe.slow_motion"}` | catalog term (recipe names, watch levels) |
| `{localized: {fr, ar, en}}` | proper noun in the reader's language (place names) |
| `count` (number) | also selects the plural form, including the 6 Arabic forms |

The template catalog is in `src/i18n/locales/{fr,ar,en}.json` under `tpl` (and `term`). To add a template, add it in all three files. `npm test` checks parity and that no template hard-codes a digit.

### Units

`mm, cm, m, mm/yr, cm/yr, mm/yr2, m3/m3, dB, ha, km2, percent, coherence, km`

## Endpoints

| Method | Path | Response | Screen |
|---|---|---|---|
| POST | `/api/ask` | `text/event-stream` (below) | Investigation |
| GET | `/api/answers/{id}` | `Answer` | Investigation, links from other screens |
| GET | `/api/discoveries?region=MA` | `Discoveries` | Home "What NISAR found in Morocco" |
| GET | `/api/watches` | `Watch[]` | Watch |
| POST | `/api/watches` body `{answer_id}` | `Watch` (idempotent per answer) | "Watch this place" |
| DELETE | `/api/watches/{id}` | 204 | Watch |
| GET | `/api/notifications` | `WatchNotification[]` | Watch history (shown in FR and AR) |
| GET | `/api/library` | `LibraryEvent[]` | World library |
| GET | `/api/proofs/lband-vs-cband` | `LbandProof` | L-band vs C-band figure |
| GET | `/api/demo` | `DemoBundle` | Offline demo cache, example questions |

Errors: any non-2xx status with body `{code, message: TemplatedText}`, e.g. `{"code": "no_coverage", "message": {"template": "error.no_coverage", "params": {}}}`.

### `POST /api/ask`: agent steps as SSE

Request: `{"question": "...", "lang": "fr"|"ar"|"en", "location": {"lat": 34.64, "lon": -5.17} | null}`

Response `Content-Type: text/event-stream`, events in order:

```
event: step
data: {"id":"s1","kind":"classify","tool":"agent.classify","status":"running","params":{},"started_at":"2026-11-11T09:00:00Z","duration_ms":null,"summary":null,"error":null}

event: step
data: {"id":"s1","kind":"classify","tool":"agent.classify","status":"done","params":{},"started_at":"…","duration_ms":180,"summary":{"template":"step.classify","params":{"recipe":{"term":"recipe.slow_motion"}}},"error":null}

… one or more steps (same id = update) …

event: answer
data: { …Answer… }
```

Or `event: error` with `{code, message}`. The UI shows each step as it arrives (name, tool, status, collapsible params, duration), then the verdict. `kind` is one of `classify, select_recipe, search_scenes, download, compute, uncertainty_checks, cross_evidence, verdict, cache`. Include the final step list in `Answer.steps` so a cached answer can show how it was produced.

With FastAPI: `StreamingResponse(gen(), media_type="text/event-stream")`, with each chunk formatted as `f"event: {name}\ndata: {json}\n\n"`.

### `Answer` (main fields)

| Field | Notes |
|---|---|
| `verdict` | `TemplatedText`, one sentence |
| `confidence`, `stable_in_noise` | from your rules |
| `recipe`, `product`, `product_status` | `provisional` while ASF products are PROVISIONAL |
| `period`, `acquisitions[]`, `tracks[]` | track `{number, direction, frame}` |
| `metrics[]` | `{id, measurement}`. Put `noise_floor` in the same unit as the metric it qualifies so the UI can draw the noise ruler |
| `series[]` | `{id: los\|vertical\|east_west\|soil_moisture\|…, unit, points[{date, value, lo, hi}], noise_floor, sigma}`. Vertical and east-west are drawn as small multiples on a shared axis |
| `checks[]` | the 4 checks: `noise_floor, coherence_mask, ionosphere, unwrapping`, each `pass\|warn\|fail\|not_applicable` |
| `evidence[]` | `{source, agreement: agrees\|disagrees\|inconclusive\|unavailable, summary, url, retrieved_at}` |
| `layers[]` | rasters (below) |
| `earthquakes[]` | USGS mainshock and aftershocks overlay |
| `limits[]` | ≥ 1 |
| `indication`, `classifier` | nullable. The classifier must carry `beta: true`, plus precision and recall measured on a held-out event |
| `next_pass`, `cached` | |

### Rasters

`RasterLayer = {id, kind, url, bounds:[west,south,east,north], unit, min, max, palette, sign_convention, period, source}`

- PNG, RGBA, north-up, WGS84 bounds (pixel outer edges), transparent = no data.
- **Colourize with the canonical palettes in [`src/design/palettes.json`](../src/design/palettes.json)** (linear between `min` and `max`) so the legend matches the pixels:
  - `diverging_displacement` for displacement or velocity, with `min = -max` (centred on zero);
  - `sequential_coherence` for coherence;
  - `sequential_coherence_loss` for coherence loss;
  - `sequential_moisture` for soil moisture.
- `sign_convention`: `positive_toward_satellite | positive_away_from_satellite | positive_up | positive_east`. It is shown in the legend.
- Serve the PNGs from the same origin (e.g. `/api/rasters/...`) so the service worker caches them for offline mode.

### Discoveries

`{region, region_name{fr,ar,en}, generated_at, period, noise_floor: Measurement, threshold_factor, zones[]}`. Each zone has `{rank, location, kind, velocity, vertical?, east_west?, snr, exposure{buildings, roads_km, dams, mines}, exposure_score, confidence, manually_checked, answer_id}`. The UI sorts by `rank` (velocity) or by `exposure_score`. It never computes the scores.

### Offline demo (`/api/demo`)

`{generated_at, entries:[{answer_id, questions:[{text, lang}]}]}`. On every online launch, the UI downloads the bundle and each listed answer, then keeps them in localStorage. Offline, a question matching one of these (after normalization, in any language) is answered from that cache with its recorded steps replayed (staged, under four seconds; immediate with reduced motion). List the Panama, Venezuela, Al Wahda, zone #1 and Gharb questions here, in FR, AR and EN.

## API changes the UI needs (not in the original plan)

These are requests to the backend team. I have not touched the backend.

1. **Templated prose instead of free LLM text** (`TemplatedText`) for verdicts, step summaries, checks, evidence, limits and notifications. This is what makes the Arabic notification and the "no invented numbers" rule possible.
2. **`DemoBundle` endpoint** for the offline demo.
3. **`noise_floor` in the metric's own unit** and **`sigma` on series**, so the uncertainty band and noise ruler are labelled honestly.
4. **Place names in three languages** (`name_i18n`, `{localized}` params).
5. **`questions[].lang`**, so example questions appear in the reader's language.

## Integration with the team backend, verified on 14 November 2026

The backend team's adapter (`AYmANTwill/NASA_SAR`, branch `feat/frontend-adapter`, `backend/api_v2.py`) serves this contract under `/api`. I ran it locally (uvicorn on port 8000, `npm run dev:api`) and checked every screen in FR, AR and EN, first in mock mode, then with the five real event results of branch `results/real-data-checks` placed in its event cache. No frontend change was needed to talk to it.

### Done on the frontend side (their four requests)

1. `surface_change` added to `Recipe` and to `recipe.surface_change` in fr/en/ar. **Backend: you can stop sending surface change as `damage`.**
2. `503 discoveries_disabled` on `/api/discoveries` is shown as an information state on the home page ("What NISAR has looked at": the library events on the map, plus your message and why discoveries stay hidden). No error, no retry button. Explicit API errors are no longer retried by the query layer.
3. `404 not_available` on `/api/proofs/lband-vs-cband` is shown as "Comparison not computed yet", with a "soon" badge on the navigation entry (http mode) and an animated, to-scale explanation of L-band versus C-band (physical constants only, no data).
4. `palettes.json` is unchanged. Nothing to copy.

### Offline demo: real recorded answers

The five real answers (`event-haouz-flood-2026-10-10`, `event-haouz-soil-moisture`, `event-gharb-soil-moisture`, `event-ben-guerir-mine`, `event-al-wahda-surroundings`) were recorded from `/api/answers/*`, `/api/demo` and `/api/library` into [`src/__fixtures__/backend/`](../src/__fixtures__/backend/). In demo mode they carry a "recorded real answer" note. Two documented adjustments: `layers` emptied (the PNGs are rendered from HDF5 files that are not shipped), and `damage` → `surface_change`. A unit test checks that every raw recording passes the zod contract as recorded.

### What I noticed (requests, not done; I did not touch the backend)

1. **Decimal separator in prose.** Verdicts are written with a point in French and Arabic ("43.4 mm", "0.219 m³/m³"), while the rest of the UI writes "43,4". Format numbers per language in `agent.template`, or pass them as `Measurement` params so the UI formats them.
2. **`uncertainty: 0` means "not provided".** Rain totals (`evidence.open_meteo.rain`), `noise_floor` and `coherence_loss_area` arrive with `uncertainty: 0`. The UI now prints the value alone instead of "± 0", but a real uncertainty, or `null` with an explicit field, would be more honest.
3. **OpenStreetMap is unreachable** (`406 Not Acceptable` from Overpass): send a descriptive `User-Agent` header. The error text is English inside the FR/AR prose.
4. **`tracks` is empty** in the recorded answers. The UI uses `tracks[0].direction` to orient the satellite pass that reveals the rasters (it falls back to ascending).
5. **Layer PNGs**: `/api/layers/*.png` returns 404 when the products are not on disk. Fine, but the answer still lists the layer. Omit layers whose PNG does not exist.
6. **Library**: only Al Haouz and Panama are listed, and Panama has no data on disk (its answer is empty). Consider listing the four other Moroccan events.
7. **Security**: `STATUS.md` (H1) says an Earthdata token is hard-coded in `download_all.py` and present in the history of a public repository. Revoke it and generate a new one.

### Ten-minute wiring checklist

1. `git clone -b feat/frontend-adapter https://github.com/AYmANTwill/NASA_SAR.git`, then in `backend/`: `python -m pip install -r requirements.txt` and `python -m uvicorn api:app --port 8000`.
2. In this repo: `npm run dev:api` and open the printed URL.
3. Home: information state, two library events on the map. L/C: "not computed yet", badge "soon".
4. Ask "Le terrain autour du barrage Al Wahda bouge-t-il ?": steps, staged pass, verdict "stable in the noise", limits.
5. Switch to Arabic and English: same answer, prose in the reader's language.
6. Production: `npm run build`, serve `dist/` and the API from the same origin.
