# NISAR data on disk: plain-language report

Generated 2026-11-14 19:54 from `D:\project\NASA_SAR\data`. Read-only: nothing in the data folder was changed. Every figure below is read from the files.

## 1. In short

| Dataset | What it is | Products | Size on disk |
|---|---|---|---|
| GUNW | Interferogram pairs (two radar passes, 12 days apart or more). Used for ground motion and, through coherence, for surface change. One product = one pair. | 103 | 200.6 GB |
| GCOV | Radar backscatter (how bright the ground looks to the radar). Used for water, soil and vegetation change. One product = one pass. | 9 | 27.9 GB |
| SME2 | Soil moisture estimates (Level 3, 200 m). One product = one pass. Provisional, not fully calibrated. | 82 | 7.5 GB |

Total on disk: **236.0 GB** (free space on that drive: 225 GB).

Health checks: 0 product(s) with no completion marker; 0 product(s) that reported a missing layer.

## 2. What we have, by place

### Morocco

- **GUNW**: 53 product(s), 151.0 GB, from 2026-06-17 to 2026-10-20.
  - Maturity (CRID): PROVISIONAL P05023
  - Viewing geometries: track 116 frame 19 ascending (8); track 23 frame 72 descending (8); track 23 frame 73 descending (8); track 44 frame 17 ascending (9); track 44 frame 18 ascending (9); track 95 frame 71 descending (9); track 95 frame 73 descending (2)
  - Pair length: 12 days: 47, 24 days: 5, 36 days: 1
  - Original file kept for 53 of 53 products; geometry extras: axes+tide.
- **GCOV**: 9 product(s), 27.9 GB, from 2026-09-21 to 2026-10-15.
  - Maturity (CRID): PROVISIONAL P05023
  - Viewing geometries: track 23 frame 73 descending (4); track 44 frame 17 ascending (5)
  - Full frames: 5, partial frames: 4.
- **SME2**: 82 product(s), 7.5 GB, from 2026-06-17 to 2026-10-20.
  - Maturity (CRID): PROVISIONAL P05023
  - Viewing geometries: track 116 frame 19 ascending (9); track 15 frame 19 ascending (9); track 23 frame 71 descending (2); track 23 frame 72 descending (9); track 23 frame 73 descending (19); track 44 frame 17 ascending (11); track 44 frame 18 ascending (10); track 95 frame 71 descending (10); track 95 frame 73 descending (3)

### Panama

- **GUNW**: 17 product(s), 34.5 GB, from 2026-09-11 to 2026-10-17.
  - Maturity (CRID): PROVISIONAL P05023
  - Viewing geometries: track 141 frame 84 descending (2); track 141 frame 85 descending (3); track 4 frame 5 ascending (2); track 4 frame 6 ascending (2); track 40 frame 84 descending (2); track 40 frame 85 descending (2); track 76 frame 5 ascending (2); track 76 frame 6 ascending (2)
  - Pair length: 12 days: 16, 24 days: 1
  - Original file kept for 17 of 17 products; geometry extras: axes+tide.

### other

- **GUNW**: 33 product(s), 15.1 GB, from 2026-06-13 to 2026-10-18.
  - Maturity (CRID): PROVISIONAL P05023
  - Viewing geometries: track 126 frame 83 descending (1); track 126 frame 84 descending (1); track 15 frame 20 ascending (8); track 162 frame 6 ascending (1); track 162 frame 7 ascending (1); track 54 frame 83 descending (1); track 61 frame 6 ascending (1); track 61 frame 7 ascending (1); track 95 frame 70 descending (18)
  - Pair length: 12 days: 30, 24 days: 3
  - Original file kept for 0 of 33 products; geometry extras: axes+tide.

## 3. Which products straddle each event

A pair straddles an event if the first pass is before it and the second pass after it. Only these pairs can show a change caused by it.

### Panama M7.7 earthquake (2026-10-09 17:56:06 UTC)

| Region | Track/frame | Direction | Reference -> secondary | Days | Straddles | Coverage |
|---|---|---|---|---|---|---|
| Panama | 4/5 | A | 2026-09-30 -> 2026-10-12 | 12 | yes | partial frame |
| Panama | 4/6 | A | 2026-09-30 -> 2026-10-12 | 12 | yes | full frame |
| Panama | 40/84 | D | 2026-10-02 -> 2026-10-14 | 12 | yes | full frame |
| Panama | 40/85 | D | 2026-10-02 -> 2026-10-14 | 12 | yes | partial frame |
| Panama | 76/5 | A | 2026-10-05 -> 2026-10-17 | 12 | yes | partial frame |
| Panama | 76/6 | A | 2026-10-05 -> 2026-10-17 | 12 | yes | partial frame |
| Panama | 141/84 | D | 2026-09-27 -> 2026-10-09 | 12 | yes | full frame |
| Panama | 141/85 | D | 2026-09-27 -> 2026-10-09 | 12 | yes | partial frame |
| Panama | 141/85 | D | 2026-09-27 -> 2026-10-09 | 12 | yes | partial frame |


### Al Haouz storm and flash floods (whole day 2026-10-10)

| Region | Track/frame | Direction | Reference -> secondary | Days | Straddles | Coverage |
|---|---|---|---|---|---|---|
| Morocco | 23/72 | D | 2026-10-01 -> 2026-10-13 | 12 | yes | full frame |
| Morocco | 23/73 | D | 2026-10-01 -> 2026-10-13 | 12 | yes | full frame |
| Morocco | 44/17 | A | 2026-10-03 -> 2026-10-15 | 12 | yes | full frame |
| Morocco | 44/18 | A | 2026-10-03 -> 2026-10-15 | 12 | yes | full frame |
| Morocco | 95/71 | D | 2026-10-06 -> 2026-10-18 | 12 | yes | full frame |
| Morocco | 95/73 | D | 2026-10-06 -> 2026-10-18 | 12 | yes | full frame |
| Morocco | 116/19 | A | 2026-10-08 -> 2026-10-20 | 12 | yes | full frame |

- GCOV single-pass products: last pass before: 2026-10-03 (track 044); first pass after: 2026-10-13 (track 023, 2.8 days later).
- SME2 single-pass products: last pass before: 2026-10-08 (track 116); first pass after: 2026-10-13 (track 015, 2.2 days later).

## 4. Things everyone should know before using these numbers

- Everything with CRID P05023 is **provisional** (calibrated, still being validated). Validated products (CRID P05036) cover acquisitions from 21 Oct 2026 and none is mixed in here unless the table above says so.
- The satellite has a **data gap** from 2026-07-27 to 2026-08-10 UTC. A chain of 12-day pairs is cut there; only a longer pair bridges it.
- Soil moisture (SME2) is provisional and not fully calibrated: treat small changes as noise.
- Radar measures movement only along its line of sight, and the sign convention is **not verified** on a real event yet.
- Backscatter (GCOV) changes with soil moisture and vegetation, so a change is not proof of a flood.
- The region comes from the footprint centre of each product when rasterio is installed (CSV column region_source = footprint), otherwise from the track number (region_source = track number).

## 5. Files

- `products.csv`: one row per product (open it in Excel). Columns: dataset, region, track, frame, direction, coverage, CRID, maturity, dates, pair length, size, raw file kept, complete, layers missing, geometry extras, folder name.
- This report: `DATA_REPORT.md`.

To regenerate: `python tools/data_report.py --data <data folder> --out results/data-inventory`.
