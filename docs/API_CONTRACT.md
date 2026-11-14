# NISAR Pulse API — contract for the interface

Base URL: `http://localhost:8000` · interactive docs: `http://localhost:8000/docs`
All answers are JSON. Add `?mock=true` to any data endpoint to get a realistic fake answer
(`"mock": true`) — useful to build screens before the data is processed.

## POST /ask — ask a question about a place
Request:
```json
{"question": "Le barrage Al Wahda se déforme-t-il depuis juin ?", "lat": 34.598, "lon": -5.198,
 "lang": "fr", "date": null}
```
`lat`/`lon` optional if the question names a known place (see `/places`). `lang`: fr | en | ar
(auto-detected if absent). `date`: YYYY-MM-DD of an event, optional. A date alone is a **whole-day event**
(precision `day`); named events with a known instant (the Panama earthquake) are `exact`.

Response (fields the interface uses):
| field | type | meaning |
|---|---|---|
| `type` | string | sudden_motion, slow_motion, surface_change, flood, deforestation, soil_moisture, large_displacement, or `unknown` (the question was not understood: `verdict` asks to rephrase, no alert) |
| `verdict` | string | the one-sentence answer, in the user's language |
| `confidence` | string | high, medium, low |
| `confidence_reasons` | string[] | why |
| `alert_level` | string | none, yellow, orange, red |
| `layers` | object[] | map overlays: `{url, bounds: [[south, west], [north, east]], vmin, vmax, cmap, title}` — a PNG to place with Leaflet `L.imageOverlay(url, bounds)` or a MapLibre image source |
| `series` | object[] \| null | time series per viewing geometry: `{direction, velocity_mm_yr, series: [{date, los_mm}]}` (slow_motion) or `[{date, value}]` (soil moisture, in `facts.series`) |
| `profile` | object[] \| null | west–east profile through the point: `[{km, value}]` |
| `evidence` | object[] | `{source, status: agrees/disagrees/none/unavailable/context, summary}`. `context` = rain or an earthquake that co-occurs with the measurement but does not test it (surface change): never counted as confirmation |
| `cannot_say` | string | what the radar cannot tell here |
| `steps` | object[] | the agent's steps for the "how I found this" panel: `{step, ok, ms}` |
| `place` | object | `{lat, lon, name}` |
| `facts` | object | every number behind the verdict (for detail panels) |
| `data_used` | string[] | NISAR product ids used |
| `event_time` | object \| null | `{utc: "YYYYMMDDTHHMMSS", precision: "exact"\|"day"}` when the answer is about an event |

### Facts added for Morocco (all numbers in `verdict` come from `facts`)
- **Every GUNW product** has `crid` (e.g. `P05023`) and `maturity` (`provisional` / `validated` / `unknown`, from the CRID).
  CRIDs are never mixed in one series or one before/after comparison. `/catalog` and `facts` expose both.
- **`surface_change`** (replaces `damage`; coherence loss, independent of the LOS sign): `mode` (`event` | `latest`),
  `event_day`, `event_precision`, `pre_pair`, `co_pair`, `pre_date_before`, `pre_date_after`, `date_before`, `date_after`,
  `window_days`, `loss_at_point` (0 none, 1 total), `changed_km2_5km` (was `damaged_km2_5km`), `coherent_before_fraction_5km`,
  `threshold`, `n_geometries`, `n_usable_geometries` (a geometry is usable if >= 50 % of the 5 km area was coherent before),
  `geometries[]` (with `usable`), `geometries_agree` (usable ones only), `changed_km2_range`, `ambiguous_pairs[]` (pairs with an acquisition on the
  event day, never used), `routed_from` (`"flood"` when no GCOV covers the point), `crid`, `maturity`, `layer`.
  The before pair and the event pair share track, frame, CRID and length (±1 day). Confidence is `medium` at most.
- **`slow_motion`**: `velocity_mm_yr` is `null` for a record shorter than `min_rate_days` (365); then `total_mm` (cumulative LOS),
  `span_days`, `noise_mm` are the answer and confidence is capped. Also `crid`, `maturity`, `chain_connected`,
  `n_components`, `unmeasured_dates`, and per series `n_bridge_pairs` (pairs that skip an acquisition, e.g. across the
  2026-07-27 → 08-10 data gap). A chain cut into pieces is reported; only the longest piece is used.
- `sudden_motion` needs an event: no event, or no pair that straddles it, gives an error in `facts` and a no-data verdict
  (there is no fallback to other pairs).

400 if there is no location: `{"detail": {"error": "...", "known_places": [...]}}`.

## GET /events · GET /events/{id}
Library of precomputed answers (instant, offline-safe). Ids: `haouz-flood-2026-10-10`, `haouz-soil-moisture`, `gharb-soil-moisture`,
`ben-guerir-mine`, `al-wahda-surroundings` (each with `title`, `title_en`, `title_ar`). Panama and Venezuela
are synthetic test fixtures: still resolvable by id, never listed. `/events/{id}` returns the same shape as `/ask` plus `event: {id, title}`.
`?refresh=true` recomputes.

## GET /discoveries — "what NISAR found"
`{zones: [{id, rank, lat, lon, area_km2, mean, peak, unit ("mm/yr" or "cm"), snr, confidence,
alert_level, direction, exposure: {buildings, dams, ...} | null}], n_geometries, note}`.
`?refresh=true&exposure=false` recomputes (exposure needs internet).

## Watch
- `POST /watch` `{lat, lon, question, lang, label}` → the watch: `{id, level, last_verdict, next_passes: [{direction, next_pass}], notifications: [...]}`
- `GET /watch` → all watches · `DELETE /watch/{id}`
- `POST /watch/check` → re-runs every watch, returns `{alerts: [{watch, level, message}]}` (message in the watch's language)
- `GET /next-pass?lat=&lon=` → next NISAR passes over a point

## Other
- `GET /health` → products available, mock mode, LLM / FIRMS keys present, `map_view` `{lat, lon, zoom}` (centred on Morocco)
- `GET /catalog?level=GUNW` → downloaded products
- `GET /places` → named places the agent understands (French, English and Arabic aliases; whole-word matching, longest alias first)
- `POST /classify` `{before_id, after_id}` → change classes map (after the classifier is trained)
- `GET /layers/{name}.png` → map images (URLs come inside answers)

Colour conventions: displacement `RdBu_r` (blue = away from the satellite / sinking, red = toward the
satellite), surface change (coherence loss) `inferno`, flood `coolwarm` (blue = open water, red = flooded vegetation), soil
moisture `YlGnBu`. Alert colours: yellow / orange / red.
