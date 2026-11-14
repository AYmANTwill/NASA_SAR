---
name: review-commit
description: Review NISAR Pulse changes before the user commits manually. Checks secrets, data files, tests, cross-file contracts and science, then gives a READY / NOT READY verdict and the commit commands. Read-only. Run only when the user types /review-commit.
disable-model-invocation: true
argument-hint: "[optional: files or focus]"
allowed-tools: Read, Grep, Glob, Bash(git status *), Bash(git diff *), Bash(git log *), Bash(git grep *), Bash(git ls-files *), Bash(python tests/test_all.py), Bash(python backend/tests/test_all.py)
---

# Review before commit

Focus (may be empty): $ARGUMENTS

## Live git state
- Staged: !`git diff --cached --stat`
- Unstaged and untracked: !`git status --short`

## Scope
Review the **staged** changes if there are any, otherwise all uncommitted changes, and say which.
If a focus is given, limit the review to it. Read the full diff (`git diff --cached` or `git diff`)
and open untracked files. Do not edit, stage or commit anything.

## Checks (in this order)
1. **Secrets** (blocker). Search the diff and untracked files for JWT-like strings (`eyJ` followed by
   dot-separated parts), `sk-ant-`, `EARTHDATA_TOKEN = "`, `MAP_KEY`, `.earthdata_token`, `.env`.
   Report file:line only, never the value.
2. **Files that must not be committed** (blocker): `data/`, `backend/cache/`, `*.h5`, `*.tif`, `*.npz`,
   `*.zip`, `*.joblib`, `.claude/settings.local.json`, anything over 1 MB.
3. **Tests** (blocker if failing): if `.py` files changed, run `python tests/test_all.py` from `backend/`.
4. **Contracts**: the partner file changed too?
   - downloader output names or `LAYERS` ↔ `catalog.LAYER_FILES` / `MAIN_LAYER`;
   - recipe fact keys ↔ `agent.template`, `template_ar`, `assess`, `mock.py`, `docs/API_CONTRACT.md`;
   - new question type ↔ `TYPES`, `KEYWORDS`, `PRIORITY`, `CANNOT_SAY`, `CANNOT_SAY_AR`;
   - new env var ↔ README table; new package ↔ `requirements.txt`.
5. **Science**: if `recipes/`, `uncertainty.py`, `config.py`, `agent.py`, `evidence.py` or
   `discoveries.py` changed, apply the `science-check` checklist to the changed lines.
6. **Code hygiene**: leftover `print(` or `breakpoint()`, dead code, bare `except:` hiding errors,
   new code outside `Steps.run` that can raise (HTTP 500), a fixed bug without a test.
7. **Docs**: STATUS.md / DECISIONS.md updated when behaviour, scope or a decision changed.

## Output
```
Verdict: ✅ READY | ⚠️ READY WITH NOTES | ⛔ NOT READY
Scope: staged | all uncommitted     Tests: n/N | not run (reason)
```
Then one table: severity (blocker / major / minor) · file:line · problem · fix. Skip empty rows.
Unless ⛔, give the commands **for the user to run** (explicit files, never `git add .`):
```
git add <files>
git commit -m "<type>(<scope>): <summary>" -m "<why>"
```
Finish with: "I did not stage or commit anything."
