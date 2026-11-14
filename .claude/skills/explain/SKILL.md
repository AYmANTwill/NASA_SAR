---
name: explain
description: Explain NISAR Pulse code, a SAR/InSAR concept, an error message or a past decision in plain language for a teammate, with file:line references. Use whenever the user asks "explain", "what does X do", "how does X work", "why does X", "c'est quoi", "explique", or types /explain. Read-only.
argument-hint: "<file | function | concept | error> [simple|deep]"
allowed-tools: Read, Grep, Glob, Bash(git log *), Bash(git show *), Bash(git grep *)
---

# Explain

Target: $ARGUMENTS

1. **Find it.** Grep the code first; the code is the truth. Use `PROJECT_DEEP_DIVE.md` only as a map
   (grep its headings, read one section) and say when it disagrees with the code. For "why"
   questions also search `docs/claude/DECISIONS.md` and `git log -S "<term>"`.
2. **Answer in this order**, skipping parts that do not apply:
   1. What it is, in one sentence.
   2. Why it exists: the problem it solves in this project.
   3. How it works, step by step, with `file:line`.
   4. One concrete example with realistic values (input → output).
   5. Who calls it and what it calls.
   6. Gotchas: known issues from `docs/claude/STATUS.md`, edge cases, what breaks if it changes.
3. **SAR concepts**: physical meaning, the formula if any, units, where it appears in the code, and
   what the radar cannot tell.
4. **Errors**: quote the error line, name the likely cause, point to file:line, give the fix and how
   to confirm it.
5. **Depth**: `simple` → no jargon, an analogy, under 15 lines. `deep` → full detail and maths.
   Default: in between.
6. Answer in the user's language. Never modify files. If you find a bug, describe it and suggest a
   fix without applying it.
