"""Synthetic data in exactly the layout written by download_all.py, with known signals,
to test every feature without real files.  Usage: python tests/make_synthetic.py <data_dir>"""
import sys
from datetime import date, timedelta
from pathlib import Path

import h5py
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import WAVELENGTH_M  # noqa: E402
from recipes.decompose import _nominal  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "synthetic_data")
N, PX = 600, 80.0
rng = np.random.default_rng(42)


def grid(lat, lon, epsg):
    x, y = Transformer.from_crs(4326, epsg, always_xy=True).transform(lon, lat)
    x0, y0 = x - N / 2 * PX, y + N / 2 * PX
    return from_origin(x0, y0, PX, PX), x0, y0


def bump(cx_off_km=0, cy_off_km=0, r_km=3.0):
    yy, xx = np.mgrid[:N, :N]
    d2 = ((xx - N / 2 - cx_off_km * 1000 / PX) ** 2 + (yy - N / 2 + cy_off_km * 1000 / PX) ** 2) * PX ** 2
    return np.exp(-d2 / (2 * (r_km * 1000) ** 2))


def tif(path, arr, transform, epsg):
    with rasterio.open(path, "w", driver="GTiff", width=N, height=N, count=1, dtype=arr.dtype,
                       crs=f"EPSG:{epsg}", transform=transform, compress="LZW") as d:
        d.write(arr, 1)


def stamp(d: date, hhmmss="053852"):
    return d.strftime("%Y%m%d") + "T" + hhmmss


def gunw(track, direction, frame, d1, d2, los_m, coh, lat, lon, epsg, crid="P05023", extra_phase=None, extra_npz=None):
    a = "A" if direction == "ascending" else "D"
    hh = "053852" if a == "A" else "235308"      # descending passes are in the evening
    name = (f"NISAR_L2_PR_GUNW_030_{track:03d}_{a}_{frame:03d}_031_4000_SH_{stamp(d1, hh)}_{stamp(d1,'235330')}_"
            f"{stamp(d2, hh)}_{stamp(d2,'235330')}_{crid}_N_F_J_001")
    f = OUT / "GUNW" / name
    f.mkdir(parents=True, exist_ok=True)
    t, *_ = grid(lat, lon, epsg)
    phase = (los_m / (-WAVELENGTH_M / (4 * np.pi))).astype("float32")
    phase += rng.normal(0, 0.15, phase.shape).astype("float32")          # ~3 mm noise
    if extra_phase is not None:                                          # e.g. a tropospheric ramp (radians)
        phase += extra_phase.astype("float32")
    tif(f / "unwrappedInterferogram_HH_unwrappedPhase.tif", phase, t, epsg)
    tif(f / "unwrappedInterferogram_HH_coherenceMagnitude.tif", coh.astype("float32"), t, epsg)
    tif(f / "unwrappedInterferogram_HH_connectedComponents.tif", np.ones((N, N), "uint16"), t, epsg)
    v = _nominal(direction)
    np.savez_compressed(f / "radar_geometry.npz", science__LSAR__GUNW__metadata__radarGrid__losUnitVectorX=np.full((3, 5, 5), v[0]),
                        science__LSAR__GUNW__metadata__radarGrid__losUnitVectorY=np.full((3, 5, 5), v[1]), **(extra_npz or {}))
    (f / "_DONE").write_text("{}")


AL_WAHDA = (34.598, -5.198)      # the dam (OSM dam polygon); the old gazetteer point (34.64, -5.17) was ~5 km away
ASNI = (31.250, -7.983)          # Al Haouz, flash flood of 2026-10-10
KHOURIBGA = (32.88, -6.91)       # far from Asni: geometries that test the usability rules of the surface-change recipe
STORM = 0.7                      # coherence lost at the centre of the storm patch


