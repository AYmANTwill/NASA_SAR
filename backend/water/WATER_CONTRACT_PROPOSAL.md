# Water U-Net contract proposal

Decision note for Ayman and Houssam. This file proposes additions only; it does not change the frozen
`docs/CASE_CONTRACT.md`, `frontend/src/api/contract.ts`, or the frontend palettes.

## Why this is not duplicate work

The existing `backend/recipes/backscatter.py` answers point questions from GCOV, and
`backend/ml_classifier.py` is a beta multi-class before/after XGBoost classifier. `backend/water/` instead
provides a spatial water-segmentation model trained on Sentinel-1, a fixed global-threshold baseline, transfer
to NISAR HH/HV, DSWx validation, reservoir time series, and uncertainty. It emits inputs for the existing
`science.cases` assembler and small frontend-ready image assets; it does not replace either existing module.

## Proposed contract additions

1. Add palette `water_mask` with transparent non-water and `#2684ff` water, plus optional
   `water_change` stops for loss `#d62728`, unchanged transparent, and gain `#1f77b4`.
2. Add `RasterLayer.kind` values `water_mask`, `water_change`, and `water_uncertainty`.
3. Add `SeriesId` value `water_area`; unit is already `km2`.
4. Register method case id `bin-el-ouidane-2026` after team approval. The React case list already renders
   backend summaries dynamically and its case id is a string, so this needs no new page component. Backend work
   is limited to `science.case_models.CASE_KIND`, the store order, a generic method-case assembler input, and
   the corresponding contract tests. Until approval, the complete draft stays at
   `backend/water/outputs/reservoir_case.json` and is not added to routes.
5. Serve committed water PNGs through a backend static route or copy them into the case figure store. Every
   entry in `backend/water/outputs/raster_index.json` uses EPSG:4326 outer-edge bounds `[west,south,east,north]`.

## Unified-interface placement now

The Haouz result already has a supported place: `science.cases` reads
`results/haouz-flood-2026/findings.json`, copies its figures, validates the case, and exposes it through
`GET /api/cases/haouz-flood-2026`. The water runner writes that assembler input from the same measured payload
as `backend/water/outputs/haouz_flooded_area.json`; no frontend fork is needed.

The reservoir result should appear as a fifth card titled **Water U-Net — Bin El Ouidane** only after the
frozen-case owners approve the new case id. This is the Water U-Net workstream's primary interface identity;
the Haouz finding is an application of the model, not its ownership boundary.
Before approval, figures can still be reviewed through `backend/water/preview_app.py`.

