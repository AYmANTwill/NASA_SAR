# NISAR Pulse: the radar investigator

Ask a question about any place in French, Arabic or English. NISAR Pulse answers with what the NISAR L-band radar measured, its uncertainty, independent evidence, and what the radar cannot tell. It can then watch the place on every new pass.

This repository is the **frontend** (React 18, Vite, TypeScript, Tailwind v4 + shadcn/ui, TanStack Query, i18next, MapLibre, Recharts). It is ready to connect to the FastAPI backend: see [docs/API_CONTRACT.md](docs/API_CONTRACT.md).

> Until the backend exists, `npm run dev` serves **synthetic fixtures** (`src/__fixtures__/`) with a permanent "test data" banner. No fixture value is a NISAR measurement.

## Run

Requires Node 22+.

```bash
npm install
npm run dev          # fixtures mode, http://127.0.0.1:5173
npm run dev:api      # http mode: proxies /api to FastAPI on http://127.0.0.1:8000
```

## Offline demo

```bash
npm run build:demo && npm run preview:demo   # fixtures build with service worker, http://127.0.0.1:4173
npm run build && npm run preview             # http build (needs the API), http://127.0.0.1:4174
```

Open the app once while online. The service worker precaches the app, fonts and map basemap (Natural Earth borders, bundled). In http mode the app also downloads every precomputed answer listed by `/api/demo`. Then cut the network: the demo path still works, a discreet "Offline" indicator appears, and the map falls back to the bundled basemap.

## Rehearse the jury demo

```bash
npm run e2e:demo     # replays Panama → discoveries → Al Wahda → watch → L/C proof → live SME2, timed
```

## Checks

```bash
npm run typecheck        # tsc --noEmit
npm run lint             # eslint
npm test                 # vitest: formatting, contract vs fixtures, i18n parity, template catalog
npm run check:numbers    # no hard-coded user-facing numbers in src/
npm run check:contrast   # WCAG AA on design-token pairs
npm run e2e              # Playwright: demo, offline, http adapter (SSE, contract errors), axe a11y × 3 languages
SCREENSHOTS=1 npx playwright test e2e/screens.spec.ts --project=demo   # docs/screenshots
```

Playwright uses the installed Google Chrome (`channel: "chrome"`).

## Layout

| Path | Role |
|---|---|
| `src/api/contract.ts` | zod schemas: the API contract (source of truth) |
| `src/api/http.ts`, `sse.ts` | FastAPI client, agent steps over SSE |
| `src/api/fixtures.ts`, `src/__fixtures__/` | synthetic data adapter (dev only, lazy chunk) |
| `src/api/queries.ts` | TanStack Query hooks, persisted cache, offline replay |
| `src/i18n/` | FR / AR / EN, template catalog (`tpl`), RTL handling |
| `src/components/map/` | MapLibre map, offline basemap, legend, palettes |
| `src/components/science/` | measurement ±, noise ruler, confidence & level badges, time series |
| `src/features/` | screens: discover, investigate, watch, library, proof |
| `src/design/palettes.json` | canonical raster palettes (shared with the backend) |
| `PRODUCT.md` | audience, voice, product rules, tokens |
| `docs/frontend-report.md` | what was done, what is still imperfect |
