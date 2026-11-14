# Morocco data inventory (metadata only)

> Written 2026-11-12 (queries about 17:30 UTC) by a read-only session. Nothing was downloaded. Sources: ASF search API (`platform=NISAR`, `intersectsWith=POINT`) and OpenStreetMap Nominatim/Overpass. Sizes are the `.h5` size reported by ASF. Hours = GB x 8000 / 50 Mbps / 3600 (ideal; real speed is often 20-30 % lower). "est." marks an estimate.

## Headline differences from MOROCCO_PLAN.md

- **No VALIDATED GUNW exists in ASF yet.** All 673 GUNW granules mission-wide with start >= 2026-10-21 are `NISAR_L2_GUNW_PROVISIONAL_V1`, CRID P05023. CRID P05036 (`*_V1`) exists only for GCOV and GSLC. The plan's "one latest VALIDATED pair per site frame" is 0 files today. Latest Morocco GUNW acquisition is 2026-10-20 (116/19/A); latest processing date 2026-10-22.
- **GCOV exists for Morocco.** 844 granules (765 PROVISIONAL P05023, 79 VALIDATED P05036), 1,562 GB, bbox -10,28,-1,36, 2026-06-17 to 2026-11-06. Plan section 5 assumes GCOV is absent (flood questions routed to `surface_change`). Not inventoried per site, not in any tier. This is worth a decision record: `/decision GCOV for Morocco`.
- **Duplicated GUNW products on the Al Haouz frames.** 44/17/A and 23/73/D list each date pair twice: a Full product (name field `2000`, about 2.3 GB) and a Partial product (field `4000`, about 1 GB). Frame 95/73/D has only `2000` Full. The other six frames have only `4000` Full. That is 18 extra rows, 18.6 GB. Use one product configuration per chain (Full only below). What `2000` vs `4000` means physically was not checked.
- **Post-event pair does not exist yet.** Last acquisitions: 44/17 10-15, 23/73 10-13, 95/73 10-18. The pair straddling 10 Oct is also the newest pair on each frame. No acquisition falls on 10 Oct on any covering frame.
- **Spans are 12 / 24 / 36 days by calendar date** (82 / 11 / 1 of 94 rows). The only 36-day pair is 116/19/A (2026-07-16 -> 08-21). The plan's limit of 48 days covers all of them.
- **Tier 1 SME2 is 25 files, not about 40**, if limited to the site frames (2.45 GB). The whole bbox from 2026-09-20 is 134 files, 10.43 GB.
- **The Al Wahda plan point is on the dam body, not on water**: it lies inside OSM way 26301395 (`waterway=dam`), not inside a `natural=water` polygon; reservoir polygons are within 400 m.
- **`ksar_el_kebir` (35.00, -5.90) is inside the town** (OSM residential), not on the Loukkos plain. A replacement is proposed below.

## 1. Sites

Water check = OSM `is_in` at the point, plus `natural=water` / `landuse=reservoir` ways and relations within 400 m (Ksar candidate: any `waterway` within 500 m). Plan coordinates are quoted from the plan; their Wikipedia source was not re-fetched.

