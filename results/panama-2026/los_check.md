# LOS vector check of the Panama pairs (2026-11-15)

Source of the vectors: `decompose.los_vector` (`backend/recipes/decompose.py`), read from `radar_geometry.npz` (`losUnitVectorX/Y`, 20 x ~673 x ~687 cubes).
The file defines the vector **from the target to the sensor** in east-north-up (`results/h5_attributes.txt:15`). The code never flipped it (the file's sign already
agrees with the nominal left-looking side). The fit uses the **track mean** of the cube (`panama_fault.py:122`); up = sqrt(1 - e² - n²).

| Pair | Direction | Source | File mean (E, N) | Frame centre (E, N, U) | **Used in the fit (E, N, U)** | East range over the cube |
|---|---|---|---|---|---|---|
| T076_F006_20261005_20261017 | asc | file | +0.640, +0.133 | +0.648, +0.135, 0.750 | **+0.640, +0.133, 0.757** | +0.470 to +0.764 |
| T076_F005_20261005_20261017 | asc | file | +0.640, +0.131 | +0.648, +0.132, 0.750 | **+0.640, +0.131, 0.757** | +0.471 to +0.764 |
| T004_F005_20260930_20261012 | asc | file | +0.641, +0.131 | +0.648, +0.132, 0.750 | **+0.641, +0.131, 0.757** | +0.472 to +0.763 |
| T040_F085_20261002_20261014 | desc | file | -0.633, +0.164 | -0.641, +0.166, 0.750 | **-0.633, +0.164, 0.756** | -0.756 to -0.465 |
| T040_F084_20261002_20261014 | desc | file | -0.633, +0.166 | -0.640, +0.168, 0.750 | **-0.633, +0.166, 0.756** | -0.755 to -0.465 |
| T141_F085_20260927_20261009 (two product variants, `2000` and `4000`) | desc | file | -0.633, +0.164 | -0.640, +0.166, 0.750 | **-0.633, +0.164, 0.756** | -0.756 to -0.464 |
| T141_F084_20260927_20261009 | desc | file | -0.633, +0.166 | -0.640, +0.168, 0.750 | **-0.633, +0.166, 0.756** | -0.755 to -0.464 |

Expected signs hold: east negative on the descending tracks (T40, T141), positive on the ascending tracks (T4, T76). The built-in nominal geometry
(+-0.589, +0.125, 0.799) is not used. Centre and mean differ by 0.008 in east; the east component varies by about +-0.15 across the swath, which the fit ignores.

## Forward model at +1 on both geometries
`science.ffm_sign.forward`, USGS finite fault `us6000u18k` (strike 295, dip 60, rake -16, 55 x 33.6 km, centre 7.54 N 80.769 W), 1 m of slip, LOS in cm, positive toward the satellite.
The right-of-strike unit vector (east, north) is (0.42, 0.91), i.e. the north-north-east side.

| Geometry (vector used) | NNE side, 20 km from the fault | SSW side, 20 km |
|---|---|---|
| descending, (-0.633, +0.164, 0.756) | +8.25 cm | -7.48 cm |
| ascending, (+0.640, +0.133, 0.757) | -11.20 cm | +7.76 cm |

On the descending geometry the north-north-east side moves toward the satellite and the south-south-west side away, as described for track 141 (Earthquake Insights, second-hand,
unverified); on the ascending geometry the pattern is reversed. **This is a forward-model check of the code chain, not an observation of the sign.**
