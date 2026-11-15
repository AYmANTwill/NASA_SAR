# Water U-Net

> Model card (weights, architecture, figures, `predict.py`): [model/MODEL.md](model/MODEL.md)

`backend/water/` segments open water in NISAR GCOV HH/HV imagery. It is a self-contained science pipeline:
large rasters and checkpoints remain under `$NASA_DATA` (default `~/nasa_data`, outside the repo), while code, small results, figures and
JSON contracts live in the repository.

## What it does

The model is a ResNet-34 U-Net trained on 10 m Sen1Floods11 Sentinel-1 `[VV,VH]` chips. NISAR frequency-A
`[HH,HV]` is mapped by polarization role to those two input slots. This cross-sensor mapping is an assumption,
so every NISAR result is checked against OPERA DSWx-HLS and compared with a global cross-pol threshold.

The fair baseline is one global VH threshold fitted once on the Sen1Floods11 training split. The U-Net
probability threshold is fitted once on the validation split. `outputs/thresholds.json` is the source of truth;
neither threshold may be retuned on the test split, Bolivia hold-out, NISAR, or DSWx.

AdaBN variants recompute BatchNorm running statistics from unlabeled NISAR tiles without gradients. They are
reported as transfer variants, not extra supervised training.

**Held-out protocol (headline).** The NISAR method variant is chosen on ONE track only (the selection track in
`outputs/aoi.json`; track 44 ascending for Bin El Ouidane). IoU / precision / recall are then reported on the
OTHER tracks (95 descending, 116 ascending), never used for any choice, with 95% bootstrap intervals over dates
(`heldout_eval.py` -> `outputs/heldout_eval.json`). That held-out number is the headline. The pooled all-track
rows in `results.csv` are kept only as a "selection set" figure (their notes say so). The model-minus-DSWx area
bias is reported with its interval; a bias correction is fitted on the selection track only and tested on the
held-out tracks. The U-Net probability threshold stays at the Sentinel-1 validation value; NISAR never tunes it.

**Target choice.** `select_target.py` compares Al Massira, Bin El Ouidane and Al Wahda on OPERA DSWx browse
areas. A DSWx acquisition is an outlier if it differs by more than 15% from the median of its time neighbours
and of all acquisitions within +-3 days (removed iteratively, worst first); outliers are flagged "dswx outlier"
and ignored. Genuine change is the range of the 30-day rolling median of the cleaned series. If no reservoir
exceeds 10%, the site with the best data is chosen and the case is framed as monitoring ("stable within noise"
is a valid result). Evidence: `outputs/reservoir_comparison.csv`, `outputs/dswx_outliers.csv`, `aoi.json`.

**The outlier check catches optical errors (`outlier_figure.py`).** At Bin El Ouidane it removed two Sentinel-2
DSWx acquisitions in late June. On 29 June (S2B) DSWx masked part of the reservoir as **snow** (class 252, cyan in
the browse) in June, so its water area dropped far below its neighbours, while NISAR the same day kept the normal
area. Without the check that date would have been the "largest change" and driven the case. Figure:
`outputs/figures/dswx_outlier_check.png`; values: `outputs/dswx_outlier_check.json`, `outputs/dswx_outliers.csv`.

**Mask diagnostics (`diagnose_mask.py`).** The earlier Esri basemap is a mosaic of old WorldView scenes (dates
per point in `outputs/diagnostics.json`), so it is not used to judge the mask. The diagnostic panels
(`figures/diagnostic_<date>.png`) use the same HLS scene that the matched DSWx was computed from. False alarms
are split into shoreline, exposed lakebed, steep slope and other land, per track and per set.

**Water-level constraint (`water_level.py`, evaluated by `water_level_eval.py`; NOT adopted).** A reservoir
surface is flat: the water level is the median DEM elevation on the boundary of the high-confidence core
(probability >= 0.9), and predicted water higher than level + T m is rejected. T is chosen on the selection track
by minimising |area bias| and the result is scored once on the held-out tracks (`outputs/water_level_eval.json`).
Adoption rule: held-out |area bias| must decrease and held-out IoU must not decrease. The constraint raises
precision with recall unchanged, but it does not reduce |area bias| (removing false alarms exposes misses), so the
operational products do not use it. Limits: the DEM (OPERA DSWx B10_DEM layer) is flat over the reservoir at the
level of its own acquisition, so the estimated "level" is that frozen DEM surface, not the current water level;
the rule applies to reservoirs and lakes only (one flat surface) and is NOT applied to the Haouz flash-flood
finding, where water sits in sloping valley floors. The slope filter (`fix_slope_eval.py`) was also rejected:
it raises IoU but biases the area strongly low (`outputs/fix_slope_eval.json`).

