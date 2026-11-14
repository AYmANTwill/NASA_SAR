# NISAR Pulse — Morocco plan (D-007)

> Put this file in `docs/claude/MOROCCO_PLAN.md`. Claude Code prompts below refer to it.
> Written 2026-11-12 from the Claude Code audit, the NISAR user guide and press reports.
> Items marked **VERIFY** must be checked before the demo.

---

## 1. What the research changes

| # | Finding | Source | Consequence for us |
|---|---|---|---|
| F1 | Permanent NISAR data gap **2026-07-27 → 2026-08-10** | ASF availability page | A 12-day-only stack is cut in two. The 24/36-day pairs that bridge the gap (e.g. 116/19, 16 Jul → 21 Aug) are **required**, not optional. The plan's `spans 12/24` filter drops them. |
| F2 | The mission only makes **12-day nearest-neighbour**, co-pol, frequency A GUNW | ASF GUNW page | No redundant pairs: the "SBAS" is a chain. Report cumulative LOS per date, not mm/yr. |
| F3 | PROVISIONAL (CRID P05023): 17 Jun → ~23 Oct 2026. VALIDATED (CRID P05036): from 21 Oct 2026, released 6 Nov. SME2 stays PROVISIONAL. | ASF availability page | Two separate stacks. Never mix CRIDs in one time series. Validated pairs answer "what changed recently". |
| F4 | Ionosphere screen is shipped **not applied**; banding in stacks, low-pass filtering advised; residuals worse on descending (evening) tracks. Troposphere and solid-earth-tide lookup tables are shipped **not applied**. | ASF GUNW + known-issues pages | Extract these layers **now** (raw files are deleted after extraction). Prefer ascending for time series. |
| F5 | Sign: several independent tools use NISAR phase as delivered with −λ/4π → positive = toward the satellite. | OpenSAR-Explorer, ARIA-tools, ASF "NISAR in GIS" story map (secondary; official spec PDF not reachable from here) | `LOS_SIGN=+1` matches. H4 drops from blocker to "documented, one empirical check pending". |
| F6 | **Al Haouz flash floods and mudflows, Saturday 10 Oct 2026** (Asni, Moulay Brahim, Imlil road cut). | Hespress, 11 Oct 2026 | A real Moroccan event inside the PROVISIONAL window. Coherence change around it is sign-independent, so it is robust even before H4 is closed. |
| F7 | No Moroccan earthquake large enough for InSAR in the window (largest found: M4.6 Errachidia, 3 Aug). | Moroccan press | No coseismic Morocco case. |
| F8 | Groundwater subsidence in Morocco is a few mm to ~20 mm/yr (Souss-Massa studies). | AGU 2022 abstract; UGA thesis | Over 4 months that is a few mm, below cm-level atmospheric noise. Do not promise subsidence results. |
| F9 | Gazetteer "Al Wahda" (34.64, −5.17) is ~5 km from the dam (34.598, −5.198), likely on the reservoir. | Wikipedia | Water is incoherent → no data. Fix the coordinates. |
| F10 | SME2 search box stops at 32.5°N; SME2 flags are not fully implemented (nulls); use `/science/LSAR/SME2/grids/soilMoisture`. | ASF known issues | Extend SME2 south to cover Ben Guerir and Al Haouz. Do not rely on SME2 flags. |

---

## 2. Decision record (paste with `/decision`)

```
## D-007 — Morocco territory: event- and site-driven data scope
- Date: 2026-11-12 · Status: Proposed · Deciders: team
- Context: the project must work on Moroccan territory. Audit: 108 Morocco GUNW (229 GB raw),
  192 SME2 (17.6 GB); data gap 27 Jul–10 Aug 2026; PROVISIONAL until ~23 Oct, VALIDATED from 21 Oct;
  only real Moroccan event in the window is the 10 Oct 2026 Al Haouz flash flood; 400 GB disk.
- Options: A) minimal 2 frames, one direction (36 GB); B) all 11 atlas frames (229 GB);
  C) frames covering 8 verified sites, both directions, complete chains incl. gap bridges,
     + validated pairs after 21 Oct, + SME2 extended south, downloaded in priority tiers.
- Decision: C.
- Why: covers a real Moroccan event, both look directions, connected chains; ~120–160 GB
  transfer instead of 229 GB; tiers put the demo data first.
- Consequences: Panama is no longer the demo hero (D-005 superseded); it stays only as a
  sign-check fixture if already on disk. Questions about slow subsidence and dam safety are
  answered as "not measurable yet". Time series reported as cumulative LOS, not mm/yr.
- Follow-ups: §4–§6 of docs/claude/MOROCCO_PLAN.md.
```

