---
name: decision
description: Compare options for a NISAR Pulse choice and record the agreed decision in docs/claude/DECISIONS.md (lightweight ADR). Run only when the user types /decision.
disable-model-invocation: true
argument-hint: "<decision title or open question>"
allowed-tools: Read, Edit, Grep, Glob
---

# Decision

Topic: $ARGUMENTS

1. Read the index table of `docs/claude/DECISIONS.md`. Find the next ID and any related or
   conflicting decision.
2. **If the choice is still open**: give 2–3 options, each with pros, cons, effort before the
   hackathon, and risk (science, demo, security). Recommend one in one sentence and ask the user to
   choose. Write nothing yet.
3. **Once the user has chosen** (or if the topic states a decision already taken), append an entry
   using the template at the top of DECISIONS.md and add a row to the index table.
   - Status: `Accepted` if the user decided now, `Proposed` if the team still has to agree.
   - Deciders: ask if unknown; never invent names.
   - Follow-ups: concrete actions with file paths.
   - Under 25 lines. Facts only from the conversation or the code.
4. If it replaces an older decision, change only the old entry's status to `Superseded by D-xxx`
   (in the entry and in the index).
5. Add any follow-ups to "Next" in `docs/claude/STATUS.md`.
6. Show the entry and end with: "Recorded in docs/claude/DECISIONS.md, not committed."