## Fine-tuning on NISAR with DSWx labels (tested, NOT adopted)

`finetune/` fine-tunes the operational model on NISAR scenes of other Moroccan reservoirs with same-day DSWx labels
(clear, outlier-checked). Split by site: training Al_Wahda, Idriss_1er, Mohammed_V, Oued_El_Makhazine, Sidi_Mohamed_Ben_Abdellah; validation Al_Massira (early
stopping, variant choice); the case reservoir is fully held out. Variants: NISAR only (validation IoU
0.469 → 0.933) and NISAR + Sentinel-1 50/50
(0.469 → 0.916); chosen: **nisar**.

Held-out reservoir, all 28 clear dates (`outputs/finetune/eval.json`, 95% date-bootstrap intervals):

| Model | IoU | Precision | Recall | Area bias km² |
|---|---|---|---|---|
| current | 0.802 [0.775, 0.828] | 0.871 | 0.910 | +1.41 [+0.51, +2.29] |
| current water level | 0.858 [0.835, 0.880] | 0.938 | 0.910 | -0.84 [-1.54, -0.12] |
| finetuned | 0.815 [0.740, 0.884] | 0.990 | 0.822 | -4.59 [-6.54, -2.82] |
| finetuned water level | 0.817 [0.742, 0.886] | 0.992 | 0.822 | -4.67 [-6.61, -2.90] |

Rule: replace only if |area bias| decreases without lowering IoU. **Decision: keep current model: fine-tuned model does not lower |area bias| without lowering IoU on the held-out reservoir.** The fine-tuned
model is far more precise and much better on tracks 95/116, but it under-maps water (large negative bias) and is
unstable on track 44, so the operational products keep the current model. This is a result, not a failure: the
next step is a bias-aware objective (area term in the loss) and more training sites.

## Inputs and outputs

- `$NASA_DATA/sen1floods11/`: training/validation/test chips.
- `$NASA_DATA/models/unet_s1.pt`: epoch-46 checkpoint; SHA-256 is recorded in
  `outputs/train_config.json`.
- `$NASA_DATA/nisar/`: remotely window-read GCOV HH/HV GeoTIFFs.
- `$NASA_DATA/dswx/`: reprojected DSWx WTR windows.
- `$NASA_DATA/outputs/`: probabilities, masks, change and uncertainty GeoTIFFs.
- `backend/water/outputs/heldout_eval.json`: HEADLINE held-out-track metrics, variant choice, area bias.
- `backend/water/outputs/heldout_per_date.csv`: per-date confusion counts and set (selection / held-out).
- `backend/water/outputs/reservoir_comparison.csv`, `dswx_outliers.csv`: target-choice evidence.
- `backend/water/outputs/figures/gallery/`: one validation map per NISAR date; `figures/gallery_contact_sheet.png`.
- `backend/water/outputs/figures/clouds.png` + `outputs/clouds_figure.json`: same-day cloudy DSWx vs NISAR.
- `backend/water/outputs/results.csv`: pooled metrics. Every S1 IoU/precision/recall row has a chip-bootstrap
  95% interval.
- `backend/water/outputs/classifier_metrics.json`: beta classifier precision/recall on the Bolivia event that
  was excluded from training.
- `backend/water/outputs/water_area_timeseries.csv`: one row per NISAR date and track. Partial DSWx coverage
  and possible wind-effect dates remain present and flagged.
- `backend/water/outputs/orbit_consistency.csv`: nearby ascending/descending comparisons.
- `backend/water/outputs/change_pair.json`: selected clear-DSWx change pair, fixed threshold and MC settings.
- `backend/water/outputs/haouz_flooded_area.json`: measured Haouz finding, figures and limits.
- `results/haouz-flood-2026/findings.json`: the same Haouz evidence shaped for `science.cases`.
- `backend/water/outputs/reservoir_case.json`: unregistered reservoir method-case draft.
- `backend/water/outputs/raster_index.json`: PNG paths and EPSG:4326 outer-edge bounds.
- `backend/water/outputs/figures/`: 300 dpi slide exports.

