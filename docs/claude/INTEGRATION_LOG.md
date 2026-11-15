# Integration log (2026-11-15)

Frontend v2 = `frontend-v2/` from origin/adam/frontend-v2 (author adambakhadi), merged into anass/cases after origin/main.

| # | check | result | cause / fix |
|---|---|---|---|
| 1 | merge conflict backend/cases/out/panama-2026.json and _fit.png | resolved | add/add; took main's generated files |
| 2 | review_cases: Haouz ERROR "km2 unit" | left as is | finding `open_water_change` (0.0014 ± 0.0075 km2, no_reference) comes from backend/water/haouz_open_water.py, a team decision; its text says no flooded area is claimed. Not hand-edited |
| 3 | npm ci + npm run build (frontend-v2, tsc + vite) | pass | none |
| 4 | /health, /api/cases (5 cases), /api/cases/<id> x5 via the v2 proxy :5310 | 200 | backend restarted after the merge; requests visible in uvicorn log |
| 5 | figure URLs of every case (7) | 200 | none |
| 6 | texts: Panama "sign not verified", "undecided"; Haouz "no flooded area is claimed"; Venezuela has no displacement finding | pass | none |
| 7 | npm test (frontend-v2) | 130/131 | 1 failure: investigator page recorded stream test, TypeError reading 'split' (frontend test, not fixed) |
| 8 | tools/frontend_contract validator | not run | targets frontend/ synthetic dump; time |