| Key | Final lat, lon | Source | OSM check | Open water? |
|---|---|---|---|---|
| `imlil` | 31.136, -7.919 | plan (Wikipedia) | inside a residential area (Imlil) and an `imlil` bare_rock polygon; Nominatim: Imlil, Asni commune, Al Haouz | no (none within 400 m) |
| `asni` | 31.250, -7.983 | plan (Wikipedia) | inside a residential area; Nominatim: Irz, Tamgounsit, Asni commune | no |
| `moulay_brahim` | 31.286, -7.966 | plan (Wikipedia) | inside the residential area of Moulay Brahim | no |
| `al_wahda_dam` | 34.598, -5.198 (keep); dam polygon centroid 34.59616, -5.19836 | plan (Wikipedia) + OSM way 26301395 | inside the dam polygon (0.71 km2, bbox 34.5861,-5.2084 to 34.6097,-5.1918); water polygons (rel 1365068 'Barrage Al Wahda', rel 1365135 'Oued Ouargha', way 94130275) within 400 m | not at the point; reservoir within 400 m, so edge pixels at 80 m may be water. Check valid pixels after download. |
| `gharb` | 34.50, -6.00 | `backend/events.py:23` | inside OSM `landuse=farmland`; Nominatim: Al Haouafate | no. VERIFY cleared by OSM (basemap not viewed) |
| `ksar_el_kebir` | **35.0105, -5.9031** (proposed); plan point 35.00, -5.90 rejected | OSM farmland way 257797663 | plan point is inside Ksar-el-Kebir town (residential). Proposed point is 1.2 km north-east, inside farmland, with no water, waterway or residential area within 500 m | no. Proposal only: confirm on a basemap; the Loukkos river is nearby. |
| `ben_guerir_mine` | **32.25825, -7.82355** (polygon centroid) | OSM way 638354631, `landuse=quarry`, no name or operator tag | centroid is inside the polygon (checked). bbox S 32.2002, W -7.8711, N 32.3119, E -7.7841 (about 12 km x 8 km, about 40 km2, est.). The town point (32.23, -7.95) is outside it. | not checked for pit water. It is one unnamed quarry way; that it is the OCP Benguerir open pit is not confirmed. |
| `chefchaouen` | 35.17, -5.27 | audit proxy | inside a residential area (Ain el Haoussi); one unnamed `natural=water` way within 400 m, not at the point | no |

Not re-checked: the old gazetteer `al wahda` (34.64, -5.17) in `backend/config.py:30` and `backend/events.py:19`, about 5 km from the dam; the plan already replaces it.

## 2. Coverage (ASF `intersectsWith=POINT`, start 2026-06-17)

GUNW and SME2 return the same frames for every site.

| Site | Ascending | Descending |
|---|---|---|
| imlil | 44/17 | 23/73, 95/73 |
| asni | 44/17 | 23/73 |
| moulay_brahim | 44/17 | 23/73 |
| al_wahda_dam | 116/19, 15/19 | 95/71 |
| gharb | 116/19 | 95/71 |
| ksar_el_kebir (plan point) | 116/19, 15/19 | 95/71, 23/71 |
| ben_guerir_mine (centroid) | 44/18 | 23/72 |
| chefchaouen | 116/19, 15/19 | 95/71 |

The Ksar proposal (35.0105, -5.9031) was not queried; it is 1.2 km from the plan point, so the same frames are expected (est.). The quarry centroid was queried: 44/18/A and 23/72/D, as for the town.
Smallest frame set for all sites: 44/17/A + 23/73/D (Haouz), 116/19/A + 95/71/D (north), 44/18/A + 23/72/D (Ben Guerir) = 6 frames. 95/73/D adds only imlil.

## 3. GUNW inventory

Only collection `NISAR_L2_GUNW_PROVISIONAL_V1` (CRID P05023, PGE R05.02.3) returned rows. VALIDATED: 0 rows (see headline). 94 rows in 9 frames, 199.86 GB. "Gap bridge" = ref <= 2026-07-27 and sec >= 2026-08-10. No frame has an acquisition between 07-27 and 08-10.

