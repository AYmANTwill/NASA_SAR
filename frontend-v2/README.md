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

## Checks

| command | what |
|---|---|
| `npm run typecheck` | TypeScript, strict |
| `npm run lint` | ESLint |
| `npm test` | unit and component tests (Vitest), including the contract copy check and token contrast |
| `npm run e2e` | Playwright with the installed Chrome, axe accessibility checks, screenshots in `e2e/__screenshots__/` |
| `npm run sync:contract` | copy `frontend/src/api/contract.ts` again when the team contract changes |

`src/api/contract.ts` is an exact copy of `frontend/src/api/contract.ts`; `npm test` fails if they differ.