def stack(track, direction, frame, start, n, lat, lon, epsg, up_mm_yr, east_mm_yr=0.0, r_km=2.0, crid="P05023"):
    v = _nominal(direction)
    for k in range(n):
        d1 = start + timedelta(days=12 * k)
        for span in (12, 24):
            d2 = d1 + timedelta(days=span)
            if (d2 - start).days > 12 * n:
                continue
            yrs = span / 365.25
            los = (v[2] * up_mm_yr + v[0] * east_mm_yr) / 1000 * yrs * bump(r_km=r_km)
            gunw(track, direction, frame, d1, d2, los, np.clip(rng.normal(0.75, 0.08, (N, N)), 0, 1), lat, lon, epsg, crid)


def main():
    # --- Panama: coseismic pairs (asc + desc) with ~25 cm uplift + 15 cm east; one pre-event pair
    lat, lon, epsg = 7.59, -80.77, 32617
    for track, direction, frame, d1, d2 in [(141, "descending", 84, date(2026, 9, 27), date(2026, 10, 9)),
                                           (4, "ascending", 6, date(2026, 9, 30), date(2026, 10, 12))]:
        v = _nominal(direction)
        los = (v[2] * 0.25 + v[0] * 0.15) * bump(r_km=6)
        coh = np.clip(rng.normal(0.7, 0.05, (N, N)) - 0.5 * bump(1, 1, 1.0), 0, 1)
        gunw(track, direction, frame, d1, d2, los, coh, lat, lon, epsg)
        gunw(track, direction, frame, d1 - timedelta(days=12), d1, np.zeros((N, N)),
             np.clip(rng.normal(0.7, 0.05, (N, N)), 0, 1), lat, lon, epsg)
    # --- Al Wahda: 9-pass stacks, -20 mm/yr vertical on the dam
    stack(116, "ascending", 19, date(2026, 6, 22), 9, *AL_WAHDA, 32630, up_mm_yr=-20)
    stack(95, "descending", 71, date(2026, 6, 20), 9, *AL_WAHDA, 32630, up_mm_yr=-20)
    # --- three VALIDATED-CRID pairs (P05036) after the provisional chain: a separate series, never mixed
    stack(116, "ascending", 19, date(2026, 10, 22), 3, *AL_WAHDA, 32630, up_mm_yr=-20, crid="P05036")
    # --- Ben Guerir mine: 4-pass stack, -60 mm/yr
    stack(44, "ascending", 18, date(2026, 6, 17), 4, 32.27, -7.93, 32629, up_mm_yr=-60, r_km=1.5)

    # --- Al Haouz flash flood (10 Oct 2026, whole day): last pre-event pair + pair across the storm, on the
    #     real frames 44/17 (ascending) and 23/73 (descending); a coherence loss around Asni in the storm pair
    for track, direction, frame, pre, co in [
            (44, "ascending", 17, (date(2026, 9, 21), date(2026, 10, 3)), (date(2026, 10, 3), date(2026, 10, 15))),
            (23, "descending", 73, (date(2026, 9, 19), date(2026, 10, 1)), (date(2026, 10, 1), date(2026, 10, 13))),
            # like the real frame 95/73 at Asni: barely coherent there -> unusable, must not vote
            (95, "descending", 73, (date(2026, 9, 24), date(2026, 10, 6)), (date(2026, 10, 6), date(2026, 10, 18)))]:
        for k, (d1, d2) in enumerate([pre, co]):
            coh = np.clip(rng.normal(0.75, 0.05, (N, N)) - (STORM * bump(0, 0, 2.0) if k == 1 else 0), 0, 1)
            if track == 95:
                coh = np.full((N, N), 0.2)
            gunw(track, direction, frame, d1, d2, np.zeros((N, N)), coh, *ASNI, 32629)

    # --- SME2 over the Gharb, 6 passes
    t, x0, y0 = grid(34.5, -6.0, 32630)
    for k in range(6):
        d = date(2026, 7, 16) + timedelta(days=24 * k)
        name = f"NISAR_L3_PR_SME2_033_116_A_019_4005_DHDH_A_{stamp(d)}_{stamp(d,'053933')}_P05023_N_F_J_001"
        f = OUT / "SME2" / name
        f.mkdir(parents=True, exist_ok=True)
        with h5py.File(f / f"{name}.h5", "w") as h:
            g = h.create_group("science/LSAR/SME2/grids")
            g["xCoordinates"] = x0 + PX * (np.arange(N) + 0.5)
            g["yCoordinates"] = y0 - PX * (np.arange(N) + 0.5)
            pr = g.create_dataset("projection", data=np.uint32(32630))
            pr.attrs["epsg_code"] = 32630
            sm = g.create_dataset("soilMoisture", data=np.clip(0.15 + 0.03 * k + rng.normal(0, 0.01, (N, N)), 0, 0.6).astype("float32"))
            sm.attrs["_FillValue"] = np.float32(-9999.0)
            g["soilMoistureUncertainty"] = np.full((N, N), 0.04, "float32")         # like real files
            c = g.create_group("algorithmCandidates/DSG")
            c["soilMoisture"] = np.full((N, N), 0.9, "float32")
        (f / "_DONE").write_text("{}")

    # --- GCOV before/after over the Gharb: flood patch (HH drop) and vegetation loss (HV drop)
    for k, d in enumerate([date(2026, 10, 1), date(2026, 10, 13)]):
        name = f"NISAR_L2_PR_GCOV_030_015_A_019_4005_DHDH_A_{stamp(d)}_{stamp(d,'053933')}_P05023_N_F_J_001"
        f = OUT / "GCOV" / name
        f.mkdir(parents=True, exist_ok=True)
        hh = 10 ** (rng.normal(-9, 0.8, (N, N)) / 10)
        hv = 10 ** (rng.normal(-15, 0.8, (N, N)) / 10)
        if k == 1:
            hh = np.where(bump(-3, 0, 1.5) > 0.5, 10 ** (-22 / 10), hh)        # open water
            hv = np.where(bump(4, 2, 1.0) > 0.5, hv / 10 ** 0.6, hv)          # -6 dB volume loss
        tif(f / "grids_frequencyA_HHHH.tif", hh.astype("float32"), t, 32630)
        tif(f / "grids_frequencyA_HVHV.tif", hv.astype("float32"), t, 32630)
        (f / "_DONE").write_text("{}")
    # --- baseline pairs for the surface-change recipe: every geometry needs the pair(s) before its "before" pair
    for track, direction, frame, d1, d2 in [(141, "descending", 84, date(2026, 9, 27), date(2026, 10, 9)),
                                           (4, "ascending", 6, date(2026, 9, 30), date(2026, 10, 12))]:
        gunw(track, direction, frame, d1 - timedelta(days=24), d1 - timedelta(days=12), np.zeros((N, N)),
             np.clip(rng.normal(0.7, 0.05, (N, N)), 0, 1), 7.59, -80.77, 32617)
    for track, direction, frame, before_pair in [(44, "ascending", 17, date(2026, 9, 21)),
                                                 (23, "descending", 73, date(2026, 9, 19))]:
        for k in range(1, 5):                       # four earlier 12-day pairs on the same chain
            d1 = before_pair - timedelta(days=12 * k)
            gunw(track, direction, frame, d1, d1 + timedelta(days=12), np.zeros((N, N)),
                 np.clip(rng.normal(0.75, 0.05, (N, N)), 0, 1), *ASNI, 32629)

    # --- usability rules, around Khouribga (never near the other test points)
    pairs = [(date(2026, 8, 4), date(2026, 8, 16)), (date(2026, 8, 16), date(2026, 8, 28)),
             (date(2026, 8, 28), date(2026, 9, 9)), (date(2026, 9, 9), date(2026, 9, 21)),
             (date(2026, 9, 21), date(2026, 10, 3)), (date(2026, 10, 3), date(2026, 10, 15))]   # last = across the storm

    def chain(track, direction, frame, first=0, lat_c=None, level=0.75, before_level=None, patch=None, loss=True,
              bad_baseline=False):
        lat, lon = KHOURIBGA
        for k, (d1, d2) in enumerate(pairs):
            if k < first:
                continue
            m = before_level if (before_level is not None and k == 4) else level
            if bad_baseline and k == 3:                  # the pair just before the before pair: nowhere coherent
                m = 0.2
            coh = np.clip(rng.normal(m, 0.05, (N, N)), 0, 1)
            if k == 5 and loss:
                coh = np.clip(coh - (patch if patch is not None else STORM * bump(0, 0, 2.0)), 0, 1)
            gunw(track, direction, frame, d1, d2, np.zeros((N, N)), coh, lat_c if lat_c is not None else lat, lon, 32629)

    chain(60, "ascending", 31)                                   # good: usable, normal before pair
    chain(61, "descending", 32, before_level=0.55)               # usable, but the before pair is degraded
    chain(62, "ascending", 33, first=4)                          # before + event only: no baseline pair
    chain(63, "descending", 34, lat_c=KHOURIBGA[0] - 0.20)       # the point is 1.8 km from the array edge: not covered
    chain(64, "ascending", 35, level=0.25)                       # never coherent: unusable
    chain(65, "descending", 36, patch=0.9 * bump(4.0, 4.0, 0.5))  # loss only in the corner of the 10x10 km square
    chain(66, "ascending", 37, patch=0.43 * bump(0, 0, 2.0))      # excess ~0.13: the borderline band
    chain(67, "descending", 38, patch=0.10 * bump(0, 0, 2.0))     # excess ~0.03: nothing clear
    chain(68, "ascending", 39, bad_baseline=True)                 # the baseline pair cannot be measured
    corrections_site()
    gps_site()
    print("synthetic data written to", OUT.resolve())


