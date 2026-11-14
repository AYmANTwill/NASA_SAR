# Checking the backend against the frontend contract

The frontend (houssam-bough/nasa-the-sar-front-end) rejects any response that does not match its zod schemas
(`src/api/contract.ts`). This check runs every `/api` route on synthetic data and validates the responses with
those exact schemas. The case studies (`/api/cases`, docs/CASE_CONTRACT.md) are validated with `case_contract.ts`,
which builds on `contract.ts`.

```
cd backend
python tests/dump_frontend_contract.py ../contract_dump              # add "consistent" to test discoveries on
python tests/dump_cases_contract.py ../contract_dump
cd ../tools/frontend_contract
copy <frontend repo>\src\api\contract.ts .                          # cp on Linux/macOS
npm init -y && npm install zod@3.25.76 tsx
npx tsx validate.ts ../../contract_dump
```
Expected: `83/83 responses match the frontend contract`. Run it again whenever either side changes.

Demo build: with `NISAR_DEMO=1` set, the check also fails on any case whose `status` is still `draft`
(PowerShell: `$env:NISAR_DEMO = "1"`).
