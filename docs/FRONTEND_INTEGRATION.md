# Running the interface with the real backend

The interface lives in its own repo: https://github.com/houssam-bough/nasa-the-sar-front-end
It validates every response with its own contract (`src/api/contract.ts`). The backend serves that
contract under `/api` (`backend/api_v2.py`), next to the original routes, which are unchanged.
All 77 responses produced on synthetic data match the frontend schemas (see `tools/frontend_contract/`),
and the three demo questions were checked in the real interface in Chrome.

## Start both (two terminals)
```
# 1. backend, from NASA_SAR\backend
python -m uvicorn api:app --port 8000

# 2. frontend, from the frontend repo
npm install
npm run dev:api          # Vite proxies /api to http://127.0.0.1:8000
```
Open the address Vite prints (http://127.0.0.1:5173). Offline demo: set `NISAR_OFFLINE=1` before
starting the backend, and run `python precompute.py` first so the event answers are cached.

## What the adapter does
| frontend route | served from |
|---|---|
| `POST /api/ask` (SSE) | `agent.investigate`, then the steps, then the `Answer` |
| `GET /api/answers/{id}` | answers stored in `cache/answers_v2/`, event answers as `event-<id>` |
| `GET /api/library` | the Panama and Al Haouz flood events |
| `GET /api/demo` | every event, with its question in FR, EN and AR (offline replay) |
| `GET /api/discoveries` | 503 `discoveries_disabled` while discoveries are off (the default) |
| `/api/watches`, `/api/notifications` | watches and alerts (`POST /api/watches/check` re-runs them) |
| `POST /api/watches/{id}/simulate?level=orange` | demo only: an alert whose text says SIMULATION in every language |
| `GET /api/proofs/lband-vs-cband` | 404 `not_available`: not computed yet |
| `/api/layers/*.png` | map layers, coloured with the frontend palettes (`backend/palettes.json`) |

Verdicts, limits and some evidence use backend template ids (`backend.*`) with the text in FR, EN and AR;
the frontend shows that text because it does not know those ids. Numbers, confidence and alert levels are
the backend's, unchanged.

## Requests for the frontend (Houssam)
1. Add `surface_change` to the `Recipe` enum and to `term.recipe.*` in the three locales. Until then the
   adapter sends surface change as `damage`, which is the word Anass removed on purpose.
2. Show the 503 `discoveries_disabled` message as an information state on the home page, not as an error.
3. Hide or label the "Bande L / bande C" page: the backend answers 404 `not_available`.
4. `palettes.json` is copied into the backend: if you change a palette, copy the file again.