If accepted, mark D-005 `Superseded by D-007`.

---

## 3. Sites (coordinates)

Rules used to choose a point:
1. The point must be on ground that stays coherent at L-band (bare soil, rock, villages, fields), never on open water.
2. Use a published coordinate (Wikipedia or OpenStreetMap), recorded with its source.
3. For areas (mine, plain, reservoir), store a polygon from OSM, not only a point.
4. Check the point is inside valid pixels of **both** directions after the first download.

| Key | Place | Lat, Lon | Source | Question we can answer | Products |
|---|---|---|---|---|---|
| `imlil` | Imlil, Al Haouz | 31.136, −7.919 | Wikipedia | Did the surface change across the 10 Oct 2026 flash flood? | GUNW (coherence), SME2 |
| `asni` | Asni, Al Haouz | 31.250, −7.983 | Wikipedia | same; valley floor and road | GUNW, SME2 |
| `moulay_brahim` | Moulay Brahim | 31.286, −7.966 | Wikipedia | same; gorge and road (rock falls reported) | GUNW, SME2 |
| `al_wahda_dam` | Al Wahda dam crest area | 34.598, −5.198 | Wikipedia | Is measurable motion visible on slopes around the dam? (not a dam-safety verdict) | GUNW |
| `gharb` | Gharb plain (cropland) | 34.50, −6.00 | existing `events.py`; **VERIFY** it is cropland on the basemap | Soil moisture before/after the October rains | SME2 |
| `ksar_el_kebir` | Loukkos plain, Ksar El Kébir | 35.00, −5.90 | **VERIFY** (OSM) | Soil-moisture context of the Feb 2026 flood area | SME2 |
| `ben_guerir_mine` | OCP Benguerir open pit | **VERIFY**: OSM `landuse=quarry` polygon east of the town (town ≈ 32.23, −7.95) | OSM | Where did the mine surface change between dates? | GUNW (coherence) |
| `chefchaouen` | Rif slopes near Chefchaouen | 35.17, −5.27 | audit proxy | Is any slope motion measurable? (expect small in dry season) | GUNW |

Keep aliases in French, English and Arabic (`الحوز`, `إمليل`, `أسني`, `مولاي إبراهيم`, `سد الوحدة`, `الغرب`, `القصر الكبير`, `ابن جرير`, `شفشاون`).

Event entry for `agent.EVENTS`: `haouz`, `al haouz`, `الحوز`, `imlil`, `asni` → `20261010T000000`.
The storm lasted the whole day, so midnight is right here. If an acquisition falls **on 10 Oct**, flag that pair as ambiguous.

---

## 4. Data scope and tiers

Average sizes from the audit: GUNW ≈ 2.1 GB raw, SME2 ≈ 0.09 GB.
At 50 Mbps ≈ 22 GB/h; real speed often 20–30 % lower. Split tiers across teammates' connections if possible and merge the folders.

| Tier | Content | Files (est.) | Raw GB (est.) | Time at 50 Mbps |
|---|---|---|---|---|
| **0** | Metadata only: coverage of every site, all acquisitions 17 Jun → today, both collections | 0 | 0 | 15 min |
| **1** (tonight first) | Al Haouz: on each covering frame (asc + desc), the last pre-event pair, the pair straddling 10 Oct, the first post pair. SME2 tiles over Haouz + north sites, 20 Sep → latest. One latest VALIDATED pair per site frame. | ~6 + ~40 + ~6 | ~30 | ~1.5 h |
| **2** (overnight) | Complete PROVISIONAL chains (all nearest-neighbour pairs **including gap bridges**) for the frames covering the sites, both directions | ~55–65 | ~120 | ~5.5 h |
| **3** (after hackathon) | Remaining atlas frames, full Morocco SME2 | rest | ~100 | — |

