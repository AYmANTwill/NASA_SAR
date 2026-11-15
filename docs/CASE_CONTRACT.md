# CaseStudy contract

Frozen Saturday 14 Nov 2026, 16:00. Changes after the freeze need both Ayman and Houssam.

The case studies of NISAR Pulse (four, plus an optional fifth) are served by the backend under `/api/cases`. Each one is a measured result
with its uncertainty and, where one exists, an independent reference.

Sources of truth:
- backend: `backend/science/case_models.py` (pydantic). It refuses any case that breaks the rules below.
- frontend: `tools/frontend_contract/case_contract.ts` (zod). It is ready to paste into `src/api/contract.ts`.

`TemplatedText`, `Measurement`, `Bounds` and `RasterLayer` are the existing types of the frontend's
`src/api/contract.ts`. `Layer` below means `RasterLayer`.

## Endpoints

```
GET /api/cases        -> CaseSummary[]   (fixed order: panama, venezuela, haouz, ionosphere)
GET /api/cases/{id}   -> CaseStudy       404 ApiErrorBody {code: "case_not_found"}
                                         500 ApiErrorBody {code: "case_invalid"} if the file on the server is broken
```

## Types

```
CaseSummary { id, kind, title: {fr,en,ar}, date: ISO UTC, status, thumbnail_url: string | null,
              bbox?: [w,s,e,n], place?: {fr,en,ar} }        // optional: the case's map extent and place

CaseStudy {
  id: "panama-2026" | "venezuela-2026" | "haouz-flood-2026" | "ionosphere-gps"
  kind: "earthquake" | "flood" | "method"
  status: "draft" | "final"
  title: {fr,en,ar}
  date: ISO UTC date-time ("2026-10-09T17:56:06Z")
  location: { lat, lon, bbox: [w,s,e,n], place: {fr,en,ar} }
  headline: TemplatedText
  findings: [{ id, label: {fr,en,ar}, nisar: Measurement, reference: Measurement | null,
               reference_source: {name, url} | null,
               agreement: "agree" | "partial" | "disagree" | "no_reference" }]
  figures: [{ id, kind: "map" | "chart" | "image", title: {fr,en,ar}, url, caption: TemplatedText, layer?: Layer }]
  exposure: { people: Measurement, buildings: Measurement, area_km2: Measurement, source: {name, url} } | null
  timeline: [{ label: {fr,en,ar}, at: ISO UTC, kind?: "event" | "acquisition" | "publication" }]
  answer_ids: string[]
  limits: TemplatedText[]          // at least one
}
```

The id fixes the kind: `panama-2026` and `venezuela-2026` are `earthquake`, `haouz-flood-2026` is `flood`, and
`ionosphere-gps` and `bin-el-ouidane-2026` are `method`.

`bin-el-ouidane-2026` (Youkaoui, `backend/water/`) is optional: it is served only when `backend/water/outputs/reservoir_case.json` exists (a full CaseStudy, same rules). Its images, and those of `haouz_open_water.json` (findings "persistent open water (U-Net)" added to the Haouz case), are served at `GET /api/water/rasters/{file}` and `GET /api/water/figures/{file}` (png / jpg / webp, same path checks as case figures). The package writes urls as `water/outputs/<figures|rasters>/<file>` (relative to
`backend/`); the loader maps them to `/api/water/...`. `GET /api/water/raster-index` returns
`outputs/raster_index.json` (every RGBA PNG layer of the package, EPSG:4326, `[west, south, east, north]`; images, not `RasterLayer`).
`backend/water/` is vendored from Youkaoui's `nisar-water` package and never edited here.

Each raster-index layer also has `role`: `"background"` for `optical_before` / `optical_after` (optical 2026 images, drawn under the water layers instead of the default basemap), `"overlay"` for the water layers, unless the package gives one. A water file that breaks its format never stops the API: in production the 5th case, the Haouz water extras or the raster index are skipped with a logged warning (raster index: 404 `water_not_found`); with `NISAR_WATER_STRICT=1` (the tests) it raises.

A case with no finding is served with the headline `backend.case_in_progress` ("En cours : aucune mesure de cette étude n'est encore calculée."), status `draft`, no finding, so no value and no agreement badge. `results/panama-2026/limits_panama.json` (`{"limits": [{fr, en, ar}]}`, Anass) is appended to the Panama limits as given; absent or malformed: ignored with a warning.

### New Measurement units

`Measurement.unit` gains `"Mw"`, `"people"`, `"count"` and `"deg"`. `"mm"` is already in the enum. Until the
frontend adds them, `case_contract.ts` uses `CaseMeasurement`, which is `Measurement` with the extended unit list.
Exposure units are fixed: `people` is in `people`, `buildings` in `count`, `area_km2` in `km2`.

### Optional keys

`figure.layer` and `TemplatedText.text` are left out when there is no value. They are never `null`.
`reference`, `reference_source` and `exposure` are always present and may be `null`.

## Rules

1. **Agreement is computed, never typed by hand.** σ is the 1-sigma uncertainty (`uncertainty / sigma`), and
   `S = sqrt(σn² + σr²)`:
   - `agree` if |nisar − reference| ≤ 2·S
   - `partial` if |nisar − reference| ≤ 4·S
   - `disagree` otherwise
   - `no_reference` if `reference` is null

   The units must be the same. Both validators recompute the agreement and reject a case where it differs.
