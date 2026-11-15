# NISAR Pulse v2 interface

A second, independent interface for NISAR Pulse (Adam). Current visual direction and feature parity:
[PARITY.md](PARITY.md). Scientific design principles: [DESIGN.md](DESIGN.md). Plan and progress:
[PLAN.md](PLAN.md). What the interface needs from the backend: [API_REQUESTS.md](API_REQUESTS.md).

## Run it

Two terminals, from the repo root:

```
# 1. backend on 127.0.0.1:8000
cd backend
python -m uvicorn api:app --host 127.0.0.1 --port 8000

# 2. this interface on 127.0.0.1:5310 (/api is proxied to the backend; VITE_API_PROXY overrides it)
cd frontend-v2
npm ci
npm run dev
```

Open http://127.0.0.1:5310. The language is in the address: `/fr/`, `/en/`, `/ar/`.

V2 includes the first interface's discovery, investigation, library, watches and L/C comparison pages, alongside
the case ledger and service status. The workspace uses a dark navigation column on desktop and a collapsible
menu on phones. Every page supports FR/EN/AR, including mirrored Arabic layouts. Figures open in a keyboard
accessible viewer. Map tools include recentering, full screen, image visibility, opacity and earthquake markers.
Reports can be printed to PDF or exported as API JSON; presentation mode is available from the menu or with `P`.

`/discover` shows the API's ranked candidates and exposure sort when enabled, or observed library locations when
the backend explicitly disables discovery. `/proof` keeps the explanatory L/C diagram visible when the real
comparison is unavailable; actual coherence maps, forest bins, sources and limits appear only when the API supplies
them. Synthetic UI scenarios live only in tests. Legacy links such as `/investigate/:id` and `/watch` redirect to V2.

The case list uses optional summary bounds and place names, with a detail fallback for older backends. Timeline
kinds separate events, acquisitions and publications; dates without a kind remain unclassified.

The optional Bin El Ouidane method case keeps its four figures in the ledger. Its before/after/change RGBA PNGs
from `/api/water/raster-index` can be selected on the map at their API bounds. They are image overlays: no
`RasterLayer` palette or legend is fabricated. A missing endpoint leaves the figures and case available.

Haouz agreement with a "No-event baseline" is explained under the badge as not different from no change.
Persistent open water (U-Net) is never described as flood detection.

The water model's validation score is the API finding `heldout_iou`, with its API uncertainty and unit. Its note
explains that the evaluation tracks were never used for model tuning. No selection score is substituted if this
finding is absent. Haouz `open_water_change` explicitly reads "no clear change in open water" with the neutral
`no_reference` badge; an agreement without a reference is rejected by the contract.

## Offline demo

### MVP with the published results

`main` includes Anass's Haouz indicators, Panama sign/inversion checks and a preliminary ionosphere noise report.
Assemble their API case files without rerunning the scientific processing, from the repository root:

```powershell
.venv/Scripts/python.exe tools/prepare_frontend_mvp.py --panama-preview
```

The Panama preview is the documented **+1 sensitivity run**, which is unstable and supplies no magnitude finding.
Its figure is exploratory; Anass's inconclusive sign decision and limitations remain visible. The script preserves
any different existing inversion input. Haouz findings retain their API labels, including the distinction between
the null-distribution spread and measurement error. Missing raw products, GPS and exposure keep the affected
cases in draft. They must not be promoted to final to make a jury build pass.

The water v3 index supplies optical backgrounds and water overlays with explicit roles. Selecting before/after
uses the matching optical date under the radar image; change uses its period end. The background can be hidden.
Older three-image indexes and unavailable optional endpoints still work. The held-out model score remains read
from `heldout_iou`; the separate unseen-reservoir metric retains its API label and uncertainty.

For the current draft-labelled standalone MVP, use `npm run snapshot`, `npm run build:rehearsal`, then
`npm run preview:rehearsal` (port 4312). For the team's final-only demo, use `npm run snapshot:final`, then
`npm run build:demo` and `npm run package:mvp -- --demo`. Drafts are omitted, never promoted. A snapshot which
includes drafts still fails the jury build. The live interface and the rehearsal retain Anass's in-progress cases.

The normal production build (`npm run build`, then `npm run preview`) also retains its app shell, validated
responses and images for reports already opened. Demo answers are prepared automatically from `/api/demo`.
Saved API responses and report images expire after a week; health and write actions are never replayed. On a
first visit, report images are saved once the service worker takes control. The offline indicator identifies
saved data. Development keeps the response cache but does not register a service worker.

The demo laptop needs neither the backend nor the internet once the build is made.

```
# with the backend running, after the last precompute
npm run snapshot          # records every response of the demo path into demo-data/ (checked by the contract)
npm run build:demo        # refuses to build while any case is a draft (CASE_CONTRACT.md, rule 5)
npm run preview:demo      # serves dist-demo/ on http://127.0.0.1:4311, no backend needed
```

- `npm run build:rehearsal` (into `dist-rehearsal/`, served by `npm run preview:rehearsal` on port 4312) keeps the
  drafts, under a hatched "REHEARSAL, not for the jury" banner. It is for testing the offline path before the cases
  are final, and it can never overwrite the jury build in `dist-demo/`.
- If a snapshot fails (backend down, a response breaking the contract, an image missing), the previous snapshot is
  kept unchanged.
- When available, the water image index and its PNGs are recorded too. Older snapshots without that optional
  endpoint still replay the case and its figures.
- The demo answers the demonstration questions of `GET /api/demo` (in FR, EN and AR, matched without case, accents
  or punctuation) and shows every recorded page. Anything else says "not available in the offline demo". It never
  creates or changes a watch.
- `demo-data/` and `dist-demo/` are not committed: make them on the demo laptop.

## Checks

| command | what |
|---|---|
| `npm run typecheck` | TypeScript, strict |
| `npm run lint` | ESLint |
| `npm test` | unit and component tests (Vitest): contract and palette copies, recorded live responses, token contrast, no number typed in interface strings |
| `npm run e2e` | Playwright on the live backend with the installed Chrome, axe accessibility checks, screenshots in `e2e/__screenshots__/` |
| `npm run e2e:demo` | the rehearsal build of the last snapshot, with every request outside the demo server blocked |
| `npm run e2e:offline` | normal production build: first visit, network loss, reload, figures, Arabic navigation and a prepared answer (run `npm run build` first) |
| `npm run sync:contract` | copy `frontend/src/api/contract.ts` and `backend/palettes.json` again when they change |
| `npm run snapshot` | record the live backend for the offline demo |

`src/api/contract.ts` and `src/design/palettes.json` are exact copies of the team's files; `npm test` fails if they
differ.
