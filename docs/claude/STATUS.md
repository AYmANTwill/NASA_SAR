# NISAR Pulse — Status

> Rewritten by `/end-session`. Read by `/start-session`. Keep under ~80 lines.
> Issue IDs H/M/L come from `PROJECT_DEEP_DIVE.md` §13; S = science review of 2026-11-12.

## Snapshot
- Updated: 2026-11-12 (seeded when the Claude Code setup was added; not yet checked by a session)
- HEAD: `eda84ef` on `main` (update on first `/end-session`)
- Tests: 30/30 reported by PROJECT_DEEP_DIVE.md on synthetic data. Not re-run here.
- Real data: part 1 reportedly downloaded by the team; no recipe validated on a real NISAR file yet.
- Frontend: none in the repository.

## Goal until the hackathon (14–15 Nov 2026)
One real, verified NISAR result shown end to end in a simple UI, with honest provenance and limits.

## Next (ordered)
1. Token owner revokes the Earthdata token; remove it from `download_all.py` (H1, D-004).
2. Run Panama on real part-1 data, compare with a published deformation map, set `LOS_SIGN` (H4).
3. Fix `run_sudden`: exact event time, no silent fallback, `max([])` crash (S1, M5, H2).
4. Word-boundary keyword router; unknown question → ask, not `damage` (H3).
5. Fix SME2 latest date/value pairing (M1).
6. Minimal map UI served by the backend (Leaflet), started from mock mode.
7. Decide demo scope (D-005) and confidence split (D-006).

## In progress
- (none)

## Done recently
- 2026-11-12: Claude Code setup added (CLAUDE.md, .claude/, docs/claude/).

## Known issues
| ID | Sev | Where | Issue |
|---|---|---|---|
| H1 | high | `download_all.py` ~L494-497 | Earthdata token hard-coded and in git history |
| H2 | high | `agent.py` run_sudden ~L143 | `max([])` → HTTP 500 when all pairs fail |
| H3 | high | `agent.py` classify_rules | substring keywords ("street"→tree); no keyword → damage |
| H4 | high | `config.LOS_SIGN` | sign not verified on real data |
| S1 | high | `events.py`, `agent.py` ~L197 | event date passed as midnight, not 17:56 UTC (Panama) |
| M5 | high | `agent.py` ~L129 | falls back to pairs that do not straddle the event |
| S2 | med | `displacement.referenced`, `uncertainty` | noise = per-pixel MAD; understates window error (SNR ~100×) |
| S3 | med | `displacement.los_cm` | only component 0 masked; 2π offsets between components |
| S4 | med | `timeseries._fit`, `agent.assess` | mm/yr from ~5 months of 12-day chains; no minimum span |
| S5 | med | `agent.assess` | quake M≥5.5 / rain ≥50 mm counted as agreement → high/red |
| M1 | med | `soil_moisture.py` ~L71 | latest date from last file, value from last valid file |
| M2 | med | `raster.render_png` callers | PNG named by product only; overwritten per request |
| M3 | med | `watch.py` | `watches.json` not atomic / not locked |
| M4 | med | `agent.py` ~L214 | damage without a date always "no data" |
| M12 | low | `requirements.txt` | unpinned; `rich` missing |

## Open questions
- Has the token been revoked? Who owns it?
- Which Panama GUNW pairs in part 1 straddle 2026-10-09 17:56 UTC with valid coverage?
- Who builds the UI, and with what (single HTML page vs React)?
