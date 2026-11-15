"""Step 7: cheap domain adaptation for NISAR.

- per-scene standardization: z-score NISAR inputs with each scene's own per-channel mean/std
  (instead of the Sentinel-1 training stats)
- AdaBN: recompute every BatchNorm's running mean/var on unlabeled NISAR tiles (cumulative
  average, momentum=None), no gradients, then back to eval. Two variants: inputs normalized with
  S1 stats, or with per-scene stats.

Usage: python src/adabn.py
"""
from __future__ import annotations

import copy
import os

import numpy as np
import pandas as pd
import rasterio
import torch
import torch.nn as nn

from common import MODELS, OUTPUTS
from data_s1 import CLIP_DB, load_stats, normalize

TILE = 512
STRIDE = 384


def scene_stats(x_db: np.ndarray) -> tuple[list[float], list[float]]:
    v = np.all(np.isfinite(x_db), 0)
    xc = np.clip(x_db[:, v], *CLIP_DB)
    return xc.mean(1).tolist(), xc.std(1).tolist()


def load_scene(path) -> tuple[np.ndarray, dict]:
    from common import dpath

    path = dpath(path)
    with rasterio.open(path) as s:
        return s.read().astype(np.float32), s.profile


def norm_scene(x_db: np.ndarray, mode: str, s1: dict) -> tuple[np.ndarray, np.ndarray]:
    """mode 's1' = S1 training stats, 'scene' = the scene's own stats. HH->VV slot, HV->VH slot."""
    if mode == "scene":
        mean, std = scene_stats(x_db)
    else:
        mean, std = s1["mean_db"], s1["std_db"]
    return normalize(x_db, mean, std)


def tiles(h: int, w: int, size: int = TILE, stride: int = STRIDE):
    ys = list(range(0, max(h - size, 0) + 1, stride)) or [0]
    xs = list(range(0, max(w - size, 0) + 1, stride)) or [0]
    if ys[-1] + size < h:
        ys.append(h - size)
    if xs[-1] + size < w:
        xs.append(w - size)
    return [(y, x) for y in ys for x in xs]


def pad_to(x: np.ndarray, size: int) -> np.ndarray:
    _, h, w = x.shape
    return np.pad(x, ((0, 0), (0, max(0, size - h)), (0, max(0, size - w))))


AMP = os.environ.get("WATER_AMP", "0") == "1"   # fp32 by default: AMP changed masks (gpu_equivalence.json) for ~6% speed
BATCH = int(os.environ.get("WATER_TILE_BATCH", "32"))  # 512x512 tiles per forward pass (peak < 1 GiB at 8)


@torch.no_grad()
def predict_scene(model, xn: np.ndarray, device, mc: int = 0, batch: int | None = None,
                  amp: bool | None = None) -> tuple[np.ndarray, np.ndarray | None]:
    """Sliding-window probability map (averaged on overlaps). mc>0 -> MC-dropout mean and std.

    Tiles are batched (BATCH per forward) and run under autocast (fp16 on CUDA); sigmoid and the
    mean/std over MC passes are accumulated in fp32 on the GPU. Halves the batch on CUDA OOM.
    """
    from model import enable_mc_dropout

    batch = batch or BATCH
    amp = AMP if amp is None else amp
    _, h, w = xn.shape
    acc = np.zeros((h, w), np.float64)
    acc2 = np.zeros((h, w), np.float64)
    cnt = np.zeros((h, w), np.float64)
    if mc:
        enable_mc_dropout(model)
    else:
        model.eval()
    coords = tiles(h, w)
    n = max(mc, 1)
    i = 0
    while i < len(coords):
        chunk = coords[i:i + batch]
        tt = torch.from_numpy(np.stack([pad_to(xn[:, y:y + TILE, x:x + TILE], TILE) for y, x in chunk]))
        tt = tt.to(device, non_blocking=True)
        try:
            s = torch.zeros((len(chunk), TILE, TILE), device=device)
            s2 = torch.zeros_like(s)
            for _ in range(n):
                with torch.autocast(device.type, enabled=amp and device.type == "cuda"):
                    lg = model(tt)
                p = torch.sigmoid(lg.float())[:, 0]
                s += p
                s2 += p * p
        except torch.cuda.OutOfMemoryError:
            if batch == 1:
                raise
            torch.cuda.empty_cache()
            batch = max(1, batch // 2)
            continue
        mean = (s / n).cpu().numpy()
        std = torch.sqrt(torch.clamp(s2 / n - (s / n) ** 2, min=0)).cpu().numpy() if mc else None
        for k, (y, x) in enumerate(chunk):
            hh, ww = min(TILE, h - y), min(TILE, w - x)
            acc[y:y + hh, x:x + ww] += mean[k, :hh, :ww]
            if mc:
                acc2[y:y + hh, x:x + ww] += std[k, :hh, :ww]
            cnt[y:y + hh, x:x + ww] += 1
        i += len(chunk)
    model.eval()
    prob = (acc / np.maximum(cnt, 1)).astype(np.float32)
    std = (acc2 / np.maximum(cnt, 1)).astype(np.float32) if mc else None
    return prob, std


@torch.no_grad()
def adabn(model: nn.Module, scenes: list[np.ndarray], device) -> nn.Module:
    m = copy.deepcopy(model)
    bns = [mod for mod in m.modules() if isinstance(mod, nn.modules.batchnorm._BatchNorm)]
    for bn in bns:
        bn.reset_running_stats()
        bn.momentum = None  # cumulative moving average over all batches
    m.eval()
    for bn in bns:
        bn.train()
    total = sum(len(tiles(xn.shape[1], xn.shape[2])) for xn in scenes)
    n = 0
    for xn in scenes:
        _, h, w = xn.shape
        for y, x in tiles(h, w):
            t = pad_to(xn[:, y:y + TILE, x:x + TILE], TILE)
            m(torch.from_numpy(t)[None].to(device))
            n += 1
            if n == 1 or n % 25 == 0 or n == total:
                print(f"AdaBN progress: {n}/{total} tiles ({100*n/total:.0f}%)", flush=True)
    m.eval()
    print(f"AdaBN: {len(bns)} BN layers re-estimated on {n} NISAR tiles")
    return m


def main() -> None:
    from model import load_model

    from common import gpu_start
    device = gpu_start(__file__)
    s1 = load_stats()
    model = load_model(MODELS / "unet_s1.pt", device)
    sc = pd.read_csv(OUTPUTS / "nisar_scenes.csv")
    raw = [load_scene(p)[0] for p in sc["nisar_tif"]]
    for mode in ("s1", "scene"):
        xs = [norm_scene(x, mode, s1)[0] for x in raw]
        m = adabn(model, xs, device)
        ck = torch.load(MODELS / "unet_s1.pt", map_location="cpu", weights_only=False)
        ck["state_dict"] = m.state_dict()
        ck["adabn"] = {"input_norm": mode, "n_scenes": len(xs)}
        torch.save(ck, MODELS / f"unet_s1_adabn_{mode}norm.pt")
        print("saved", MODELS / f"unet_s1_adabn_{mode}norm.pt")


if __name__ == "__main__":
    main()
