# NISAR Pulse — instructions for Claude Code

Hackathon project (NASA Space Apps 2026, "Dancing with the SARs", 14–15 Nov 2026, team The SAR,
Ben Guerir). A FastAPI backend answers questions about a place with NISAR radar data. Numbers come
from deterministic recipes; text is written from those numbers.

## Where things are
- `download_all.py` + `plan_nisar.json`: standalone downloader → writes `data/` (git-ignored).
- `backend/`: FastAPI service. Entry `api.py`; brain `agent.py`; maths `recipes/*.py`;
  index `catalog.py`; geometry and PNGs `raster.py`; confidence `uncertainty.py`; outside sources `evidence.py`.
- `PROJECT_DEEP_DIVE.md`: 200 KB reference of every file and function. **Never read it whole.**
  `grep -n "^### 4\." PROJECT_DEEP_DIVE.md` to find a chapter, then read that range. The code wins
  when the two disagree.
- `docs/claude/STATUS.md` (where we are), `DECISIONS.md` (why), `SESSIONS.md` (log).

## Hard rules
1. **Never commit.** Do not run `git commit`, `push`, `merge`, `rebase`, `pull`, `tag`, `revert`,
   `cherry-pick`, `reset --hard/--soft`, `clean -f`, or `gh pr create/merge`. A hook blocks them; if
   one is blocked, do not retry another way. Stage files only if the user asks. When work is ready,
   give the user an explicit `git add <files>` list and a commit message to run themselves.
2. **Secrets.** Never print, copy, log or move the Earthdata token, `.earthdata_token`, `.env`,
   `ANTHROPIC_API_KEY` or `FIRMS_MAP_KEY`. If you see a credential in code, report its file:line only.
3. **Data.** Do not edit `plan_nisar.json`, do not run `download_all.py build-plan`, and ask before
   any download, `precompute.py`, or deleting files in `data/` or `backend/cache/`.
4. **Tests before "done".** After code changes, run `python tests/test_all.py` from `backend/` and
   report the count. Passing synthetic tests do not prove the physics is right; say so when relevant.
5. **Ask when unsure** about scope, science or a destructive step. One question, then continue.

## Science invariants (use the `science-check` skill when touching numbers)
- No language-model number in a verdict: every number must exist in the recipe facts.
- Phase → LOS: `d_cm = LOS_SIGN · (−λ/4π) · φ · 100`, λ = 0.2384 m. `LOS_SIGN` is unverified until
  STATUS.md says it was checked on real Panama data.
- An event answer must use pairs that straddle the exact event time. No silent fallback.
- LOS is not vertical. Decomposition assumes no north–south motion and the same period.
- Label provenance everywhere: real, cached-real, synthetic, mock. SME2 is provisional.

## Code conventions
- Run backend commands from `backend/`: modules import each other by bare name (`import catalog`).
- `config.py` reads env vars at import; set them before importing or restart uvicorn.
- Recipe contract: return a plain dict of rounded facts (NaN → `None`) or `{"error": "..."}`.
  No HTTP, no sentences in recipes.
- Renaming a fact key means updating `agent.template`, `template_ar`, `assess`, `mock.py` and
  `docs/API_CONTRACT.md`. A new question type needs all four sentence tables.
- Keep each file's language: downloader messages in French, backend in English, answers fr/en/ar.
- The team uses Windows + PowerShell + VS Code: give PowerShell syntax (`$env:NISAR_OFFLINE="1"`).
- Small, reviewable changes. No new dependency without asking; add it to `requirements.txt`.

## Workflow
- `/start-session [goal]` → load status, git state, agree a plan.
- `/explain <target>` → plain explanation of code, concept or error. Read-only.
- `/decision <topic>` → compare options or record a decision in `DECISIONS.md`.
- `/review-commit` → check the diff before the user commits. Read-only.
- `/demo-check` → go/no-go list before presenting.
- `/end-session` → update STATUS.md and SESSIONS.md, propose the commit. Never commits.
- When a choice changes architecture, scope, science, data or the demo, say
  "This is worth a decision record: `/decision <title>`" instead of deciding silently.
- Answer in the user's language (French, English or Arabic). Keep answers short and concrete,
  with `file:line` references.
