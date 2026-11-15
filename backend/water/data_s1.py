"""Sen1Floods11 hand-labeled Sentinel-1 chips: download (size-checked), Dataset, stats.

Bucket layout verified 2026-11-14 via the public GCS JSON API (gs://sen1floods11):
  v1.1/data/flood_events/HandLabeled/S1Hand/<Event>_<id>_S1Hand.tif     2 bands VV,VH in dB, float32, 512x512
  v1.1/data/flood_events/HandLabeled/LabelHand/<Event>_<id>_LabelHand.tif  -1 no-data, 0 dry, 1 water
  v1.1/splits/flood_handlabeled/flood_{train,valid,test,bolivia}_data.csv
446 chips, S1Hand total 729.5 MB, LabelHand 2.6 MB.

Usage:
  python src/data_s1.py download [--limit 20]
  python src/data_s1.py stats
"""
from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from common import DATA, OUTPUTS, check_budget, dir_size

BUCKET = "sen1floods11"
API = f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o"
PUBLIC = f"https://storage.googleapis.com/{BUCKET}/"
PREFIX = "v1.1/data/flood_events/HandLabeled/"
SPLITS = "v1.1/splits/flood_handlabeled/"
ROOT = DATA / "sen1floods11"

CLIP_DB = (-30.0, 5.0)  # VV/VH dB clip range (refined from stats; see s1_stats.json)
IGNORE = 255


def list_objects(prefix: str) -> list[dict]:
    out, tok = [], None
    while True:
        q = {"prefix": prefix, "fields": "nextPageToken,items(name,size)", "maxResults": 1000}
        if tok:
            q["pageToken"] = tok
        d = json.load(urllib.request.urlopen(API + "?" + urllib.parse.urlencode(q)))
        out += [{"name": i["name"], "size": int(i["size"])} for i in d.get("items", [])]
        tok = d.get("nextPageToken")
        if not tok:
            return out


def _fetch(name: str) -> Path:
    dst = ROOT / name.replace("v1.1/", "")
    if dst.exists():
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    urllib.request.urlretrieve(PUBLIC + urllib.parse.quote(name), tmp)
    tmp.replace(dst)
    return dst


def read_split(split: str) -> list[str]:
    """Return chip ids '<Event>_<id>' of an official split (train/valid/test/bolivia)."""
    f = ROOT / "splits" / "flood_handlabeled" / f"flood_{split}_data.csv"
    df = pd.read_csv(f, header=None)
    return [Path(s).name.replace("_S1Hand.tif", "") for s in df[0]]