`haouz_flooded_area.json` and the assembler input contain:

```json
{
  "date": "2026-10-10T00:00:00Z",
  "bbox": [-8.2, 31.05, -7.75, 31.45],
  "products": ["GCOV_T023_F073_20261001_20261001", "..."],
  "findings": [{"id": "flooded_area", "label": {"fr": "...", "en": "...", "ar": "..."},
    "nisar": {"value": 0.0, "uncertainty": 0.1, "unit": "km2", "sigma": 1},
    "reference": null, "reference_source": null, "agreement": "no_reference"}],
  "figures": [{"id": "haouz_backscatter_change", "raster": "backscatter_change_T023D.tif",
    "title": {"fr": "...", "en": "...", "ar": "..."},
    "caption": {"template": "backend.water_haouz", "params": {}, "text": {"fr": "...", "en": "...", "ar": "..."}},
    "layer": {"kind": "backscatter_change", "unit": "dB", "palette": "diverging_displacement", "min": -8, "max": 8}}],
  "limits": [{"fr": "...", "en": "...", "ar": "..."}]
}
```

The values above are illustrative schema values only; runners overwrite them from measured outputs. Agreement
is always produced with `science.case_models.agreement`, never typed independently. The runner creates tiny,
ignored GDAL VRT views in `data/GCOV/` so the existing catalog can resolve the four product ids and construct the
full acquisition/publication timeline; the large source windows remain under `nasa_data`.

## Run order

Create or activate the external environment, then install after checking disk space:

```powershell
python -m pip install --no-cache-dir -r backend/water/requirements.txt
```

From `backend/water/`:

```powershell
python s1_eval.py                 # bootstrap S1 metrics, fixed thresholds and checkpoint metadata
python nisar_search.py --all      # reservoir CMR/DSWx inventory
python select_target.py           # three-way comparison and target choice
python nisar_prep.py --tree       # authenticated remote HDF5 layout check
python nisar_prep.py              # window reads only; no full granules
python adabn.py                   # optional transfer checkpoints
python evaluate.py                # U-Net/baselines versus DSWx, per date
python heldout_eval.py            # variant chosen on the selection track; held-out headline; area bias
python timeseries.py              # tracks; wind / partial / outlier flags; orbit consistency
python save_probs.py              # probability GeoTIFFs for the chosen variant only (data budget)
python change_detect.py --mc 20   # change pair (clean, non-wind dates), change map, MC-dropout products
python haouz_flood.py --mc 20     # Haouz pre/post finding and assembler input
python reservoir_case.py          # draft reservoir method case (nested objects validated)
python output_assets.py           # EPSG:4326 PNG index and slide figures
python gallery.py                 # per-date validation maps + contact sheet
python clouds_figure.py           # same-day cloudy optical vs radar figure
python handoff_doc.py             # regenerates docs/claude/WATER_HANDOFF.md from the output files
```

Validate without editing the frozen case fixture:

```powershell
cd backend
python -m science.cases --results ..\results --offline --dry-run
python tests\test_science.py
```

## Where each number comes from

- S1 IoU, precision and recall: pooled confusion counts across chips; 95% intervals are 1,000 paired chip
  bootstrap resamples with seed 0.
- U-Net-minus-baseline interval: method differences computed inside the same paired bootstrap resamples.
- Reservoir water area: count of thresholded valid pixels times projected pixel area.
- DSWx water area: WTR classes 1 or 2 on valid WTR pixels; dates below 95% valid coverage are retained but
  excluded from pair selection and comparisons.
- Held-out NISAR IoU / precision / recall: pooled confusion counts over held-out-track dates; 95% intervals are
  1,000 bootstrap resamples over dates (seed 0). Excluded dates: DSWx < 95% valid, "dswx outlier".
- Area bias: model area minus DSWx area on the same DSWx-valid pixels, per date; mean with a date-bootstrap
  interval. Corrections (additive, multiplicative) are fitted on the selection track only.
- Orbit consistency: mean absolute model-area difference in km² and percent for closest ascending/descending
  observations no more than three days apart.
