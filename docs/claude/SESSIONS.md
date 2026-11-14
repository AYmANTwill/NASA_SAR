# NISAR Pulse — Session log

> Appended by `/end-session`, newest at the bottom. One entry per session, max 12 lines.

## Template
```
### YYYY-MM-DD HH:MM — <who> — <goal in a few words>
- Done: …
- Not done / carried over: …
- Files: …
- Tests: n/N | not run (reason)
- Decisions: D-xxx (new/changed) | none
- Next step: …
```

---

### 2026-11-12 — setup — Claude Code workflow added
- Done: CLAUDE.md, .claude/settings.json (manual-commit policy), git guard hook, 7 skills,
  docs/claude/STATUS.md, DECISIONS.md, SESSIONS.md seeded from PROJECT_DEEP_DIVE.md and review.
- Files: CLAUDE.md, .claude/**, docs/claude/**
- Tests: not run (docs and config only)
- Decisions: D-001…D-006 recorded (D-004…D-006 Proposed)
- Next step: `/start-session` and work on STATUS "Next" #1–#3.

### 2026-11-14 — Anass + Claude — Morocco backend v2 and real-data checks
- Done: surface change v2 (circle, baseline, frame background, bands); signed LOS answers "sign unverified"; discoveries off; soil-moisture uncertainty; mine "not validated"; precompute UTF-8; phase A real-data checks (`results/REPORT.md`).
- Not done / carried over: phase B (Ayman's branch missing), Panama download and sign check, token revocation, ionosphere decision.
- Files: backend/{agent,config,discoveries,events,mock,raster,api,precompute,train_classifier}.py, recipes/{damage,displacement,soil_moisture,timeseries}.py, tests/*, docs/API_CONTRACT.md, results/**
- Tests: 151/151 (synthetic; no `.py` changed after the run)
- Decisions: none recorded (7 candidates listed in the session, awaiting confirmation)
- Next step: STATUS "Next" #1–#3.
