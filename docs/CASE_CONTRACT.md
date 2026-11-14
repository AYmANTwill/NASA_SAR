# CaseStudy contract

Frozen Saturday 14 Nov 2026, 16:00. Changes after the freeze need both Ayman and Houssam.

The four case studies of NISAR Pulse are served by the backend under `/api/cases`. Each one is a measured result
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
CaseSummary { id, kind, title: {fr,en,ar}, date: ISO UTC, status, thumbnail_url: string | null }

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
  timeline: [{ label: {fr,en,ar}, at: ISO UTC }]
  answer_ids: string[]
  limits: TemplatedText[]          // at least one
}
```

The id fixes the kind: `panama-2026` and `venezuela-2026` are `earthquake`, `haouz-flood-2026` is `flood`, and
`ionosphere-gps` is `method`.

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