# --- corrections: a tropospheric ramp (+ a small tide ramp) in the phase, and the matching radarGrid cubes ----------
TROPO_SITE = (30.40, -9.55)          # far from every other test point
TROPO_RAD = 2.0                      # tropospheric ramp: -2 .. +2 rad across the frame (about +-3.8 cm)
TIDE_RAD = 0.5                       # solid-earth tide ramp: -0.5 .. +0.5 rad north-south (about +-1 cm)


def correction_screens(epsg=32629):
    """(tropo ramp, tide ramp) on the GUNW grid at height 0, and the npz cubes that hold them."""
    _, x0, y0 = grid(*TROPO_SITE, epsg)
    xs = x0 - 4000 + 8000 * np.arange(8)                 # coarse radarGrid axes, wider than the frame
    ys = y0 + 4000 - 8000 * np.arange(8)                 # descending, like the real files
    hs = np.array([-500.0, 0.0, 3000.0, 9000.0])
    w = N * PX
    tx = lambda x: TROPO_RAD * (2 * (x - x0) / w - 1)    # noqa: E731  linear in x, exact under bilinear interpolation
    ty = lambda y: TIDE_RAD * (2 * (y0 - y) / w - 1)     # noqa: E731
    X, Y = np.meshgrid(xs, ys)
    fade = np.clip(1 - hs / 9000.0, 0, None)[:, None, None]          # the delay shrinks with height
    hydro = 0.7 * tx(X)[None] * fade
    wet = 0.3 * tx(X)[None] * fade
    tide = np.broadcast_to(ty(Y)[None], (hs.size, *X.shape)).copy()
    cols = x0 + PX * (np.arange(N) + 0.5)
    rows = y0 - PX * (np.arange(N) + 0.5)
    on_grid = (tx(cols)[None, :] + 0 * rows[:, None], ty(rows)[:, None] + 0 * cols[None, :])
    long_ = "science__LSAR__GUNW__metadata__radarGrid__"
    npz = {long_ + "hydrostaticTroposphericPhaseScreen": hydro, long_ + "wetTroposphericPhaseScreen": wet,
           "slantRangeSolidEarthTidesPhase": tide, "heightAboveEllipsoid": hs, "xCoordinates": xs, "yCoordinates": ys,
           "projection": np.uint32(epsg)}
    return on_grid, npz


