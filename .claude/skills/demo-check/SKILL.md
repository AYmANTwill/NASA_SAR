---
name: demo-check
description: Go / no-go checklist before presenting NISAR Pulse to judges. Checks tests, secrets, cached demo answers, data provenance, sign verification and offline readiness. Run only when the user types /demo-check.
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash(git status *), Bash(git log *), Bash(git grep *), Bash(git ls-files *), Bash(python tests/test_all.py), Bash(python backend/tests/test_all.py)
---

# Demo check

Check each item, then print one table: item · ✅ / ⚠️ / ⛔ · evidence · fix. Do not run downloads or
`precompute.py`; give the user the command instead.

1. Tests: `python tests/test_all.py` from `backend/` passes.
2. No credential in tracked files: `git grep -n -I "eyJ"` and `git grep -n "EARTHDATA_TOKEN ="`
   (report file:line only). STATUS.md confirms the old token was revoked.
3. Working tree clean, or only intended changes; the demo commit is known (`git log -1`).
4. `backend/cache/events/*.json` exist, are newer than the last recipe change, contain no
   `"mock": true`, and their `data_used` ids look like real products whose dates match the story.
5. LOS sign verified on real Panama data (STATUS.md). If not: ⛔ for any displacement claim.
6. The hero question returns the expected type, a straddling pair and a sensible verdict.
7. Offline rehearsal written out for the user (PowerShell):
   `$env:NISAR_OFFLINE="1"; cd backend; python -m uvicorn api:app --port 8000`, the UI works
   without internet (basemap cached, or a recorded video as fallback).
8. Every mock, synthetic or provisional output is visibly labelled in the UI.
9. Numbers in the pitch match the cached answers exactly (no hand-typed figures).

Verdict: **GO** only if there is no ⛔.
