# Notes for Youkaoui: integration of backend/water (15 Nov 2026)

`backend/water/` and `backend/tests/test_water.py` are vendored as-is from `nisar-water` (commit 3fae8a0) and never
edited in NASA_SAR. The integration code is `backend/science/water.py`, `backend/science/cases.py` and
`backend/api_v2.py`. `python backend/tests/test_water.py`: 32/32, including "reservoir case validates as CaseStudy".

## What the integration does
- `bin-el-ouidane-2026` (kind `method`) is a case id. `reservoir_case.json` is validated as given (final, 3 findings,
  4 figures, 32 passes, 4 limits); no number is recomputed. It is written to `backend/cases/bin-el-ouidane-2026.json`
  and served at `/api/cases/bin-el-ouidane-2026`.
- `haouz_open_water.json`: `findings[]` (`open_water_change`, your label kept), `figures[]` (`clouds.png`) and
  `limits[]` are appended to `haouz-flood-2026`. Its headline ("candidate surface change, no clear change") does not
  change. Nothing is written into `results/`.
- Urls `water/outputs/figures/<f>` and `water/outputs/rasters/<f>` are served at `/api/water/figures/<f>` and
  `/api/water/rasters/<f>` (png / jpg / webp, path checks). `raster_index.json` is served at
  `/api/water/raster-index` with the same url mapping.

## One problem in the package (please fix in v2)
- **List-valued template params.** `reservoir_case.json` → `limits[1].params.crid = ["P05023", "P05036"]` and
  `limits[3].params.ci95_km2 = [0.35, 2.18]`. The frontend's `TemplateParam` (zod) accepts a string, a number, a
  Measurement, `{date}`, `{term}` or `{localized}`, not an array: the frontend would reject the whole case. The
  loader turns them into scalars with the same values (`crid: "P05023, P05036"`, `ci95_km2_low: 0.35`,
  `ci95_km2_high: 2.18`). Writing them that way in the JSON would let the loader pass them unchanged.