Keep the **raw `.h5`** for the Tier 1 GUNW pairs (≈ 13 GB) so the hero analysis can be redone without re-downloading. Extract-and-delete everything else.

Extra layers to extract (decide from `data/GUNW/_structure.json` before Tier 1):
- ionosphere uncertainty;
- troposphere (hydrostatic, wet) and solid-earth-tide lookup cubes;
- the validity / water mask;
- coherence at 80 m.

Disk estimate: kept GUNW ~15–30 GB + raw Tier 1 ~13 GB + SME2 ~8 GB → **under 60 GB**.

---

## 5. Code changes

| Area | Change |
|---|---|
| `download_all.py` | `--plan <file>`, `--keep-raw`. New datasets `morocco_gunw` (site frames, nearest-neighbour pairs of any span ≤ 48 days, PROVISIONAL + VALIDATED) and `morocco_sme2` (bbox −10, 30.5, −1, 36). Extra layers in `LAYERS`/`META_KEYWORDS`. Tier field in plan rows. `plan_nisar.json` untouched; new `plan_morocco.json`. |
| `catalog.py` | Parse CRID (`P05023`, `P05036`) into `Product.crid` and maturity; expose in `summary()`. |
| `recipes/timeseries.py` | Group by `(geometry, crid)`. Check the pair graph is connected; never bridge a gap silently. Report cumulative LOS per date; give mm/yr only if span ≥ 12 months. |
| `recipes/damage.py` → coherence change | Rename the concept to "surface change (coherence loss)". It answers flash-flood, mudflow, mine and damage questions when GCOV is absent. |
| `agent.py` | New type `surface_change`; keywords FR/EN/AR (`crue`, `coulée de boue`, `éboulement`, `flash flood`, `mudflow`, `rockfall`, `سيول`, `انهيار`) with word boundaries. Flood questions without GCOV route to `surface_change` and say so. New event names. Templates and `CANNOT_SAY` for the new type. |
| `config.py` | New gazetteer (§3). Default map view centred on Morocco. |
| `events.py` | Morocco library: `haouz-flood-2026-10-10`, `haouz-soil-moisture`, `gharb-soil-moisture`, `ben-guerir-mine`, `al-wahda-surroundings`. Panama removed from the listing (kept only as a test fixture). |
| `uncertainty.py`, `agent.assess` | Per D-006 when accepted. Minimum: a 4-month chain never yields "high" confidence for slow motion. |
| tests | Synthetic: data gap with a 36-day bridge; mixed CRIDs not mixed; flood question routed to `surface_change`; Haouz event name parsed. |

---

## 6. Claude Code prompts (in order)

### P1 — Inventory, read-only except one report file
```text
/start-session Morocco data inventory
Read docs/claude/MOROCCO_PLAN.md. Do not download products. You may write only
docs/claude/morocco_inventory.md.
1. For every site in §3 (use OSM Overpass/Nominatim for the VERIFY rows; for ben_guerir_mine
   return the quarry polygon centroid and bbox), list: final lat/lon with source, and which
   NISAR GUNW (track, frame, direction) and SME2 frames cover it (ASF search, intersectsWith=POINT).
2. For each of those frames: every GUNW from 2026-06-17 to today, BOTH collections
   (PROVISIONAL and VALIDATED), with ref/sec dates, span, CRID, size, full/partial.
   Mark pairs that bridge the 2026-07-27 → 08-10 gap and say if the chain is connected.
3. Al Haouz: for each covering frame, the pair straddling 2026-10-10, the last pre-event pair
   and the first post pair. Flag any acquisition on 10 Oct itself.
4. SME2 with bbox (-10, 30.5, -1, 36) from 2026-09-20 to today: count and GB.
5. Read data/GUNW/_structure.json if it exists and list the dataset paths for: ionosphere
   uncertainty, troposphere (hydrostatic/wet), solid earth tide, validity/water mask, coherence 80 m.
6. Table per tier (§4): files, raw GB, hours at 50 Mbps. Flag every difference from the plan.
```

