# NISAR Pulse v2: build plan

Design: [DESIGN.md](DESIGN.md) (direction C "Evidence ledger", IBM Plex, light only).
Every step below runs against the real backend on `127.0.0.1:8000` before it is called done.

## 1. Stack

| piece | choice | why |
|---|---|---|
| build | Vite 6, React 18, TypeScript 5.7 (strict) | same as `frontend/`: the API layer and the team's knowledge carry over |
| data | TanStack Query 5, zod 3.25 (same major as `frontend/`) | caching, retries, abort; zod is required by the contract |
| routing | react-router 6, language in the URL (`/fr/…`, `/en/…`, `/ar/…`) | shareable links in one language; e2e tests address each language directly |
| i18n | i18next + react-i18next | same template catalogue mechanism as `frontend/` (`tpl`, `term`) |
| map | maplibre-gl 5, bundled `world-atlas` land and borders, online vector detail only when reachable | works offline; image sources for the API's PNG layers |
| charts | hand-written SVG (comparison strip, pass timeline, series) | three small, specific charts; full control of RTL, labels and accessibility; no chart library |
| style | plain CSS with custom-property tokens and logical properties, one file per component | hue-less chrome needs few rules; no Tailwind or shadcn defaults to fight |
| fonts | `@fontsource/ibm-plex-sans`, `@fontsource/ibm-plex-sans-arabic` | self-hosted, offline |
| tests | Vitest + Testing Library, Playwright + `@axe-core/playwright` | unit, component, e2e and accessibility in CI |

All dependencies in `frontend-v2/package.json`, nothing global.

## 2. The contract, kept identical

- `src/api/contract.ts` is a **byte-for-byte copy** of `frontend/src/api/contract.ts`.
- `src/api/contract.sync.test.ts` reads both files and fails if they differ (it prints the diff).
- `npm run sync:contract` copies the file again, for when the source changes.
- Why a copy, not an import: importing across project roots makes `zod` resolve from `frontend/node_modules`, so
  `frontend-v2` would break whenever `frontend/` has not run `npm ci`.

## 3. Data flow

```
backend /api/*  ──fetch──▶  api/http.ts  ──zod parse──▶  typed value  ──TanStack Query──▶  components
                                   │                        │
                       network down: OfflineError     mismatch: ContractError(endpoint, issues)
                       4xx/5xx: ApiError(code, TemplatedText)
```

- Components never call `fetch`. One `ApiClient` interface, two implementations: `http` (live backend) and `replay`
  (recorded snapshot, for the offline demo build). Both validate with the same schemas.
- `/api/ask` is read as a `text/event-stream` from a POST (`step`, `answer` and `error` events). Each `step` is parsed
  as it arrives and shown live; the final `answer` is parsed before anything of it is shown.
- A `ContractError` renders as an explicit error panel: which endpoint, which fields, and "this response was not
  shown because it does not match the contract". The data is never patched or partly shown.
- Information states, not errors: 503 `discoveries_disabled`, 404 `not_available` (L-band proof).

## 4. Display rules (one module, `src/science/`, unit-tested)

These are the only places where the interface decides how a value looks. None of them creates a number.

