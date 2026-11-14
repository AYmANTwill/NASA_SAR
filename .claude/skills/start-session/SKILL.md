---
name: start-session
description: Start a NISAR Pulse work session. Loads STATUS.md, recent sessions, open decisions and git state, then agrees a goal and plan with the user. Run only when the user types /start-session.
disable-model-invocation: true
argument-hint: "[goal for this session]"
allowed-tools: Read, Grep, Glob, Bash(git status *), Bash(git log *), Bash(git diff *), Bash(git branch --show-current), Bash(git rev-parse *)
---

# Start session

## Live git state
- Branch: !`git branch --show-current`
- Last commits: !`git log --oneline -8`
- Uncommitted: !`git status --short`

## Steps
1. Read `docs/claude/STATUS.md` fully, the **last two** entries of `docs/claude/SESSIONS.md`, and only
   the index table of `docs/claude/DECISIONS.md` (open full entries only for `Proposed` ones).
2. Compare the commit recorded in STATUS.md with HEAD. If someone committed since, list those
   commits in one line each and note what they change in the status.
3. If there are uncommitted changes, list them and say whether they look like leftovers from the
   last session. Do not discard or stage anything.
4. Write a brief (max 15 lines):
   - **Where we are**: one or two sentences.
   - **Blocking**: blockers and `Proposed` decisions that need a human call.
   - **Next up**: the top 3 items from STATUS.md "Next".
   - **Warnings**: stale STATUS (older than the last commit), failing tests, secrets still in code.
5. Goal:
   - If a goal was given (`$ARGUMENTS`), restate it, give a plan of 3–6 steps with the files likely
     touched, flag any rule it may hit (science, data, secrets), and ask "Go?".
   - If no goal, ask the user to pick one of the "Next up" items or name another.
6. Do not edit any file here. STATUS.md is updated by `/end-session`.
