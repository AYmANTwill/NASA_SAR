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

`{generated_at, entries:[{answer_id, questions:[{text, lang}]}]}`. On every online launch, the UI downloads the bundle and each listed answer, then keeps them in localStorage. Offline, a question matching one of these (after normalization, in any language) is answered from that cache in under a second, with its recorded steps replayed. List the Panama, Venezuela, Al Wahda, zone #1 and Gharb questions here, in FR, AR and EN.

## API changes the UI needs (not in the original plan)

These are requests to the backend team. I have not touched the backend.

1. **Templated prose instead of free LLM text** (`TemplatedText`) for verdicts, step summaries, checks, evidence, limits and notifications. This is what makes the Arabic notification and the "no invented numbers" rule possible.
2. **`DemoBundle` endpoint** for the offline demo.
3. **`noise_floor` in the metric's own unit** and **`sigma` on series**, so the uncertainty band and noise ruler are labelled honestly.
4. **Place names in three languages** (`name_i18n`, `{localized}` params).
5. **`questions[].lang`**, so example questions appear in the reader's language.
