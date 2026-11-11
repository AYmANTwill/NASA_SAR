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
# Sign convention: +1 means "positive = motion TOWARD the satellite".
# CHECK on the Panama pair against the published NASA/USGS map; flip to -1 if reversed.
LOS_SIGN = float(os.environ.get("NISAR_LOS_SIGN", "1"))

COHERENCE_MIN = 0.3          # pixels below are masked
POINT_RADIUS_M = 1000        # radius used to measure the signal around a clicked point

# Optional keys
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.environ.get("NISAR_LLM_MODEL", "claude-haiku-5-5")
FIRMS_MAP_KEY = os.environ.get("FIRMS_MAP_KEY", "")
OFFLINE = os.environ.get("NISAR_OFFLINE", "0") == "1"   # skip all internet calls (demo mode)

# Demo places the agent recognises by name (approximate coordinates; refine on the map)
GAZETTEER = {
    "al wahda": (34.64, -5.17), "wahda": (34.64, -5.17), "الوحدة": (34.64, -5.17),
    "ben guerir": (32.27, -7.93), "benguerir": (32.27, -7.93), "ابن جرير": (32.27, -7.93),
    "khouribga": (32.88, -6.90), "خريبكة": (32.88, -6.90),
    "casablanca": (33.57, -7.59), "الدار البيضاء": (33.57, -7.59),
    "chefchaouen": (35.17, -5.27), "panama": (7.59, -80.77), "pitaloza": (7.59, -80.77),
    "caracas": (10.50, -66.90), "venezuela": (10.50, -66.90),
}
