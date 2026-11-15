# Claude Code setup for NISAR Pulse

## Install (once)
1. Copy `CLAUDE.md`, `.claude/` and `docs/claude/` into the repository root (next to `download_all.py`).
2. Add to `.gitignore`: `.claude/settings.local.json`
3. Check the hook works. PowerShell, from the repo root:
   ```powershell
   '{"tool_input":{"command":"git commit -m x"}}' | python .claude/hooks/guard_git.py; $LASTEXITCODE   # 2 = blocked
   '{"tool_input":{"command":"git status"}}'      | python .claude/hooks/guard_git.py; $LASTEXITCODE   # 0 = allowed
   ```
   On macOS/Linux, if `python` is not found, replace `python` with `python3` in `.claude/settings.json`.
4. Start `claude` in the repo root, run `/hooks` to confirm the PreToolUse hook is listed and
   `/permissions` to see the rules. Commit these files yourself.

## Daily workflow
```
/start-session fix the Panama event pairing      ← loads status + git state, agrees a plan
   … work …   /explain agent.run_sudden            ← understand before changing
              /decision demo scope                  ← compare options, record the choice
/review-commit                                      ← READY / NOT READY + commands
/end-session                                        ← updates STATUS + log, prints commands
git add <files> ; git commit -m "..."               ← YOU run this
```

## What each part does
| Part | Role |
|---|---|
| `CLAUDE.md` | Rules Claude reads every session: no commits, secrets, data, science invariants, conventions |
| `.claude/settings.json` | Permissions: read-only git allowed; staging/branch/download ask first; commit/push/merge/... denied; secrets and `plan_nisar.json` protected |
| `.claude/hooks/guard_git.py` | Second lock: blocks any command that writes git history, even inside `cd x && …` or `bash -c` |
| `/start-session` | Brief of where we are + plan for a goal. Edits nothing |
| `/end-session` | Runs tests if code changed, rewrites STATUS, logs the session, prints commit commands |
| `/review-commit` | Pre-commit review: secrets, data files, tests, contracts, science, hygiene. Read-only |
| `/explain` | Plain explanation of code, concept or error (also triggers on "explain …"). Read-only |
| `/decision` | Options → choice → entry in DECISIONS.md |
| `science-check` | Automatic checklist whenever numbers, signs, units or confidence change |
| `/demo-check` | Go / no-go before presenting |
| `docs/claude/STATUS.md` | Current state, next steps, known issues (by ID) |
| `docs/claude/DECISIONS.md` | Why things are the way they are |
| `docs/claude/SESSIONS.md` | Short log so teammates can pick up |

## Limits to know
- Permissions and the hook stop Claude, not you. Nothing prevents a human from committing.
- If Python is missing the hook cannot run; the deny rules in `settings.json` still apply.
- Personal overrides go in `.claude/settings.local.json` (not committed). Do not add
  `git commit` to an allow list there: deny rules win anyway, and it defeats the policy.