| rule | behaviour |
|---|---|
| `MeasurementView` | `value ± uncertainty unit`, numbers formatted per language and isolated LTR. Source link next to it when the API gives one. |
| placeholder | in a `draft` case, a NISAR value with `uncertainty: 0` is a placeholder: "not measured yet", hatched, and its agreement badge is hidden |
| exact value | in a `final` case (or an answer), `uncertainty: 0` is shown as the value with an "exact count / no σ given" label (Ayman's `value_only()`) |
| agreement | the API's word plus a shape, never a colour; never recomputed (the zod schema rejects a wrong one) |
| comparison strip | marks at the API's values, extents at the API's ±σ × `sigma`; **no axis tick labels**, because ticks would be numbers the interface computed |
| limits | rendered on every case and answer, never collapsible |
| status | `draft` → DRAFT band and browser title prefix; a demo build refuses to show a draft |

## 5. Pages and components

Order of build = order of demo importance.

| route | page | main components |
|---|---|---|
| `/:lang/` | **Cases** (home) | `CaseCard` (thumbnail or map extent, title, date, kind, status) ×4 |
| `/:lang/cases/:id` | **Case view** | `CaseHeader` (title, date, place, status, DRAFT band) · `RadarMap` + `RasterLegend` · `PassTimeline` · `Ledger`: `Headline`, `FindingStrip` ×n, `ExposureTable`, `FigureList`, `Limits`, `Sources` |
| `/:lang/cases/:id/sheet` | **Map sheet** (print / export) | same data, laid out as a map frame + marginalia, `@media print` |
| `/:lang/ask` | **Investigator** | `AskBox` (question, optional point on the map) · `LiveSteps` (SSE) · `AnswerLedger`: verdict, confidence, metrics, series, checks, evidence, limits |
| `/:lang/answers/:id` | **Answer** | `AnswerLedger` with its map and series |
| `/:lang/library` | **Library** | precomputed events → their answers |
| `/:lang/watches` | **Watches** | watch list, next pass, notifications; create from an answer |
| `/:lang/about` | **Status** | backend health, discoveries and L-band proof as information states, data sources, AI-use note link |

Shared: `AppShell` (language switch, offline indicator, presentation mode `P`), `ErrorPanel`
(`ApiError` / `ContractError` / `OfflineError`), `NotMeasured`, `SourceLink`, `TemplatedTextView`.

## 6. Build steps

Each step ends runnable against the backend, with its tests green, and is one or a few commits.

| # | step | done when |
|---|---|---|
| 0 | Scaffold: Vite app, tokens, fonts, i18n FR/EN/AR with `dir` switching, routing, `AppShell`, lint, Vitest, Playwright config, `sync:contract` + sync test | `npm run dev` shows the shell in 3 languages; typecheck, lint, test green |
| 1 | API layer: copied contract, `http` client, SSE reader, error classes, query hooks, `ErrorPanel` | unit tests on every error path; live `/api/cases` and `/api/health` parsed |
| 2 | **Cases list** | four drafts from the backend, DRAFT shown, keyboard-navigable |
| 3 | **Case view: ledger** (header, headline, findings with strips, placeholder state, exposure, limits, sources) | Panama draft shows "not measured yet", not "disagree"; limits visible in 3 languages |
| 4 | **Case view: map + legend + pass timeline** | layer PNG placed at its bounds with the canonical palette legend; timeline from `timeline[]`; empty states while drafts have no figure |
| 5 | **Investigator**: ask box, live SSE steps, answer ledger, map layers, series chart | a real question streams steps and shows an answer with its limits; contract errors shown |
| 6 | Answers, library, watches, status page | each reads the real API; 503/404 information states |
| 7 | **Offline demo**: `npm run snapshot` records live responses into `demo-data/` (zod-validated, figures and layers copied), `build:demo` serves them through the `replay` client and **fails on any draft** | the demo build runs with the backend stopped and the network off |
| 8 | Map sheet / print view, presentation mode | prints on A4 / A3 landscape with legend and limits |
| 9 | Polish pass: screenshots in FR/EN/AR at 1440, 1024 and 390 px, fix what looks wrong | reviewed by eye, then the review gate below |

## 7. Tests

| level | what | tool |
|---|---|---|
| contract | copy identical to `frontend/`; every recorded backend response parses | Vitest |
| display rules | placeholder vs exact vs measured; strip extents; no number rendered that is not in the input (property test: every digit run in the output appears in the API payload) | Vitest |
| components | ledger, strip, timeline, error panels, in 3 languages, with RTL | Vitest + Testing Library |
| e2e live | every screen in FR / EN / AR against the running backend: cases → case → ask → answer → watch | Playwright (backend started by the config, or skipped with a clear message if it cannot start) |
| e2e demo | demo build, backend stopped, network blocked: the demo path works; a snapshot with a draft makes the build fail | Playwright |
| accessibility | axe on every screen in every language; keyboard-only path through the demo; focus visible | `@axe-core/playwright` |
| visual | screenshots per screen × language × width, looked at by eye before each PR | Playwright |

Test fixtures are recorded from the backend (`snapshot`) or produced by the backend's own scripts
(`backend/tests/dump_*_contract.py`), never typed by hand.

## 8. Review and PR gate

Before each PR to `main`: typecheck, lint, unit, e2e live, e2e demo and axe green; screenshots reviewed;
`/code-review` run on the diff and its findings fixed or answered; then a 5-line status (works on real data /
placeholder / next). Ayman merges.

## 9. Already known for `API_REQUESTS.md` (for Ayman)

1. Draft placeholders are sent as `{value: 0, uncertainty: 0}` and Panama's placeholder Mw gets
   `agreement: "disagree"` against USGS 7.7. Request: a way to mark a placeholder in the public payload (for example
   `nisar: null` in drafts, or a `placeholder: true` flag), so the interface does not have to infer it from
   `status` + `uncertainty: 0`.
2. `CaseSummary` has no `location` / `bbox`: the case list cannot frame a map thumbnail without fetching each case.
   Request: `bbox` in the summary (or `thumbnail_url` filled).
3. `timeline[]` items have no type (event / acquisition / publication): the pass timeline can only show labels.
   Request: a `kind` per item.
