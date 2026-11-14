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
| `steps` | object[] | the agent's steps for the "how I found this" panel: `{step, ok, ms}`; a failed step (or an evidence source that answered `unavailable`) has `ok: false` and `error` |
| `place` | object | `{lat, lon, name}` |
| `facts` | object | every number behind the verdict (for detail panels) |
| `data_used` | string[] | NISAR product ids used |
| `event_time` | object \| null | `{utc: "YYYYMMDDTHHMMSS", precision: "exact"\|"day"}` when the answer is about an event |

### Facts added for Morocco (all numbers in `verdict` come from `facts`)
- **Every GUNW product** has `crid` (e.g. `P05023`) and `maturity` (`provisional` / `validated` / `unknown`, from the CRID).
  CRIDs are never mixed in one series or one before/after comparison. `/catalog` and `facts` expose both.
- **`surface_change`** (replaces `damage`; coherence loss, independent of the LOS sign): `mode` (`event` | `latest`),
  `event_day`, `event_precision`, `pre_pair`, `co_pair`, `pre_date_before`, `pre_date_after`, `date_before`, `date_after`,
  `window_days`, `threshold` (0.3), `radius_m` (5000), `n_geometries`, `n_usable_geometries`, `geometries[]`,
  `geometries_agree` (usable ones only: do they all reach at least the borderline band?), `changed_km2_range`,
  `ambiguous_pairs[]` (pairs with an acquisition on the event day, never used), `routed_from` (`"flood"` when no GCOV
  covers the point), `crid`, `maturity`, `layer`. The before pair and the event pair share track, frame, CRID and length (±1 day).
  The area is a **true 5 km radius circle** clipped at the array edge (not the old 10×10 km square; the key names are unchanged).
  Per geometry, and at the top level of `facts` for the main geometry (a reliable baseline first, then the best covered):
  - `coverage_5km`: fraction of the circle with valid data in both pairs. `coherent_before_fraction_5km`: fraction of those
    valid pixels with coherence >= 0.4 before the event.
  - `loss_at_point` (median within 1 km, 0 none, 1 total; **a fact only, it is not in the sentence**), `loss_mean_5km`,
    `changed_km2_5km` (was `damaged_km2_5km`: area with a loss above `threshold`).
  - Baseline: `baseline_pair`, `baseline_loss_mean`, `baseline_changed_km2` = the same loss between the before pair and the
    pair just before it (no event in that window). Frame background: `frame_loss_mean`, `frame_frac_changed` (whole frame,
    event pair).
  - `excess_over_frame` = `loss_mean_5km` − `frame_loss_mean`, and `excess_level`: `"strong"` (>= `excess_strong` 0.15:
    "local excess", orange, medium at most) · `"borderline"` (>= `excess_margin` 0.11 and < 0.15: "just above the 1 % no-event
    level", yellow, low, no cause) · `"none"` (< 0.11: "no clear local change", no alert). `local_excess` is true only for strong.
  - `baseline_unreliable`: true when the before pair's mean coherence is more than 0.1 below the median of the geometry's other
    pairs (confidence capped at low); `null` when fewer than 3 other pairs exist. With `pair_coherence_mean`,
    `other_pairs_coherence_median`, `n_other_pairs`.
  - The no-event reference: `null_false_alarm` (0.01) and `null_false_alarm_pct` (1) = share of no-event circles above
    `excess_margin`, and `null_limits[]`: it was measured on one viewing geometry (044/17), one season (June to September 2026)
    and circles placed at random in the frame. The verdict says so in the three languages.
  - **Usable** geometry: `coverage_5km >= 0.9`, a baseline pair exists and is measurable (coherent on >= 50 % of the valid
    pixels), and >= 50 % of the valid pixels were coherent before the event. Otherwise `usable: false`,
    `reason: "not usable: <reason>"` and no change number (`coverage_5km` and `coherent_before_fraction_5km` stay as diagnostics).
    If no geometry is usable, `facts` is `{"error": "not usable: <reason>", "geometries": [...], ...}` and the verdict is a no-data sentence.
  Confidence is `medium` at most.
- **Signed line-of-sight answers** (`sudden_motion`, `slow_motion`): `sign_verified` (false until `NISAR_LOS_SIGN_VERIFIED=1`).
  While false, the verdict starts with "Uncorrected line-of-sight change, sign unverified" (FR/AR equivalents), `confidence` is
  `low` and `alert_level` is `none`. `sign_basis`: why the sign is what it is (documented convention: GUNW phase positive = away
  from the sensor, ARIA-tools / MintPy prep_nisar); `NISAR_LOS_SIGN_VERIFIED` stays the switch. Also `iono_screen` (`"subtracted"` =
  the product's `ionospherePhaseScreen` is subtracted, not validated · `"partly subtracted"` · `"not applied"`),
  `troposphere_corrected` (false unless `NISAR_CORRECTIONS` includes `tropo` and it was applied; then the verdict says so),
  `tide_corrected` (same for `tide`), `corrections_requested[]` / `corrections_applied[]`, and
  `reference_same_component` (the reference area shares the point's connected component; false caps confidence at low;
  slow motion also `n_pairs_reference_other_component`). Slow motion adds `crosses_data_gap`, `n_pairs_across_gap`,
  `data_gap_start`, `data_gap_end` (a pair that starts before and ends after a configured acquisition gap, now 2026-07-27 to
  2026-08-10); the verdict says so.
- **Corrections** (`NISAR_CORRECTIONS`, default `iono` = the previous behaviour; `tropo` and `tide` stay off until
  `noise_report.py` shows they lower the noise): each pair in `facts.pairs[]` (sudden motion) has `corrections: {iono|tropo|tide:
  {applied, reason, dataset, convention ("subtracted from unwrappedPhase"), units, units_attribute, description,
  attributes_from (the raw .h5 kept with --keep-raw, else "not available"), already_applied_flag (true/false/null from
  processingInformation; true = never applied twice)}}`. Cubes add `height_source` (Copernicus GLO-30, a local DEM, or the
  documented constant), `height_m_median`, `cube_epsg`. The ionosphere adds `kept_raw` (the raw phase is kept for a pair where
  subtracting does not lower the frame-wide robust sigma), `frame_sigma_raw_rad`, `frame_sigma_subtracted_rad`,
  `uncertainty_layer`, `uncertainty_max_rad` (`NISAR_IONO_UNC_MAX_RAD`, default 1.0) and `uncertainty_masked_fraction`
  (pixels whose screen uncertainty is above the threshold are masked).
- **Pair quality** (all GUNW answers): `rejected_pairs[]` = `{product, reasons[], phase_sigma_rad, coherence_median}` for pairs
  with a flat unwrapped phase (robust sigma < `NISAR_FLAT_PHASE_SIGMA_RAD`, 0.001) or a median coherence below
  `NISAR_MIN_PAIR_COHERENCE` (0.15). They are never used: not in series, not as surface-change before / event / baseline pairs,
  not in discoveries. Time series also list them per series.
- **`soil_moisture`**: `uncertainty_m3m3` (median of the product's `soilMoistureUncertainty` around the point; 0.028 if the layer
  is missing) and `within_uncertainty` (|`anomaly_m3m3`| below it). When true the confidence is `low` and the verdict says the
  change is within the product's uncertainty. Never above `medium` (provisional L3 product).
- **`slow_motion`**: `velocity_mm_yr` is `null` for a record shorter than `min_rate_days` (365); then `total_mm` (cumulative LOS),
  `span_days`, `noise_mm` are the answer and confidence is capped. Also `crid`, `maturity`, `chain_connected`,
  `n_components`, `unmeasured_dates`, and per series `n_bridge_pairs` (pairs that skip an acquisition, e.g. across the
  2026-07-27 → 08-10 data gap). A chain cut into pieces is reported; only the longest piece is used.
- `sudden_motion` needs an event: no event, or no pair that straddles it, gives an error in `facts` and a no-data verdict
  (there is no fallback to other pairs).

400 if there is no location: `{"detail": {"error": "...", "known_places": [...]}}`.

## GET /events · GET /events/{id}
Library of precomputed answers (instant, offline-safe). Ids: `haouz-flood-2026-10-10`, `haouz-soil-moisture`, `gharb-soil-moisture`,
`ben-guerir-mine`, `al-wahda-surroundings` (each with `title`, `title_en`, `title_ar`, and `kind: "morocco"`).
**Validation event** (outside the Morocco scope): `panama-2026` (Panama M7.7, 9 Oct 2026 17:56:06 UTC, USGS `us6000u18k`, exact
instant), `kind: "validation"`, `status: "validation"`. Listed only with `GET /events?include_validation=true` (after the five
Morocco events; the default listing is unchanged); its answer has `kind` and `event: {id, title, scope, usgs_id, magnitude,
origin_utc, usgs_url}`. Venezuela is a synthetic test fixture: resolvable by id, never listed. `/events/{id}` returns the same shape as `/ask` plus `event: {id, title}`.
`?refresh=true` recomputes. Each event has `status` (`"ready"`, or `"not validated"` with `status_note`: `ben-guerir-mine` is the
mine centroid with no quarry polygon checked) in the listing and in the answer; the title says so too.

## GET /discoveries — "what NISAR found" (OFF by default)
Disabled unless `NISAR_DISCOVERIES_ENABLED=1`: the API then returns `{enabled: false, label: "unvalidated candidate", zones: [], n_geometries: 0,
reason}` (never an old cache). The first zones on real data were 8 to 15 fringes in one 12-day pair, not physical for Morocco.
When enabled: `{enabled: true, label, schema: 2, zones: [{id, rank, lat, lon, area_km2, mean, peak, unit ("mm/yr" or "cm"), snr,
label: "unvalidated candidate", confidence: "low" (never high), alert_level: "yellow" (never orange or red), direction,
fringes (|cm| / 11.92, cm zones only), peak_fringes, coherence_mean, n_components, main_component_share, in_one_component,
in_frame_main_component, n_other_geometries_covering, other_geometries_showing[], second_geometry_shows (null = no other geometry
covers it), flags[] (why it is doubtful), exposure | null}], n_geometries, note}`.
`?refresh=true&exposure=false` recomputes (exposure needs internet).

Every payload now also has `mode`: `"off"` (default), `"single"` (the old mode above, `NISAR_DISCOVERIES_ENABLED=1`) or
`"consistent"` (the safe mode, `NISAR_DISCOVERIES_MODE=consistent`; still off unless set). The fields above are unchanged.
In **consistent** mode, per geometry and CRID, only **independent** pairs (no shared time interval) that pass the pair quality
filter are used, with the default corrections (ionosphere with its uncertainty mask). A zone is kept only if it is above
3 sigma after smoothing in **at least 3** of them, with the **same sign** in each (no pair beyond 2 sigma with the opposite
sign), and **no single pair holds more than half** of its motion. Extra fields: top level `n_geometries_with_enough_independent_pairs`,
`rejected_pairs[]` (see "Pair quality" above), `rules {min_independent_pairs: 3, sigma_after_smoothing: 3, same_sign: true,
opposite_sign_max_sigma: 2, max_single_pair_share: 0.5, corrections, quality_filter: true}`; per zone `mode: "consistent"`,
`unit: "cm"` (mean change per pair), `n_independent_pairs`, `n_pairs_detected`, `pairs_detected[]` (product ids),
`per_pair_mean_cm[]`, `same_sign`, `max_single_pair_share`. Every zone is still an **unvalidated candidate**: `confidence`
`"low"`, `alert_level` `"yellow"`, never higher. The mock (`?mock=true`) returns the consistent-mode shape.

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
