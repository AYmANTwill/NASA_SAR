# NISAR Pulse API — contract for the interface

Base URL: `http://localhost:8000` · interactive docs: `http://localhost:8000/docs`
All answers are JSON. Add `?mock=true` to any data endpoint to get a realistic fake answer
(`"mock": true`) — useful to build screens before the data is processed.

## POST /ask — ask a question about a place
Request:
```json
{"question": "Le barrage Al Wahda se déforme-t-il depuis juin ?", "lat": 34.64, "lon": -5.17,
 "lang": "fr", "date": null}
```
`lat`/`lon` optional if the question names a known place (see `/places`). `lang`: fr | en | ar
(auto-detected if absent). `date`: YYYY-MM-DD of an event, optional.

Response (fields the interface uses):
| field | type | meaning |
|---|---|---|
| `type` | string | sudden_motion, slow_motion, damage, flood, deforestation, soil_moisture, large_displacement |
| `verdict` | string | the one-sentence answer, in the user's language |
| `confidence` | string | high, medium, low |
| `confidence_reasons` | string[] | why |
| `alert_level` | string | none, yellow, orange, red |
| `layers` | object[] | map overlays: `{url, bounds: [[south, west], [north, east]], vmin, vmax, cmap, title}` — a PNG to place with Leaflet `L.imageOverlay(url, bounds)` or a MapLibre image source |
| `series` | object[] \| null | time series per viewing geometry: `{direction, velocity_mm_yr, series: [{date, los_mm}]}` (slow_motion) or `[{date, value}]` (soil moisture, in `facts.series`) |
| `profile` | object[] \| null | west–east profile through the point: `[{km, value}]` |
| `evidence` | object[] | `{source, status: agrees/disagrees/none/unavailable, summary}` |
| `cannot_say` | string | what the radar cannot tell here |
| `steps` | object[] | the agent's steps for the "how I found this" panel: `{step, ok, ms}` |
| `place` | object | `{lat, lon, name}` |
| `facts` | object | every number behind the verdict (for detail panels) |
| `data_used` | string[] | NISAR product ids used |

400 if there is no location: `{"detail": {"error": "...", "known_places": [...]}}`.

## GET /events · GET /events/{id}
Library of precomputed answers (instant, offline-safe). Ids: `panama-2026`, `venezuela-2026`, `al-wahda`,
`ben-guerir-mine`, `gharb-soil`. `/events/{id}` returns the same shape as `/ask` plus `event: {id, title}`.
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
- `GET /health` → products available, mock mode, LLM / FIRMS keys present
- `GET /catalog?level=GUNW` → downloaded products
- `GET /places` → named places the agent understands
- `POST /classify` `{before_id, after_id}` → change classes map (after the classifier is trained)
- `GET /layers/{name}.png` → map images (URLs come inside answers)

Colour conventions: displacement `RdBu_r` (blue = away from the satellite / sinking, red = toward the
satellite), damage `inferno`, flood `coolwarm` (blue = open water, red = flooded vegetation), soil
moisture `YlGnBu`. Alert colours: yellow / orange / red.