| Frame | Rows | GB | Acquisitions | Connected? | Missing consecutive links | Gap bridge(s): ref -> sec (span, GB) |
|---|---|---|---|---|---|---|
| 44/17/A | 18 | 29.29 | 10 (06-17 to 10-15) | yes | none | 07-23 -> 08-16 (24 d, 2.31 GB); 07-23 -> 08-16 (24 d, 0.96 GB Partial) |
| 23/73/D | 17 | 28.79 | 9 (06-27 to 10-13) | yes | none | 07-21 -> 08-14 (24 d, 2.38 GB); 07-21 -> 08-14 (24 d, 1.10 GB Partial); 07-21 -> 08-14 (24 d, 1.09 GB Partial) |
| 95/73/D | 9 | 20.48 | 10 (06-20 to 10-18) | yes | none | 07-26 -> 08-19 (24 d, 2.32 GB) |
| 116/19/A | 8 | 21.19 | 9 (06-22 to 10-20) | yes | none | 07-16 -> 08-21 (36 d, 2.65 GB) |
| 95/71/D | 9 | 21.27 | 10 (06-20 to 10-18) | yes | none | 07-26 -> 08-19 (24 d, 2.34 GB) |
| 15/19/A | 8 | 20.48 | 9 (06-27 to 10-13) | yes | none | 07-21 -> 08-14 (24 d, 2.63 GB) |
| 23/71/D | 8 | 19.60 | 9 (06-27 to 10-13) | yes | none | 07-21 -> 08-14 (24 d, 2.47 GB) |
| 44/18/A | 9 | 20.82 | 10 (06-17 to 10-15) | yes | none | 07-23 -> 08-16 (24 d, 2.35 GB) |
| 23/72/D | 8 | 17.94 | 9 (06-27 to 10-13) | yes | none | 07-21 -> 08-14 (24 d, 2.32 GB) |

Every chain is connected only through the gap bridge: without it each frame splits into two components. Each chain is nearest-neighbour (N acquisitions give N-1 pairs).

### 3.1 Every pair (ref -> sec, span, size; P = Partial duplicate)

**44/17/A**: 06-17->06-29 (12 d, 2.27 GB); 06-17->06-29 (12 d, 0.97 GB, P); 06-29->07-11 (12 d, 2.26 GB); 06-29->07-11 (12 d, 0.96 GB, P); 07-11->07-23 (12 d, 2.29 GB); 07-11->07-23 (12 d, 0.96 GB, P); 07-23->08-16 (24 d, 2.31 GB, bridge); 07-23->08-16 (24 d, 0.96 GB, P, bridge); 08-16->08-28 (12 d, 2.28 GB); 08-16->08-28 (12 d, 0.95 GB, P); 08-28->09-09 (12 d, 2.29 GB); 08-28->09-09 (12 d, 0.96 GB, P); 09-09->09-21 (12 d, 2.29 GB); 09-09->09-21 (12 d, 1.00 GB, P); 09-21->10-03 (12 d, 2.31 GB); 09-21->10-03 (12 d, 0.97 GB, P); 10-03->10-15 (12 d, 2.29 GB); 10-03->10-15 (12 d, 0.96 GB, P)

**23/73/D**: 06-27->07-09 (12 d, 2.34 GB); 06-27->07-09 (12 d, 1.12 GB, P); 07-09->07-21 (12 d, 2.36 GB); 07-09->07-21 (12 d, 1.09 GB, P); 07-21->08-14 (24 d, 2.38 GB, bridge); 07-21->08-14 (24 d, 1.10 GB, P, bridge); 07-21->08-14 (24 d, 1.09 GB, P, bridge); 08-14->08-26 (12 d, 2.36 GB); 08-14->08-26 (12 d, 1.08 GB, P); 08-26->09-07 (12 d, 2.38 GB); 08-26->09-07 (12 d, 1.06 GB, P); 09-07->09-19 (12 d, 2.37 GB); 09-07->09-19 (12 d, 1.06 GB, P); 09-19->10-01 (12 d, 2.38 GB); 09-19->10-01 (12 d, 1.13 GB, P); 10-01->10-13 (12 d, 2.36 GB); 10-01->10-13 (12 d, 1.13 GB, P)

**95/73/D**: 06-20->07-02 (12 d, 2.27 GB); 07-02->07-14 (12 d, 2.27 GB); 07-14->07-26 (12 d, 2.30 GB); 07-26->08-19 (24 d, 2.32 GB, bridge); 08-19->08-31 (12 d, 2.31 GB); 08-31->09-12 (12 d, 2.26 GB); 09-12->09-24 (12 d, 2.25 GB); 09-24->10-06 (12 d, 2.24 GB); 10-06->10-18 (12 d, 2.26 GB)

**116/19/A**: 06-22->07-04 (12 d, 2.64 GB); 07-04->07-16 (12 d, 2.65 GB); 07-16->08-21 (36 d, 2.65 GB, bridge); 08-21->09-02 (12 d, 2.63 GB); 09-02->09-14 (12 d, 2.66 GB); 09-14->09-26 (12 d, 2.65 GB); 09-26->10-08 (12 d, 2.64 GB); 10-08->10-20 (12 d, 2.65 GB)