- Possible wind effect: model area more than 20% below the mean of neighbouring dates on the same track.
- Haouz flooded area: post-water AND NOT pre-water for same-track pairs bracketing 10 October 2026. The finding
  is the mean of usable track estimates. One-sigma uncertainty combines MC-dropout area standard deviation and
  half the ascending/descending range in quadrature. If only one track is usable, the MC term remains non-zero
  and the missing orbit comparison is stated.

## Limits

- Sentinel-1 C-band VV/VH to NISAR L-band HH/HV is domain transfer, not sensor equivalence.
- DSWx is a nearby-date optical weak reference; cloud, shadow, shoreline mixing and acquisition-time mismatch
  can change agreement.
- Wind can brighten open water in SAR and reduce predicted area; flagged dates are never silently removed.
- Terrain layover and shadow affect the narrow High Atlas valleys.
- A flash flood may drain before NISAR's 12-day revisit. A measured near-zero extent means no persistent open
  water was detectable at the revisit, not that flooding did not occur.
- AdaBN failure mode: on some dates (mostly track 95) the AdaBN variant misses straight-edged strips of very
  dark, homogeneous water that the source-only model detects. The gap is in the model, not in tiling
  (whole-scene inference shows it too) and not in the data (water HV is smooth across the strip). See the gallery.
- Model water area is biased high relative to DSWx (shoreline mixing, false alarms in the north-east arm).
- The water assets are figure images until the proposed palette/layer/series additions are approved.


## Versions (2026-11-15)

| Version | Model | Case water-area change | Status |
|---|---|---|---|
| v1 | U-Net + AdaBN (Sentinel-1 trained, no NISAR labels) | single pair T44: -1.91 ± 2.04 km² vs DSWx -2.06 | first delivery |
| v1.1 | v1 | same; contract fixes (scalar params, FR/AR text, clouds first) | delivered |
| v1.2 | v1 | **3 tracks**: -2.76 ± 0.53 km² vs DSWx -1.98 (`change_multitrack.json`) | this version |
| v2 | v1 fine-tuned on NISAR with DSWx labels of 6 other reservoirs (`finetune/`, run v2) | 3 tracks: -0.98 ± 0.59 vs DSWx -1.98 | not adopted |
| v3 | v2 + incidence-angle input + 7 more reservoirs (13 in all, 182 scenes); test reservoir Oued El Makhazine never used | 3 tracks: -1.59 ± 0.20 vs DSWx -1.98; IoU 0.929 on the test reservoir (v1: 0.193) | general model |
| **v3site** | v3 + this reservoir's own passes after 2026-10-03 (more than one revisit after the case period; shaded, never scored) | **3 tracks: -1.83 ± 0.14 vs DSWx -1.98; held-out IoU 0.948 [0.944, 0.952] on tracks 95/116, dates up to 2026-10-03; test reservoir IoU 0.933** | **shipped** |

**v3 / v3site protocol.** Test reservoir (Oued El Makhazine) fixed before training and never used to train or choose.
Validation reservoir Al Massira (epoch and probability threshold). v3site adds Bin El Ouidane DSWx labels only for
passes after 2026-10-03; every reported number uses dates up to 2026-10-03, and the case dates (June–September) are
never in training. The variant is still chosen on track 44 only (v3site 0.951 vs v1 0.851). A model that memorised
the lake would show no change; v3site's change (-1.83) matches DSWx (-1.98). Full comparison:
`outputs/finetune/v3/eval.json`. Haouz with v3site: 0.00 ± 0.01 km² of new persistent open water (consistent with zero).

**Why 3 tracks.** On one track the area of a model varies by about ±1.7 km² from date to date (v1 and v2 alike),
so a single pair of dates carries about ±2.4 km² of noise. The change is now the mean, over every track with a clean
pass within ±5 days of both case dates, of the per-track change (a constant per-track bias cancels); 1σ = standard
error over tracks. DSWx is processed the same way. This showed that v1 over-states the June→September drop and v2
under-states it.

**Why v2 was not adopted.** Higher pixel accuracy (held-out IoU 0.934 vs 0.763 on tracks 95/116, which were also
frequent in its training), but its error on track 44 at the case reservoir (incidence 34°) varies from date to date,
so its case change is off. The v1 fine-tuning had trained on 10 of 75 scenes (disk-guard refusals); `ft_prep.py`
now stops when more than 20% of reads fail.
