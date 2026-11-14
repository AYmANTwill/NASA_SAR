"""Settings. Everything can be overridden with environment variables."""
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Folder created by download_all.py (contains GUNW/, SME2/, manifest.csv)
DATA_DIR = Path(os.environ.get("NISAR_DATA", HERE.parent / "data"))
# Where computed results (PNG layers, cached answers) are written
CACHE_DIR = Path(os.environ.get("NISAR_CACHE", HERE / "cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# NISAR L-band wavelength (m). Centre frequency ~1.257 GHz.
WAVELENGTH_M = 0.2384
# Sign convention: +1 means "positive = motion TOWARD the satellite". NISAR GUNW unwrapped phase is positive = motion
# AWAY from the sensor (ARIA-tools README, MintPy prep_nisar), so displacement = -lambda/(4 pi) * phase with +1 is the
# documented convention. NISAR_LOS_SIGN_VERIFIED below stays the switch for saying it was checked on our data.
LOS_SIGN = float(os.environ.get("NISAR_LOS_SIGN", "1"))
SIGN_BASIS = ("documented convention (ARIA-tools, MintPy prep_nisar): GUNW unwrapped phase positive = motion away "
              "from the sensor; displacement = -lambda/(4 pi) x phase, positive = toward the satellite"
              if LOS_SIGN > 0 else
              "NISAR_LOS_SIGN=-1 set by hand: OPPOSITE to the documented convention (ARIA-tools, MintPy prep_nisar)")
# STATUS H4: the sign has not been checked on real data. While False, every signed line-of-sight answer says "sign
# unverified", has confidence low and no alert. Set NISAR_LOS_SIGN_VERIFIED=1 only after the Panama check.
LOS_SIGN_VERIFIED = os.environ.get("NISAR_LOS_SIGN_VERIFIED", "0") == "1"
FRINGE_CM = WAVELENGTH_M / 2 * 100      # 11.92 cm of line-of-sight change per fringe (one 2*pi of phase)

COHERENCE_MIN = 0.3          # pixels below are masked
POINT_RADIUS_M = 1000        # radius used to measure the signal around a clicked point
# A rate (mm/yr) is only reported for a record at least this long (12 months): a few months of a
# 12-day chain cannot separate a trend from atmospheric noise and seasonal effects.
MIN_RATE_DAYS = 365

# Acquisition gaps (docs/claude/morocco_inventory.md): a pair that starts before and ends after one is a "bridge" pair.
DATA_GAPS = [("20260727", "20260810")]

# Automatic discoveries are OFF: the zones were not physical (8 to 15 fringes in one 12-day pair). The code is kept.
DISCOVERIES_ENABLED = os.environ.get("NISAR_DISCOVERIES_ENABLED", "0") == "1"
# NISAR_DISCOVERIES_MODE=consistent turns on the SAFE mode only: a zone must appear in >= 3 independent pairs of one
# geometry, with the same sign, not concentrated in one pair, above 3 sigma after smoothing (discoveries.py).
# Unset (default): discoveries stay off unless NISAR_DISCOVERIES_ENABLED=1 (the old single-pair / velocity mode).
DISCOVERIES_MODE = os.environ.get("NISAR_DISCOVERIES_MODE", "").strip().lower()
DISCOVERIES_OFF_REASON = ("Automatic discoveries are disabled: the candidate zones were not physical (several fringes in a "
                          "single 12-day pair) and are not validated. Set NISAR_DISCOVERIES_MODE=consistent for the safe mode "
                          "(>= 3 independent pairs, same sign), or NISAR_DISCOVERIES_ENABLED=1 to run the old mode anyway.")

# SME2 soil-moisture retrieval uncertainty (m3/m3), used when the product has no uncertainty layer (median in real files).
SM_UNCERTAINTY = 0.028

# Product maturity from the CRID in the file name (ASF NISAR availability page, 2026-11-12).
# Never mix CRIDs in one time series. Add a line when a new CRID appears; unknown CRIDs stay "unknown".
CRID_MATURITY = {"P05023": "provisional", "P05036": "validated"}

# Optional keys
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.environ.get("NISAR_LLM_MODEL", "claude-haiku-5-5")
FIRMS_MAP_KEY = os.environ.get("FIRMS_MAP_KEY", "")
OFFLINE = os.environ.get("NISAR_OFFLINE", "0") == "1"   # skip all internet calls (demo mode)

# Places the agent recognises by name, with French / English / Arabic aliases. Coordinates and sources:
# docs/claude/morocco_inventory.md §1 (OSM-checked on 2026-11-12). Matching is by whole word, longest alias first.
# A Moroccan map view for the interface (centre lat, lon, zoom).
DEFAULT_MAP_VIEW = {"lat": 32.0, "lon": -6.5, "zoom": 6}

_PLACES = {
    # Al Haouz flash flood area (frames 44/17 A, 23/73 D, 95/73 D)
    "imlil": ((31.136, -7.919), ["imlil", "إمليل"]),
    "asni": ((31.250, -7.983), ["asni", "أسني", "al haouz", "haouz", "الحوز"]),   # Asni stands for the Haouz region
    "moulay brahim": ((31.286, -7.966), ["moulay brahim", "moulay_brahim", "مولاي إبراهيم"]),
    # Al Wahda dam: OSM dam polygon (way 26301395), NOT the old (34.64, -5.17) which is ~5 km away
    "al wahda": ((34.598, -5.198), ["al wahda", "al wahda dam", "barrage al wahda", "wahda", "al ouahda",
                                    "سد الوحدة", "الوحدة"]),
    "gharb": ((34.50, -6.00), ["gharb", "plaine du gharb", "الغرب"]),
    # proposed farmland point (OSM way 257797663); the plan's (35.00, -5.90) is inside the town. Confirm on a basemap.
    "ksar el kebir": ((35.0105, -5.9031), ["ksar el kebir", "ksar el kébir", "ksar el-kebir", "ksar-el-kebir",
                                           "loukkos", "القصر الكبير"]),
    "ben guerir mine": ((32.25825, -7.82355), ["ben guerir mine", "mine de ben guerir", "mine de benguerir",
                                               "mine benguerir", "منجم ابن جرير"]),
    "ben guerir": ((32.27, -7.93), ["ben guerir", "benguerir", "ابن جرير"]),
    "khouribga": ((32.88, -6.90), ["khouribga", "خريبكة"]),
    "casablanca": ((33.57, -7.59), ["casablanca", "الدار البيضاء"]),
    "chefchaouen": ((35.17, -5.27), ["chefchaouen", "شفشاون"]),
    # Panama: global VALIDATION event (events.VALIDATION_EVENTS), outside the Morocco scope; Venezuela: test fixture
    "panama": ((7.59, -80.77), ["panama", "pitaloza"]),
    "caracas": ((10.50, -66.90), ["caracas", "venezuela"]),
}
GAZETTEER = {alias: coords for coords, aliases in _PLACES.values() for alias in aliases}
