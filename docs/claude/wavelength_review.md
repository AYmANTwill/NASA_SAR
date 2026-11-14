# Review of the per-product wavelength change (2026-11-14)

Scope: `backend/recipes/wavelength.py`, the `backend/recipes/displacement.py` change, `backend/tests/test_wavelength.py`. Read-only review; nothing in these files was changed.
Checked against the real catalog (103 GUNW products) with a scratchpad script, `wavelength_m(p)` on each.

## Checklist
| Item | Result |
|---|---|
| centerFrequency unit and value of c | **OK.** Hz, `C_M_S = 299_792_458.0` (`wavelength.py:22`); `L_BAND_HZ = (1.0e9, 2.0e9)` rejects a value written in MHz (`:25`, tested with `1239.0`). |
| `frequencyA` used | **OK for the .h5** (`FREQ_SUFFIX = "frequencyA/centerFrequency"`, `:24`; first matching dataset). **Weak for the npz:** `_from_npz` accepts any key ending in `centerFrequency` (`:37`), not specifically frequencyA. Harmless today: no npz stores it (see problem 1). |
| Missing metadata gives a warning, not a silent 0.2384 | **OK in code:** a warning is logged and the source string says `config WAVELENGTH_M (no centerFrequency in the product)` (`:63-64`), and `displacement` puts it in `report["wavelength"]`. **Limit:** the warning is logged once per folder (`lru_cache`), not per request. |
| One wavelength per product | **OK.** `_los_cm` calls `wavelength_m(p)` once and uses it for the correction screens and for the displacement (`displacement.py:37-43`). |
| No consumer still uses 0.2384 / 11.92 / 1.90 cm/rad (grep of `backend/`) | **Not fully.** `config.FRINGE_CM = WAVELENGTH_M/2*100` (11.92 cm, `config.py:26`) is still used by `discoveries.py:111-113, 234` (fringes per zone; discoveries are off by default). No `1.90` found. The `0.2384` values in `tests/test_all.py:1109-1156` are explicit arguments in unit tests of `corrections`, not consumers. `config.WAVELENGTH_M` itself is the intended fallback. |
| A test expects 12.10 and 12.20 cm | **Partly.** 12.10 cm (40 MHz) is tested (`test_wavelength.py:88`). The 20 MHz mode is tested only as a wavelength, 0.24393 m (`:56`), not as 12.20 cm of LOS per fringe. |

## Problems found
1. **33 of the 103 GUNW products still get 0.2384 m** (49 get 0.24196 m from the raw .h5, 21 get 0.24393 m; none come from the npz). Cause: the product has no kept raw `.h5`, and the downloader does not store `centerFrequency` in `radar_geometry.npz` (`download_all.py:84-95`: `META_KEYWORDS`/`EXTRA_SHORT_META` do not list it). For these products the displacement is 1.5 to 2.3 % off (see REPORT section 8, item 8), with a warning logged and the source recorded. Fix: add `centerFrequency` to the short metadata of the downloader and run `rebuild-npz` where the `.h5` is kept; for products without `.h5` the value must be re-read at download time. Not done (I may not edit `download_all.py`).
   All eight Panama co-seismic pairs have the value from the raw .h5 (checked with `los_vector` in Phase 5 and the Phase 3 runs).
2. `config.FRINGE_CM` (11.92 cm) is stale for products at 1239 MHz (12.10 cm) and 1229 MHz (12.20 cm). Only `discoveries.py` uses it (disabled by default). Suggest a per-product value if discoveries are re-enabled.
3. No test checks 12.20 cm for the 20 MHz mode (small gap).
4. The warning appears once per folder per process; a long-running API will not repeat it. The `report["wavelength"]["source"]` field is the reliable place to show it.

## Verdict
The code of the change is **OK**; the data coverage is **not**: 33 products still use the fallback. Product-level fix needs a downloader change (problem 1).
