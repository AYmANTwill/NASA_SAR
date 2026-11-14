# Morocco plan

Scope, sites, frames, download tiers and demo library of NISAR Pulse for Morocco. Built from
`tools/make_morocco_plan.py`, `plan_morocco.json` (scheme `morocco-v1`) and the README. Code comments refer to the
sections below (§4 tiers, §5 demo library).

## 1. Scope
- Every answer in the demo is about Morocco. The app's map opens on Morocco (`/health` → `map_view`).
- **Panama (M7.7, 9 Oct 2026, USGS us6000u18k) is a global VALIDATION event, outside the Morocco scope.** It is
  the only large, unambiguous NISAR signal we have and our line-of-sight sign check. It is listed only with
  `/events?include_validation=true` and downloaded with its own plan (`plan_validation.json`, README → Validation).
- Venezuela is a synthetic test fixture only.

## 2. Sites
Coordinates as used by `tools/make_morocco_plan.py` and `backend/config.py` (OSM-checked on 2026-11-12):

| site | lat, lon | role |
|---|---|---|
| Imlil | 31.136, -7.919 | Al Haouz flash flood (10 Oct 2026) |
| Asni | 31.250, -7.983 | Al Haouz flash flood; stands for the Haouz region |
| Moulay Brahim | 31.286, -7.966 | Al Haouz flash flood |
| Al Wahda dam | 34.598, -5.198 | slow motion (OSM dam polygon, not the old point ~5 km away) |
| Gharb plain | 34.50, -6.00 | soil moisture |
| Ksar el Kebir | 35.0105, -5.9031 | farmland point proposed by the inventory (confirm on a basemap) |
| Ben Guerir mine | 32.25825, -7.82355 | mine centroid; no quarry polygon checked, so the event is "not validated" |
| Chefchaouen | 35.17, -5.27 | Rif slopes |

## 3. Frames
- **Minimal frames** (cover every site): 116/19 A, 44/17 A, 44/18 A, 95/71 D, 23/73 D, 23/72 D.
- **Al Haouz frames**: 23/73 D, 44/17 A, 95/73 D (95/73 barely covers Asni and is coherent there too rarely to vote).
- Known acquisition gap: 2026-07-27 → 2026-08-10. A 24-day pair across it is a "bridge" pair; it is kept and said.

## 4. Download tiers (`plan_morocco.json`)
With `--plan`, "part N" means tier N; `plan_nisar.json` is never touched.

| tier | files | size | content |
|---|---|---|---|
| 1 | 31 | 16.3 GB | Al Haouz: last pair before, pair across, first pair after 10 Oct 2026 (one per frame); SME2 at the sites since 20 Sep; last VALIDATED pair per frame |
| 2 | 47 | 111.4 GB | full nearest-neighbour chains of the minimal frames (pairs <= 48 days, gap bridges included) |
| 3 | 432 | 32.7 GB | rest of the SME2 soil moisture over the box -10, 30.5, -1, 36 |

Filters: no "Partial" duplicates (unless `--include-partial`), nothing above 48 days, no pair that skips an
acquisition except across the data gap, one SME2 version per date, CRIDs (provisional P05023, validated P05036)
never mixed in one chain. GUNW rows carry `extra_layers: true`: the ionosphere uncertainty and mask GeoTIFFs and, in
`radar_geometry.npz`, the troposphere and solid-earth-tide cubes with their axes (see the README).

```powershell
python tools/make_morocco_plan.py --dry-run
python tools/make_morocco_plan.py
python download_all.py status --plan plan_morocco.json
python download_all.py run --plan plan_morocco.json --part 1 --workers 3 --keep-raw --out D:\nisar_data
```

## 5. Demo library (`backend/events.py`)
| id | question | recipe |
|---|---|---|
| `haouz-flood-2026-10-10` | did the ground change at Asni in the 10 Oct 2026 flash flood? | surface change (whole-day event) |
| `haouz-soil-moisture` | soil moisture at Asni | soil moisture |
| `gharb-soil-moisture` | soil moisture in the Gharb | soil moisture |
| `ben-guerir-mine` | where did the mine surface change? (not validated: no polygon) | surface change, latest mode |
| `al-wahda-surroundings` | is the ground around the Al Wahda dam moving? | slow motion |

Rules that hold for every answer (do not weaken):
- surface change is measured against a baseline pair and the frame background, never called damage, confidence
  medium at most;
- no mm/yr for a record shorter than 12 months (`MIN_RATE_DAYS = 365`);
- signed line-of-sight answers say "sign unverified" (confidence low, no alert) until `NISAR_LOS_SIGN_VERIFIED=1`;
  the sign basis is the documented convention (ARIA-tools, MintPy prep_nisar);
- discoveries are off by default; the safe mode is `NISAR_DISCOVERIES_MODE=consistent`;
- a soil-moisture change inside the product's uncertainty is not a change (confidence low);
- pairs with a flat unwrapped phase or a median coherence below 0.15 are rejected and listed.

## 6. Validation
Outside the Morocco scope; commands and outputs in the README, section "Validation".