**95/71/D**: 06-20->07-02 (12 d, 2.38 GB); 07-02->07-14 (12 d, 2.35 GB); 07-14->07-26 (12 d, 2.34 GB); 07-26->08-19 (24 d, 2.34 GB, bridge); 08-19->08-31 (12 d, 2.34 GB); 08-31->09-12 (12 d, 2.38 GB); 09-12->09-24 (12 d, 2.38 GB); 09-24->10-06 (12 d, 2.38 GB); 10-06->10-18 (12 d, 2.37 GB)

**15/19/A**: 06-27->07-09 (12 d, 2.45 GB); 07-09->07-21 (12 d, 2.43 GB); 07-21->08-14 (24 d, 2.63 GB, bridge); 08-14->08-26 (12 d, 2.58 GB); 08-26->09-07 (12 d, 2.58 GB); 09-07->09-19 (12 d, 2.61 GB); 09-19->10-01 (12 d, 2.59 GB); 10-01->10-13 (12 d, 2.62 GB)

**23/71/D**: 06-27->07-09 (12 d, 2.43 GB); 07-09->07-21 (12 d, 2.47 GB); 07-21->08-14 (24 d, 2.47 GB, bridge); 08-14->08-26 (12 d, 2.47 GB); 08-26->09-07 (12 d, 2.44 GB); 09-07->09-19 (12 d, 2.42 GB); 09-19->10-01 (12 d, 2.43 GB); 10-01->10-13 (12 d, 2.47 GB)

**44/18/A**: 06-17->06-29 (12 d, 2.34 GB); 06-29->07-11 (12 d, 2.33 GB); 07-11->07-23 (12 d, 2.33 GB); 07-23->08-16 (24 d, 2.35 GB, bridge); 08-16->08-28 (12 d, 2.29 GB); 08-28->09-09 (12 d, 2.29 GB); 09-09->09-21 (12 d, 2.28 GB); 09-21->10-03 (12 d, 2.29 GB); 10-03->10-15 (12 d, 2.30 GB)

**23/72/D**: 06-27->07-09 (12 d, 2.32 GB); 07-09->07-21 (12 d, 2.31 GB); 07-21->08-14 (24 d, 2.32 GB, bridge); 08-14->08-26 (12 d, 2.30 GB); 08-26->09-07 (12 d, 2.01 GB); 09-07->09-19 (12 d, 2.06 GB); 09-19->10-01 (12 d, 2.32 GB); 10-01->10-13 (12 d, 2.31 GB)

Year 2026. CRID is P05023 on every row; full file names are in the ASF results and not repeated here. Frame 23/73/D has 9 Partial rows for 8 date pairs: the 07-21->08-14 pair appears twice as Partial.

## 4. Al Haouz, 2026-10-10 (event time = midnight UTC, as in the plan)

Pairs are Full products. Partial duplicates exist on 44/17 and 23/73 with the same dates.

| Frame | Acquisition on 10 Oct? | Last pre-event pair | Pair straddling 10 Oct | First post-event pair | Latest acquisition |
|---|---|---|---|---|---|
| 44/17/A | no | 09-21 -> 10-03 (12 d, 2.31 GB) | 10-03 -> 10-15 (12 d, 2.29 GB) | none yet | 10-15 |
| 23/73/D | no | 09-19 -> 10-01 (12 d, 2.38 GB) | 10-01 -> 10-13 (12 d, 2.36 GB) | none yet | 10-13 |
| 95/73/D (imlil only) | no | 09-24 -> 10-06 (12 d, 2.24 GB) | 10-06 -> 10-18 (12 d, 2.26 GB) | none yet | 10-18 |

Each straddling pair spans 12 days, so a coherence change cannot be attributed to 10 Oct alone. Nearest acquisitions to the event: 10-06 (95/73), 10-03 and 10-15 (44/17), 10-01 and 10-13 (23/73). The next acquisitions would be 12 days later (est. 10-27, 10-25, 10-30); their GUNW products are not in ASF yet.