def corrections_site():
    (tropo, tide), npz = correction_screens()
    for k in range(2):
        d1 = date(2026, 8, 1) + timedelta(days=12 * k)
        gunw(172, "descending", 52, d1, d1 + timedelta(days=12), np.zeros((N, N)),
             np.clip(rng.normal(0.8, 0.05, (N, N)), 0, 1), *TROPO_SITE, 32629, extra_phase=tropo + tide, extra_npz=npz)


# --- GPS validation: a NISAR stack over the RABT station and an NGL-format sample of its daily positions -----------
RABT = (33.998103660, -6.854289218)  # NGL DataHoldings.txt / RABT.tenv3 coordinates
GPS_START = date(2026, 7, 4)


def gps_up_m(d: date) -> float:
    """Vertical motion of the synthetic station: a seasonal swing, so the pair-to-pair changes vary in sign."""
    t = (d - GPS_START).days
    return 0.015 * np.sin(2 * np.pi * t / 60.0)


def gps_site():
    v = _nominal("ascending")
    for k in range(6):
        d1 = GPS_START + timedelta(days=12 * k)
        d2 = d1 + timedelta(days=12)
        los = v[2] * (gps_up_m(d2) - gps_up_m(d1)) * bump(r_km=5.0)
        gunw(170, "ascending", 50, d1, d2, los, np.clip(rng.normal(0.8, 0.05, (N, N)), 0, 1), *RABT, 32629)
    g = OUT / "GPS_sample"
    g.mkdir(parents=True, exist_ok=True)
    hdr = ("site YYMMMDD yyyy.yyyy __MJD week d reflon _e0(m) __east(m) ____n0(m) _north(m) u0(m) ____up(m) _ant(m) "
           "sig_e(m) sig_n(m) sig_u(m) __corr_en __corr_eu __corr_nu _latitude(deg) _longitude(deg) __height(m)")
    lines, d = [hdr], date(2026, 6, 1)
    noise = np.random.default_rng(7)
    while d <= date(2026, 10, 31):
        mjd = (d - date(1858, 11, 17)).days
        up = 0.0999 + gps_up_m(d) + noise.normal(0, 0.001)
        lines.append(f"RABT {d.strftime('%y%b%d').upper()} {d.year + (d.timetuple().tm_yday - 0.5) / 365.25:.4f} {mjd} "
                     f"{(mjd - 44244) // 7} {(mjd - 44244) % 7}   -6.9   4222 {0.9919 + noise.normal(0, 0.0007):.6f}   3763451 "
                     f"{0.0079 + noise.normal(0, 0.0007):.6f}    90 {up:.6f}  0.0800 0.000800 0.000900 0.003200  0.08 0.04 -0.07  "
                     f"{RABT[0]:.10f}   {RABT[1]:.10f}    90.09")
        d += timedelta(days=1)
    (g / "RABT.tenv3").write_text("\n".join(lines) + "\n")
    (g / "DataHoldings.txt").write_text(
        "Sta  Lat(deg)   Long(deg) Hgt(m)  X(m)           Y(m)         Z(m)          Dtbeg      Dtend      Dtmod      NumSol StaOrigName\n"
        f"RABT  {RABT[0]:.4f}   {RABT[1] % 360:.4f}   90.104  5255617.6865  -631745.6791  3546322.5599 2000-05-17 2026-10-31 2026-11-01   9000\n"
        "OLDX  33.9990   353.1400   90.000  5255617.0000  -631745.0000  3546322.0000 2000-05-17 2009-08-12 2025-09-29   3000\n"
        "FARX  10.0000    10.0000   10.000  6000000.0000  1000000.0000  1000000.0000 2010-01-01 2026-10-31 2026-11-01   5000\n")


if __name__ == "__main__":
    main()
