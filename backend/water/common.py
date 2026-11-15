"""Shared paths, disk-space guards and metrics."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
# Standalone research repo keeps modules in src/; the team repo copies the same
# modules directly into backend/water/.  Keep outputs beside the water package in
# either layout so integration never writes into the backend's general outputs.
REPO = _HERE.parent if _HERE.name == "src" else _HERE
OUTPUTS = REPO / "outputs"  # small files only (csv, json, png)
DATA = Path(os.environ.get("NASA_DATA", Path.home() / "nasa_data"))  # data root, outside the repo
MODELS = DATA / "models"
BIG_OUT = DATA / "outputs"  # GeoTIFFs etc.

MAX_DOWNLOAD_BYTES = 500 * 1024**2
MAX_DATA_BYTES = 14 * 1024**3  # data root budget (raised 2026-11-14 from 2 GB)
MIN_FREE_BYTES = 8 * 1024**3   # always keep at least 8 GB free on the disk

for _p in (OUTPUTS, DATA, MODELS, BIG_OUT):
    _p.mkdir(parents=True, exist_ok=True)

# Earthdata token lives OUTSIDE the repo (data root); loaded silently, never printed or logged.
_TOKEN_FILE = DATA / ".earthdata_token"
_TOKEN_ENV = "EARTH" + "DATA_TOKEN"
if not os.environ.get(_TOKEN_ENV) and _TOKEN_FILE.exists():
    os.environ[_TOKEN_ENV] = _TOKEN_FILE.read_text().strip()

RESERVOIRS = {
    # Approximate centres only; real AOI bbox is derived in nisar_search.py.
    "Al_Massira": (32.48, -7.63),
    "Bin_El_Ouidane": (32.10, -6.45),
    "Al_Wahda": (34.60, -5.50),
}


def rel(p) -> str:
    """Store data paths portably: '$NASA_DATA/<relative posix path>' when under the data root."""
    p = Path(p)
    try:
        return "$NASA_DATA/" + p.resolve().relative_to(DATA.resolve()).as_posix()
    except ValueError:
        return str(p)


def dpath(p) -> Path:
    """Resolve a stored path ('$NASA_DATA/...' or legacy absolute) to a local Path."""
    s = str(p).replace("\\", "/")
    if s.startswith("$NASA_DATA/"):
        return DATA / s[len("$NASA_DATA/"):]
    return Path(str(p))


def retry(fn, *args, tries: int = 5, base_wait: float = 10.0, what: str = "", **kw):
    """Call fn with retries + linear backoff. The campus Wi-Fi drops DNS lookups intermittently."""
    import time

    for i in range(tries):
        try:
            return fn(*args, **kw)
        except Exception as e:  # network errors come from requests, aiohttp, fsspec, h5py, GDAL...
            if i == tries - 1:
                raise
            wait = base_wait * (i + 1)
            print(f"   [retry {i+1}/{tries-1}] {what or getattr(fn, '__name__', 'call')}: "
                  f"{type(e).__name__}: {str(e)[:120]} -> waiting {wait:.0f}s", flush=True)
            time.sleep(wait)


def free_bytes(path: Path = DATA) -> int:
    return shutil.disk_usage(path).free


def dir_size(path: Path = DATA) -> int:
    return sum(f.stat().st_size for f in Path(path).rglob("*") if f.is_file())


def check_budget(n_bytes: int, what: str = "") -> None:
    """Raise before a download that would break the disk limits."""
    if n_bytes > MAX_DOWNLOAD_BYTES:
        raise RuntimeError(f"{what}: {n_bytes/1e6:.0f} MB > 500 MB per-download limit")
    used = dir_size(DATA)
    if used + n_bytes > MAX_DATA_BYTES:
        raise RuntimeError(f"{what}: data root would reach {(used+n_bytes)/1e9:.2f} GB > {MAX_DATA_BYTES/1e9:.0f} GB limit")
    if free_bytes() - n_bytes < MIN_FREE_BYTES:
        raise RuntimeError(f"{what}: would leave less than {MIN_FREE_BYTES/1e9:.0f} GB free on disk")


def confusion(pred: np.ndarray, ref: np.ndarray, valid: np.ndarray) -> tuple[int, int, int]:
    p, r = pred[valid].astype(bool), ref[valid].astype(bool)
    return int((p & r).sum()), int((p & ~r).sum()), int((~p & r).sum())


def scores(tp: int, fp: int, fn: int) -> dict:
    return {
        "iou": tp / max(tp + fp + fn, 1),
        "precision": tp / max(tp + fp, 1),
        "recall": tp / max(tp + fn, 1),
    }


def append_results(rows: list[dict]) -> None:
    import pandas as pd

    f = OUTPUTS / "results.csv"
    new = pd.DataFrame(rows)
    if f.exists():
        old = pd.read_csv(f)
        key = ["domain", "method"]
        old = old[~old.set_index(key).index.isin(new.set_index(key).index)]
        new = pd.concat([old, new], ignore_index=True)
    new.to_csv(f, index=False)


def gpu_start(run: str = ""):
    """Log the compute device at the start of a run; peak GPU memory is printed at exit."""
    import atexit

    import torch

    ok = torch.cuda.is_available()
    dev = torch.device("cuda" if ok else "cpu")
    name = torch.cuda.get_device_name(0) if ok else "CPU"
    print(f"[gpu] {Path(run).name or 'run'}: torch.cuda.is_available()={ok}, device={dev}, name={name}", flush=True)
    if ok:
        torch.cuda.reset_peak_memory_stats()

        def _peak():
            print(f"[gpu] {Path(run).name or 'run'}: peak GPU memory {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB", flush=True)
        atexit.register(_peak)
    return dev


def https_fs():
    """Authenticated fsspec HTTPS filesystem for Earthdata Cloud (NISAR/ASF, PO.DAAC, LP DAAC).

    Uses earthaccess when it can log in with the token (earthaccess >= 0.15); otherwise (e.g. Python 3.10, where
    earthaccess stops at 0.14 without token login) builds the same kind of session directly: an aiohttp-backed
    fsspec HTTPS filesystem sending the Earthdata token as a bearer header. The token is never printed.
    """
    try:
        import earthaccess

        auth = earthaccess.login(strategy="environment")
        if auth and auth.authenticated:
            return earthaccess.get_fsspec_https_session()
    except Exception:
        pass
    import fsspec

    tok = os.environ.get("EARTHDATA_TOKEN")
    if not tok:
        raise RuntimeError("Earthdata token not found (data root token file or EARTHDATA_TOKEN)")
    return fsspec.filesystem("https", client_kwargs={"headers": {"Authorization": f"Bearer {tok}"}, "trust_env": False})
