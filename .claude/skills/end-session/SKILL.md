---
name: end-session
description: Close a NISAR Pulse work session. Runs tests if code changed, rewrites docs/claude/STATUS.md, appends to SESSIONS.md, lists decisions to record, and prepares the commit commands for the user. Never commits. Run only when the user types /end-session.
disable-model-invocation: true
argument-hint: "[optional note]"
allowed-tools: Read, Edit, Write, Grep, Glob, Bash(git status *), Bash(git diff *), Bash(git log *), Bash(git rev-parse *), Bash(python tests/test_all.py), Bash(python backend/tests/test_all.py)
---

# End session

User note (may be empty): $ARGUMENTS

## Live git state
- HEAD: !`git log --oneline -1`
- Changed files: !`git status --short`
- Size of change: !`git diff HEAD --stat`

## Steps
1. **Summarise the session** from the conversation and the diff: goal, what was done, what was not.
2. **Tests**: if any `.py` file changed, run `python tests/test_all.py` from `backend/` and keep the
   exact result (`n/N`). If only docs changed, write "not run (docs only)".
3. **Rewrite `docs/claude/STATUS.md`** (rewrite, do not append; stay under ~80 lines):
   update "Snapshot" (date, HEAD, tests), move finished items to "Done recently" (keep the last 5),
   reorder "Next", open or close entries in "Known issues" by ID, update "Open questions".
   Never mark something verified on real data unless it was actually checked in this session.
4. **Append to `docs/claude/SESSIONS.md`** using the template at the top of that file (≤ 12 lines).
5. **Decisions**: list any choice made in this session that is not in `DECISIONS.md`. Ask whether to
   record each one; record only those the user confirms (same format as `/decision`).
6. **Hand over the commit** — show these, do not run them:
   ```
   git add <every changed file, listed one by one, including docs/claude/*>
   git commit -m "<type>(<scope>): <summary>" -m "<why, 1–3 lines>"
   ```
   Types: feat, fix, refactor, test, docs, chore, science. Never include `data/`, `backend/cache/`,
   `*.h5`, `*.tif`, `*.zip` or secrets. If `/review-commit` was not run after the last change, say so.
7. End with one line: "Nothing was committed. Run the commands above when you are ready."