## 5. SME2

bbox -10,30.5,-1,36, start 2026-09-20: **134 files, 10.43 GB** (mean 78 MB), acquisition dates 2026-09-21 to 2026-10-21, all PROVISIONAL P05023, 39 frames. Whole window (from 2026-06-17), same bbox: 493 files, 36.86 GB. Only files that intersect the 8 site points since 2026-09-20: 25 files, 2.45 GB.

## 6. Layers

`data/GUNW/_structure.json` does **not** exist: there is no `data/` directory in this checkout. The five layer groups (ionosphere uncertainty, troposphere hydrostatic/wet, solid earth tide, validity/water mask, 80 m coherence) cannot be listed from here. `download_all.py` `extract` writes the file on the first GUNW it processes, so the layer decision needs one real file first.

## 7. Tiers vs plan section 4

"This inventory" is measured from ASF sizes unless marked est. The plan columns are quoted from the plan.

| Tier | Content (this inventory) | Files | Raw GB | Hours at 50 Mbps | Plan said |
|---|---|---|---|---|---|
| 0 | metadata only | 0 | 0 | 0.25 (plan figure, not measured) | 0 files, 0 GB, 15 min |
| 1a | Haouz GUNW: last pre + straddling pair, Full, 3 frames (44/17, 23/73, 95/73) | 6 | 13.85 | 0.62 | about 6 files |
| 1b | SME2 at the 8 sites, 2026-09-20 to latest | 25 | 2.45 | 0.11 | about 40 files |
| 1c | latest VALIDATED GUNW per site frame | 0 (none published) | 0 | 0 | about 6 files |
| **1 total** | | **31** | **16.30** | **0.72** | about 52 files, about 30 GB, about 1.5 h |
| 1 alt | 1a + SME2 whole bbox from 09-20 | 140 | 24.28 | 1.08 | |
| 2 (A) | all PROVISIONAL pairs, 9 covering frames, all rows | 94 | 199.86 | 8.88 | 55-65 files, about 120 GB, about 5.5 h |
| 2 (B) | same, Full only (drops 18 Partial duplicates) | 76 | 181.29 | 8.06 | |
| 2 (B) incremental | (B) minus the 6 Tier 1a pairs | 70 | 167.44 | 7.44 | |
| 2 (C) | 6 minimal frames, Full only | 51 | 120.73 | 5.37 | matches the plan's about 120 GB |
| 2 (C) incremental | (C) minus the 4 Tier 1a pairs on its frames | 47 | 111.39 | 4.95 | |
| 3 | full-window SME2 in the bbox | 493 | 36.86 | 1.64 | rest, about 100 GB |
| 3 | remaining atlas GUNW frames; GCOV | not inventoried | | | |

Only Tier 2 (C) matches the plan's 120 GB; the plan's "all frames covering the sites" (A) is 200 GB. The plan's "55-65 files" fits (C): 51 rows, 47 after Tier 1.

**Disk (est.)**: kept GUNW is est. 6 % of raw (README example: 2.7 GB kept as 170 MB); the README's "about 11 GB per part" implies up to about 18 %. Tier 2 (B) 181 GB gives est. 11-33 GB kept, plus raw Tier 1a 13.85 GB, plus SME2 10.43 GB: est. 35-57 GB. The plan's "under 60 GB" holds, with little room at the high end. The extra layers (ionosphere, troposphere, tide cubes, masks) are not in these figures.

## 8. Open items

- Decide Full-only vs Full + Partial before building `plan_morocco.json`.
- Re-query ASF later for VALIDATED GUNW (processing lag unknown).
- `ksar_el_kebir` and `ben_guerir_mine` need a human look at a basemap; `al_wahda_dam` needs a valid-pixel check at 80 m after download.
- GCOV for Morocco is available and changes the flood and damage story; it needs a decision.
- `download_all.py` has no `--plan` flag and no VALIDATED-collection support yet (P3 in the plan).
