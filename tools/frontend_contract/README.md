# Checking the backend against the frontend contract

The frontend (`frontend/`) rejects any response that does not match its zod schemas (`frontend/src/api/contract.ts`).
This check runs every `/api` route on synthetic data and validates the responses with those exact schemas.

The case studies (`/api/cases`) are checked twice:
- against the frontend's own `CaseStudy`, which is what the interface accepts;
- against `case_contract.ts`, the rules of docs/CASE_CONTRACT.md (computed agreement, units, ISO UTC dates).

```
cd backend
python tests/dump_frontend_contract.py ../contract_dump              # add "consistent" to test discoveries on
python tests/dump_cases_contract.py ../contract_dump
cd ../tools/frontend_contract
copy ..\..\frontend\src\api\contract.ts .                           # cp on Linux/macOS (copy, do not edit)
npm init -y && npm install zod@3.25.76 tsx
npx tsx validate.ts ../../contract_dump
```
Expected: `83/83 responses match the frontend contract`. Run it again whenever either side changes.

Demo build: with `NISAR_DEMO=1` set, the check also fails on any case whose `status` is still `draft`
(PowerShell: `$env:NISAR_DEMO = "1"`).