2. A `reference` always comes with its `reference_source`, and the reverse.
3. Every case has at least one `limits` item: what the radar cannot tell here.
4. **Draft or final.**
   - `draft` cases may hold placeholder values. They are listed in the backend-only key `placeholders`, as JSON
     paths. The frontend ignores this key.
   - A case can only be `final` when `placeholders` is empty, it has at least one finding, and every NISAR value has
     a non-zero uncertainty.
   - The four cases are drafts until `backend/science/cases.py` writes them from real outputs.
5. **Demo gate.** `NISAR_DEMO=1 npx tsx validate.ts <dump>` fails on any `draft` case, so the demo cannot ship with
   one.

## Inputs for `science/cases.py`

`python -m science.cases` builds the four cases. Anything missing is listed in `placeholders`, and the case stays a
`draft`. Run it with `--dry-run` to see what is missing without writing anything.

| case | inputs |
|---|---|
| panama-2026 | `backend/cases/out/panama-2026.json` + `_fit.png` (`python -m science.panama_fault`); `backend/cases/out/panama-2026_exposure.json` (`python -m science.exposure_run --case panama-2026 --event us6000u18k --iso3 PAN`); USGS event; co-seismic pairs in the catalog |
| venezuela-2026 | `results/venezuela-2026/findings.json` (UCSD comparison); `--venezuela-event <USGS id>`; exposure via `exposure_run --event <id> --iso3 VEN` |
| haouz-flood-2026 | a candidate surface-change area, not a flood map (`science/haouz_case.py`): `results/haouz-flood-2026/findings.json` with `coherence_loss_excess` (unit `coherence`) and `backscatter_change` (unit `dB`), each as `nisar` = the change at the site ± its standard error (effective number of looks), `reference` = the no-event baseline (mean of the random circles ± their spread, sigma 1), `reference_source` = {name: "No-event baseline: 2,000 random circles, …", url}, agreement by the rule; plus `date`, `products` and a backscatter-change raster. `results/events/haouz-flood-2026-10-10.json` (passes, dates, CRID) and `results/events/haouz-soil-moisture.json` (anomaly ± uncertainty). No `flooded_area`, no km², no exposure |
| ionosphere-gps | `results/gps/gps_none/gps_*.json` and `results/gps/gps_iono/gps_*.json` (`validate_gps.py` without / with the ionospheric correction); optional `results/noise_with_without_iono_*.csv` (one row per pair: `track,frame,direction,ref,sec,sigma_raw_cm,sigma_minus_iono_cm,sigma_plus_iono_cm,…,valid_px`) for the before / after noise chart, a final file preferred to a `preliminary` one |

`results/<id>/findings.json`, written by Anass:

```
{
  "findings": [Finding, ...],                  // exactly the Finding of this contract, agreement computed by the rule
  "figures":  [
    { "id", "kind": "image"|"chart", "title": {fr,en,ar}, "file": "name.png", "caption": TemplatedText },
    { "id", "title": {fr,en,ar}, "caption": TemplatedText, "raster": "name.tif",      // a map: rendered by cases.py
      "layer": { "kind", "unit", "palette", "min", "max", "period"?: {start,end}, "source"?, "sign_convention"? } }
  ],
  "limits":   [{fr,en,ar}, ...],
  "products": ["<catalog product id>", ...],   // the NISAR products used: their acquisition times + ASF dates make the timeline
  "date": ISO UTC, "bbox"?: [w,s,e,n]          // event date (flood case); bbox defaults to the products' extent
}
```

- Every case needs at least one **map** (a figure with a `layer`) and a **full timeline**: the event, every NISAR
  acquisition time of the products (from their names), and each product's ASF publication date (`processingDate`).
  Without them the case stays a draft.
- Earthquake maps (the LOS displacement of each co-seismic pair) and the ionosphere map are rendered by `cases.py`
  itself.
- Map layers use the frontend palettes (`backend/palettes.json`) and the kinds and units of `RasterLayer`. A flood
  map should be a backscatter-change raster (`kind: "backscatter_change"`, `unit: "dB"`), not the 0/1 mask.
- Figure files and rasters sit next to `findings.json`. The PNGs are copied or rendered into
  `backend/cases/figures/<id>/` and served at `GET /api/cases/{id}/figures/{file}`.
- Panama's line-of-sight sign verdict (`sign_check` in `cases/out/panama-2026.json`, rule of
  `science/sign_decision.py`) becomes a `limits` item with its track counts and variance reductions. A decided sign
  opposite to the `NISAR_LOS_SIGN` of the run keeps the case a draft until panama_fault is rerun with that sign.
- A file that breaks this format stops the build with an error. It is never patched silently.

## Checking

From `backend/`:

```
python tests/test_science.py                                   # contract rules + routes
python tests/dump_frontend_contract.py ../contract_dump        # existing /api routes
python tests/dump_cases_contract.py ../contract_dump           # /api/cases
```

Then in `tools/frontend_contract/`, with `contract.ts` copied from the frontend repo:

```
npx tsx validate.ts ../../contract_dump                        # every response
set NISAR_DEMO=1 && npx tsx validate.ts ../../contract_dump    # demo build; bash: NISAR_DEMO=1 npx tsx ...
```
