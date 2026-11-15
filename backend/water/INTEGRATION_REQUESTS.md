# Integration requests from backend/water (for Ayman)

1. **Contract:** add `"bin-el-ouidane-2026"` to `CaseId` and `CASE_KIND` (`"method"`) in `backend/science/case_models.py`,
   and to the case order in `cases.py`. Then `backend/water/outputs/reservoir_case.json` validates as `CaseStudy`
   (`backend/tests/test_water.py` switches from nested checks to the full check automatically).
2. **Haouz:** read `backend/water/outputs/haouz_open_water.json` as an extra source of `haouz-flood-2026`:
   append its `findings[]` (`open_water_change`) and `figures[]` (`clouds.png`), and its `limits`.
   `results/haouz-flood-2026/findings.json` is not touched by us.
3. **Static files:** serve `backend/water/outputs/figures/*.png` and `backend/water/outputs/rasters/*.png` from the
   same origin (e.g. `/api/water/...`), so the offline service worker caches them. Figure `url`s are written as
   `water/outputs/...` relative to `backend/`.
4. **Map layers:** `backend/water/outputs/raster_index.json` lists 3 RGBA PNG layers (before, after, change) with
   EPSG:4326 bounds. They are images, not `RasterLayer` (no water palette in the contract yet).
