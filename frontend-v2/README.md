# NISAR Pulse v2 interface

A second, independent interface for NISAR Pulse (Adam). Design: [DESIGN.md](DESIGN.md). Plan and progress:
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
| `npm run sync:contract` | copy `frontend/src/api/contract.ts` and `backend/palettes.json` again when they change |
| `npm run snapshot` | record the live backend for the offline demo |

`src/api/contract.ts` and `src/design/palettes.json` are exact copies of the team's files; `npm test` fails if they
differ.
