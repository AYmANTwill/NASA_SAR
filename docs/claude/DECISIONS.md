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
| D-008 | Surface-change reference: circle, baseline pair, frame background, margin 0.11, borderline band | Accepted | 2026-11-14 |
| D-009 | Ionosphere screen: subtract only where well determined, mask elsewhere | Accepted (criteria open) | 2026-11-14 |
| D-010 | Discoveries off until validated | Accepted | 2026-11-14 |

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

## D-008 — Surface-change reference: circle, baseline pair, frame background, margin 0.11, borderline band
- Date: 2026-11-14 · Status: Accepted · Deciders: user (this session)
- Context: the first real answers used a point loss and a 10×10 km square. At Imlil two geometries gave
  0.03 km² (044/17) and 11.86 km² (095/73), with no baseline to say which was normal.
- Options: A) keep point loss > 0.3 in the square; B) 5 km circle, baseline pair, frame mean and a margin;
  C) a per-geometry threshold only.
- Decision: B. Excess = circle mean loss − frame mean loss. ≥ 0.15 "local excess" (orange, medium at most);
  0.11 to 0.15 "borderline" (yellow, low, no cause); < 0.11 "no clear local change". Usable geometry:
  coverage ≥ 0.9, measurable baseline pair (coherent on ≥ 50 % of valid pixels), ≥ 50 % coherent before.
  "Baseline unreliable" if the before pair is > 0.1 below the median of the geometry's other pairs.
- Why: 0.11 is exceeded by 1 % of no-event circles (sd 0.038, about 24 million circles, 044/17, Jun–Sep
  2026); 0.15 by 0.25 %.
- Consequences: the null comes from one geometry, one season, random circles (said in every verdict).
  All real answers rest on 044/17. Asni is borderline (0.119), Moulay Brahim none (0.099): a hard
  threshold. Does not implement D-006.
- Follow-ups: measure the null on more geometries (more T095/F073 history); constants in
  `backend/recipes/damage.py` (`EXCESS_MARGIN`, `EXCESS_STRONG`).

## D-009 — Ionosphere screen: subtract only where well determined, mask elsewhere
- Date: 2026-11-14 · Status: Accepted (criteria open) · Deciders: user (this session)
- Context: `recipes/displacement.py:24-29` subtracts the product's screen on every pair. The product spec
  (Rev B) says it is "not applied by default" (variable quality). Real data: whole-frame noise 96 → 2.6 cm
  (23/73, 1→13 Oct), lowest in 10 of 12 pairs; but at discovery zones 3, 4, 6 a screen of −71.5, +130.4,
  −92.2 cm (stated uncertainty ±1–7 cm) gave corrected +66.6, −200.4, +46.1 cm.
- Options: A) subtract everywhere (today); B) subtract only where well determined, mask elsewhere;
  C) never subtract.
- Decision: B. What "well determined" means is not decided yet: no threshold is set here.
- Why: C raises noise up to 40×; A injects whole-fringe artefacts.
- Consequences: masked pixels reduce coverage; displacement numbers change (Al Wahda: +43.4/−20.0 mm with
  the screen, +29.6/+71.4 mm without).
- Follow-ups: define the criterion with Ayman's noise report (`feat/validation-corrections`); implement
  in `backend/recipes/displacement.py` `los_cm`; re-run `precompute.py`; update tests, API contract; link
  to H4 and S3.

## D-010 — Discoveries off until validated
- Date: 2026-11-14 · Status: Accepted · Deciders: user (this session)
- Context: zones of −182.7 cm over 600 km², +98 cm and −179 cm in one 12-day pair (8 to 15 fringes). On
  real data 18 of 20 zones had ≥ 1 fringe, 0 of 20 were shown by a second geometry, all lay in one
  connected component; three of the top six come from the ionosphere subtraction (D-009).
- Decision: `DISCOVERIES_ENABLED` is False by default; `/discoveries` returns an empty list and a reason,
  never the old cache; zones are "unvalidated candidate" (confidence low, alert yellow at most). Code kept.
- Consequences: no "what NISAR found" panel in the demo.
- Follow-ups: re-enable only after D-009 is implemented and a second geometry confirms a zone
  (`backend/config.py`, `backend/discoveries.py`).
