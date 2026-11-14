# NISAR Pulse — Decisions

> Lightweight decision records. Add with `/decision <topic>`. Never delete an entry: supersede it.
> Status: Proposed · Accepted · Superseded by D-xxx · Rejected

## Template
```
## D-xxx — <title>
- Date: YYYY-MM-DD · Status: <status> · Deciders: <names or "team">
- Context: <the problem, 1–3 lines>
- Options: A) … B) … C) …
- Decision: <what we do>
- Why: <main reasons>
- Consequences: <what this costs or rules out>
- Follow-ups: <actions with file paths>
```

## Index
| ID | Title | Status | Date |
|---|---|---|---|
| D-001 | Numbers come only from deterministic recipes | Accepted | 2026-11-11 |
| D-002 | File-based storage, no database | Accepted | 2026-11-11 |
| D-003 | Claude Code never commits; humans commit | Accepted | 2026-11-12 |
| D-004 | Credentials only from env var or git-ignored file | Proposed | 2026-11-12 |
| D-005 | Demo scope: Panama GUNW hero + Morocco context | Proposed | 2026-11-12 |
| D-006 | Split confidence into quality and independent support | Proposed | 2026-11-12 |
| D-007 | Morocco territory: event- and site-driven data scope | Proposed | 2026-11-12 |

---

## D-001 — Numbers come only from deterministic recipes
- Date: 2026-11-11 · Status: Accepted · Deciders: original author (recorded from the code)
- Context: judges must trust the figures; an LLM can invent numbers.
- Decision: recipes compute all numbers; the LLM may only classify a question or reword Arabic text,
  and its output is rejected if it contains a number not in the facts (`agent.rephrase`).
- Consequences: keyword routing is brittle (H3) but answers are reproducible and work offline.

## D-002 — File-based storage, no database
- Date: 2026-11-11 · Status: Accepted · Deciders: original author (recorded from the code)
- Context: hackathon speed; data are rasters; single laptop demo.
- Decision: `data/` folders with `_DONE` markers; JSON/PNG/joblib in `backend/cache/`.
- Consequences: no concurrency control (M2, M3). Revisit only for multi-user deployment.

## D-003 — Claude Code never commits; humans commit
- Date: 2026-11-12 · Status: Accepted · Deciders: team
- Context: every commit must be reviewed and made by a person.
- Decision: deny rules in `.claude/settings.json` + `guard_git.py` hook block commit, push, merge,
  rebase, pull, tag, revert, cherry-pick, hard/soft reset, `clean -f`, `gh pr create/merge`.
  Claude proposes `git add <files>` and a message; the user runs them.
- Consequences: `/end-session` and `/review-commit` end with commands for the user.

## D-004 — Credentials only from env var or git-ignored file
- Date: 2026-11-12 · Status: Proposed · Deciders: team (token owner must act)
- Context: an Earthdata token is hard-coded in `download_all.py` and in git history (H1).
- Decision: revoke it; resolution order env `EARTHDATA_TOKEN` → `.earthdata_token` → prompt.
- Follow-ups: revoke at urs.earthdata.nasa.gov; edit `download_all.py` `get_token`; decide whether
  to rewrite git history if the repository is or will be public.

## D-005 — Demo scope: Panama GUNW hero + Morocco context
- Date: 2026-11-12 · Status: Proposed · Deciders: team
- Context: only GUNW and SME2 are in the download plan; no GCOV/GOFF; nothing validated on real data.
- Options: A) Panama coseismic hero + SME2 Gharb (provisional) + Ben Guerir cumulative LOS;
  B) Morocco-only GUNW; C) GCOV flood (needs new data, Jan–Feb 2026 flood predates NISAR data).
- Decision (proposed): A. Hide flood, deforestation, large displacement, damage and classifier in the demo.
- Follow-ups: confirm straddling Panama pairs in part 1; verify `LOS_SIGN`.

## D-006 — Split confidence into quality and independent support
- Date: 2026-11-12 · Status: Proposed · Deciders: team
- Context: current confidence mixes SNR, co-occurring quakes/rain and exposure (S2, S5, M7).
- Decision (proposed): report `measurement_quality` (valid fraction, realistic noise, corrections)
  and `independent_support` (only sources that test the measurement); exposure shown separately;
  alert level may be `none`.
- Follow-ups: `uncertainty.py`, `agent.assess`, `mock.py`, `docs/API_CONTRACT.md`.

## D-007 — Morocco territory: event- and site-driven data scope
- Date: 2026-11-12 · Status: Proposed · Deciders: team (user to confirm)
- Context: the project must work on Moroccan territory. ASF inventory (`docs/claude/morocco_inventory.md`):
  the 8 sites are covered by 9 frames, 94 PROVISIONAL GUNW rows (199.9 GB, CRID P05023), 18 of them
  Partial duplicates on 44/17 and 23/73. Data gap 2026-07-27 → 08-10: every chain is connected only
  through a 24/36-day bridge. No VALIDATED GUNW is published yet. Only Moroccan event in the window:
  Al Haouz flash flood, 10 Oct 2026; no acquisition on 10 Oct, straddling pairs are 12 days wide, no
  post-event pair yet. SME2 since 20 Sep: 134 files, 10.4 GB. Plan states 400 GB disk.
- Options: A) minimal 2 frames, one direction, 12-day pairs (36.5 GB, drops gap bridges and Haouz);
  B) all 11 atlas frames (108 rows, 229 GB); C) frames covering the verified sites, both directions,
  gap bridges included, Full products only, in tiers (Tier 1 31 files 16.3 GB; Tier 2 minimal
  6 frames 51 files 120.7 GB; about 128 GB, 5.7 h at 50 Mbps for Tier 1 + Tier 2 without overlap).
- Decision (proposed): C.
- Why: covers a real Moroccan event, both look directions, connected chains; about 128 GB instead of
  229 GB; tiers put the demo data first.
- Consequences: Panama is no longer the demo hero (D-005 would be superseded); it stays only as a
  sign-check fixture if already on disk. Slow subsidence and dam safety are answered as "not
  measurable yet". Cumulative LOS per date, not mm/yr. No validated stack exists yet.
- Follow-ups: `docs/claude/MOROCCO_PLAN.md` §4–§6; decide Full-only vs Full + Partial; a decision on
  GCOV (844 Morocco granules exist, 1,562 GB); re-query ASF for VALIDATED GUNW; move `ksar_el_kebir`
  to 35.0105, -5.9031 after a basemap check.
