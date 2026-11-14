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

## Offline demo

The demo laptop needs neither the backend nor the internet once the build is made.

```
# with the backend running, after the last precompute
npm run snapshot          # records every response of the demo path into demo-data/ (checked by the contract)
npm run build:demo        # refuses to build while any case is a draft (CASE_CONTRACT.md, rule 5)
npm run preview:demo      # serves dist-demo/ on http://127.0.0.1:4311, no backend needed
```

- `npm run build:rehearsal` builds the same thing with the drafts kept, under a hatched "REHEARSAL, not for the
  jury" banner. It is for testing the offline path before the cases are final.
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
