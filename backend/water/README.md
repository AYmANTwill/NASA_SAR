# Water U-Net workstream

This package is the Water U-Net contribution. Its primary product is a dedicated method case,
**Water U-Net — Bin El Ouidane**, with the Haouz flooded-area result as a second application of the same model.

It does not modify or replace:

- `backend/ml_classifier.py` — the team's beta XGBoost multi-class change classifier;
- `backend/recipes/backscatter.py` — the team's rule-based point flood/deforestation recipe;
- `backend/recipes/damage.py` — the team's coherence surface-change analysis;
- any frontend source or frozen contract.

The package owns Sentinel-1 training/evaluation, the fixed global-threshold baseline, NISAR HH/HV transfer,
AdaBN variants, DSWx validation, water-area time series, change maps, uncertainty, and its generated outputs.

## Unified-interface placement

The current frontend renders case summaries returned by `/api/cases` dynamically, so no new page component is
needed. Registering `bin-el-ouidane-2026` requires a small backend contract decision: add the method-case id to
`science.case_models.CASE_KIND` and the case store order. Until Ayman and Houssam approve that frozen-contract
change, the complete draft remains at `outputs/reservoir_case.json`; the exact proposal is
`docs/claude/WATER_CONTRACT_PROPOSAL.md`.

The Haouz application is exported through the generic `results/haouz-flood-2026/findings.json` importer. That
does not transfer ownership of this model: the finding records the Water U-Net method and the package remains
under `backend/water/`.

See `docs/claude/WATER_UNET.md` for inputs, commands, output schemas, provenance, uncertainty and limitations.

