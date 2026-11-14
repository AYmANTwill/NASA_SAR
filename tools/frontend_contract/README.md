# Checking the backend against the frontend contract

The frontend (houssam-bough/nasa-the-sar-front-end) rejects any response that does not match its zod schemas
(`src/api/contract.ts`). This check runs every `/api` route on synthetic data and validates the responses with
those exact schemas.

```
cd backend
python tests/dump_frontend_contract.py ../contract_dump              # add "consistent" to test discoveries on
cd ../tools/frontend_contract
copy <frontend repo>\src\api\contract.ts .                          # cp on Linux/macOS
npm init -y && npm install zod@3.25.76 tsx
npx tsx validate.ts ../../contract_dump
```
Expected: `77/77 responses match the frontend contract`. Run it again whenever either side changes.