### P2 — Record the decision
```text
/decision Morocco territory data scope
Use the D-007 text in docs/claude/MOROCCO_PLAN.md §2, updated with the numbers from
docs/claude/morocco_inventory.md. Status Proposed until I confirm. If I confirm, mark D-005
"Superseded by D-007" and add §5 items to STATUS "Next".
```

### P3 — Downloader and plan
```text
Implement the download_all.py part of docs/claude/MOROCCO_PLAN.md §4–§5, using the inventory.
- tools/make_morocco_plan.py builds plan_morocco.json from the inventory (no edit to
  plan_nisar.json), with a "tier" field and parts = tiers.
- --plan, --keep-raw (keep the .h5 next to the extracted layers), extra layers from the
  _structure.json paths, nearest-neighbour pairs up to 48 days, VALIDATED collection support.
- Default behaviour without new flags must stay identical. Tests for: plan filter, gap-bridge
  pair kept, extra layers written, catalog still indexes the folder. Run tests, report n/N.
Do not run any download. Do not read or print any token.
```

### P4 — Download (you, in PowerShell, not in Claude Code)
```powershell
$env:EARTHDATA_TOKEN = "<new token>"
python download_all.py status --plan plan_morocco.json
python download_all.py run --plan plan_morocco.json --part 1 --workers 3 --keep-raw --out D:\nisar_data
# check /health and /catalog, then:
python download_all.py run --plan plan_morocco.json --part 2 --workers 3 --out D:\nisar_data
```

### P5 — Backend for Morocco
```text
Implement docs/claude/MOROCCO_PLAN.md §5 for catalog.py, timeseries.py, damage.py,
agent.py, config.py, events.py and the tests. Use the science-check skill on every change.
Keep the recipe contract. Update mock.py and docs/API_CONTRACT.md for new fact keys.
Run tests and report n/N. Show me the new verdict sentences in FR, EN and AR before finishing.
```

### P6 — Real-data check
```text
With NISAR_DATA pointing at the downloaded data and NISAR_OFFLINE=1, run agent.investigate for
each event in events.py and for each site in the gazetteer. For each: type, products used (CRID),
pairs, valid-pixel fraction at the point, verdict. Flag any site with no valid pixels in either
direction and propose a better point within 2 km using the coherence map. Then run /demo-check.
```

---

## 7. What we will say on stage (and not say)

- **Say:** "Across the 10 October 2026 storm, NISAR shows where the surface changed in Al Haouz, with the exact radar dates, quality and limits."
- **Say:** "Soil moisture rose after the October rains (provisional product)."
- **Do not say:**
  - that it measured flood depth or duration;
  - that it confirmed damage (coherence loss is not damage);
  - that it measured subsidence rates over 4 months;
  - that the dam is safe or unsafe.

## Sources
- ASF NISAR availability: https://nisar-docs.asf.alaska.edu/availability-overview
- ASF GUNW guide: https://nisar-docs.asf.alaska.edu/gunw
- ASF known issues (BETA): https://nisar-docs.asf.alaska.edu/product-known-issues
- ASF known issues (PROVISIONAL): https://nisar-docs.asf.alaska.edu/provisional-known-issues
- Sign convention (secondary): https://github.com/Dkashkush/OpenSAR-Explorer · https://github.com/aria-tools/ARIA-tools · https://storymaps.arcgis.com/stories/c8f85d20b73c48fd8e89f8eef49bc60b
- Al Haouz floods: https://fr.hespress.com/491813-haut-atlas-de-violentes-crues-eclair-frappent-al-haouz.html
- Al Wahda dam: https://en.wikipedia.org/wiki/Al_Wahda_Dam_(Morocco)
- Imlil / Asni / Moulay Brahim: Wikipedia articles
- Souss-Massa subsidence: https://ui.adsabs.harvard.edu/abs/2022AGUFM.G42D0247R