def download(limit: int | None = None, batch_mb: int = 400) -> None:
    from tqdm import tqdm

    for o in list_objects(SPLITS):
        _fetch(o["name"])
    ids = read_split("train") + read_split("valid") + read_split("test")
    if limit:  # tiny sample: keep the split mix
        ids = read_split("train")[:limit] + read_split("valid")[: max(2, limit // 4)] + read_split("test")[: max(2, limit // 4)]
    sizes = {o["name"]: o["size"] for o in list_objects(PREFIX + "S1Hand/") + list_objects(PREFIX + "LabelHand/")}
    names = [f"{PREFIX}{k}/{i}_{k}.tif" for i in ids for k in ("S1Hand", "LabelHand")]
    todo = [n for n in names if not (ROOT / n.replace("v1.1/", "")).exists()]
    total = sum(sizes[n] for n in todo)
    print(f"{len(todo)} files to fetch, {total/1e6:.1f} MB; data root now {dir_size()/1e6:.0f} MB")
    batch, acc = [], 0
    for n in todo + [None]:
        if n is not None and acc + sizes[n] <= batch_mb * 1e6:
            batch.append(n)
            acc += sizes[n]
            continue
        if batch:
            check_budget(acc, f"S1 batch of {len(batch)} files")
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(8) as ex:
                list(tqdm(ex.map(_fetch, batch), total=len(batch), desc=f"batch {acc/1e6:.0f} MB", mininterval=30))
        if n is not None:
            batch, acc = [n], sizes[n]
    print(f"done; data root {dir_size()/1e6:.0f} MB")


def available(split: str) -> list[str]:
    return [i for i in read_split(split)
            if (ROOT / f"data/flood_events/HandLabeled/S1Hand/{i}_S1Hand.tif").exists()
            and (ROOT / f"data/flood_events/HandLabeled/LabelHand/{i}_LabelHand.tif").exists()]


def load_chip(chip: str) -> tuple[np.ndarray, np.ndarray]:
    """Return (2,H,W) float32 dB [VV,VH] and (H,W) int16 label (-1/0/1)."""
    import rasterio

    with rasterio.open(ROOT / f"data/flood_events/HandLabeled/S1Hand/{chip}_S1Hand.tif") as s:
        x = s.read().astype(np.float32)
    with rasterio.open(ROOT / f"data/flood_events/HandLabeled/LabelHand/{chip}_LabelHand.tif") as s:
        y = s.read(1).astype(np.int16)
    return x, y


def to_db_if_linear(x: np.ndarray) -> np.ndarray:
    """S1Hand is already dB; guard in case a chip is linear (all finite values > 0 and small)."""
    v = x[np.isfinite(x)]
    if v.size and v.min() >= 0 and np.percentile(v, 99) < 5:
        return 10 * np.log10(np.clip(x, 1e-6, None))
    return x


def load_stats() -> dict:
    return json.loads((OUTPUTS / "s1_stats.json").read_text())


def normalize(x_db: np.ndarray, mean, std) -> tuple[np.ndarray, np.ndarray]:
    """Clip dB, z-score per channel. Returns (normalized, valid mask). NaNs -> 0 and invalid."""
    valid = np.all(np.isfinite(x_db), axis=0)
    x = np.clip(np.nan_to_num(x_db, nan=CLIP_DB[0]), *CLIP_DB)
    x = (x - np.asarray(mean, np.float32)[:, None, None]) / np.asarray(std, np.float32)[:, None, None]
    x[:, ~valid] = 0
    return x.astype(np.float32), valid


class S1Dataset:
    """torch Dataset of (x[2,H,W] normalized, y[H,W] uint8 with 255 = ignore)."""

    def __init__(self, split: str, stats: dict | None = None, augment: bool = False,
                 crop: int | None = None, limit: int | None = None):
        self.ids = available(split)[:limit] if limit else available(split)
        st = stats or load_stats()
        self.mean, self.std = st["mean_db"], st["std_db"]
        self.augment, self.crop = augment, crop

    def __len__(self):
        return len(self.ids)

    def __getitem__(self, i):
        import torch

        x, y = load_chip(self.ids[i])
        x, valid = normalize(to_db_if_linear(x), self.mean, self.std)
        t = np.where((y == -1) | ~valid, IGNORE, y).astype(np.uint8)
        if self.crop:
            h, w = t.shape
            r, c = np.random.randint(0, h - self.crop + 1), np.random.randint(0, w - self.crop + 1)
            x, t = x[:, r:r + self.crop, c:c + self.crop], t[r:r + self.crop, c:c + self.crop]
        if self.augment:
            if np.random.rand() < 0.5:
                x, t = x[:, :, ::-1], t[:, ::-1]
            if np.random.rand() < 0.5:
                x, t = x[:, ::-1], t[::-1]
            k = np.random.randint(4)
            x, t = np.rot90(x, k, (1, 2)), np.rot90(t, k)
        return torch.from_numpy(x.copy()), torch.from_numpy(t.copy())


def compute_stats() -> dict:
    ids = available("train")
    s, s2, n = np.zeros(2), np.zeros(2), 0
    lab = {-1: 0, 0: 0, 1: 0}
    lo, hi = [], []
    for c in ids:
        x, y = load_chip(c)
        x = to_db_if_linear(x)
        v = np.all(np.isfinite(x), 0) & (y != -1)
        xv = x[:, v].astype(np.float64)
        lo.append(np.percentile(xv, 0.5, axis=1)) if xv.size else None
        hi.append(np.percentile(xv, 99.5, axis=1)) if xv.size else None
        xv = np.clip(xv, *CLIP_DB)
        s += xv.sum(1)
        s2 += (xv**2).sum(1)
        n += xv.shape[1]
        for k in lab:
            lab[k] += int((y == k).sum())
    mean = s / n
    std = np.sqrt(s2 / n - mean**2)
    labeled = lab[0] + lab[1]
    stats = {
        "channels": ["VV_dB", "VH_dB"],
        "split": "train",
        "n_chips": {sp: len(available(sp)) for sp in ("train", "valid", "test")},
        "clip_db": list(CLIP_DB),
        "mean_db": mean.round(4).tolist(),
        "std_db": std.round(4).tolist(),
        "p0.5_db_median_over_chips": np.median(lo, 0).round(2).tolist(),
        "p99.5_db_median_over_chips": np.median(hi, 0).round(2).tolist(),
        "label_pixels": {"nodata(-1)": lab[-1], "dry(0)": lab[0], "water(1)": lab[1]},
        "water_fraction_of_labeled": round(lab[1] / max(labeled, 1), 4),
    }
    (OUTPUTS / "s1_stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["download", "stats"])
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    download(a.limit) if a.cmd == "download" else compute_stats()
