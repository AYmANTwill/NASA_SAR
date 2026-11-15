"""Per-track IoU and area bias of fine-tuned checkpoints on the VALIDATION reservoir only (Al Massira).

Optional label-free per-track AdaBN (--adabn-track): BatchNorm statistics re-estimated on the unlabelled tiles of
each track before predicting that track (transductive, no labels), to test whether a track-geometry shift explains
the bias. The case reservoir is never read here.
Usage: python finetune/diag_tracks.py unet_ft_v2_base.pt [--thr 0.35] [--adabn-track]
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import rasterio  # noqa: E402
import torch  # noqa: E402

from adabn import norm_scene, predict_scene  # noqa: E402
from common import MODELS, OUTPUTS, dpath  # noqa: E402
from data_s1 import IGNORE, load_stats  # noqa: E402
from model import load_model  # noqa: E402
from ft_train import VAL_SITE  # noqa: E402

TILE = 256


@torch.no_grad()
def adabn_on(model, scenes_xn, device):
    """Copy of the model with BN running stats re-estimated (cumulative average) on non-overlapping tiles."""
    m = copy.deepcopy(model)
    bns = [x for x in m.modules() if isinstance(x, torch.nn.modules.batchnorm._BatchNorm)]
    for b in bns:
        b.reset_running_stats(); b.momentum = None
    m.train()
    for mod in m.modules():
        if isinstance(mod, torch.nn.Dropout2d):
            mod.eval()
    for xn in scenes_xn:
        _, h, w = xn.shape
        tiles = [xn[:, r:r + TILE, c:c + TILE] for r in range(0, h - TILE + 1, TILE) for c in range(0, w - TILE + 1, TILE)]
        for i in range(0, len(tiles), 16):
            m(torch.from_numpy(np.nan_to_num(np.stack(tiles[i:i + 16]))).to(device))
    m.eval()
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("checkpoint")
    ap.add_argument("--thr", type=float, default=0.35)
    ap.add_argument("--adabn-track", action="store_true")
    a = ap.parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    s1 = load_stats()
    ds = pd.read_csv(OUTPUTS / "finetune" / "dataset.csv")
    val = ds[ds["site"] == VAL_SITE]
    base = load_model(MODELS / a.checkpoint, device)
    rows = []
    for track, g in val.groupby("track"):
        data = []
        for _, r in g.iterrows():
            with rasterio.open(dpath(r["nisar_tif"])) as s:
                x, tr = s.read().astype(np.float32), s.transform
            with rasterio.open(dpath(r["label_tif"])) as s:
                y = s.read(1)
            xn, valid = norm_scene(x, "s1", s1)
            data.append((r["date"], xn, valid, y, abs(tr.a * tr.e) / 1e6))
        model = adabn_on(base, [d[1] for d in data], device) if a.adabn_track else base
        for date, xn, valid, y, px in data:
            prob, _ = predict_scene(model, xn, device)
            v = valid & (y != IGNORE)
            p, t = (prob >= a.thr) & v, (y == 1) & v
            tp, fp, fn = int((p & t).sum()), int((p & ~t).sum()), int((~p & t).sum())
            rows.append({"track": int(track), "date": date, "tp": tp, "fp": fp, "fn": fn,
                         "bias_km2": (int(p.sum()) - int(t.sum())) * px, "dswx_km2": int(t.sum()) * px})
    d = pd.DataFrame(rows)
    out = {}
    for track, g in d.groupby("track"):
        s = g[["tp", "fp", "fn"]].sum()
        out[int(track)] = {"n": len(g), "iou": round(s.tp / (s.tp + s.fp + s.fn), 4),
                           "bias_km2_mean": round(g.bias_km2.mean(), 2), "bias_km2_std": round(g.bias_km2.std(), 2),
                           "dswx_km2_mean": round(g.dswx_km2.mean(), 2)}
    print(json.dumps({"checkpoint": a.checkpoint, "thr": a.thr, "adabn_track": a.adabn_track, "val_site": VAL_SITE,
                      "per_track": out}, indent=1))


if __name__ == "__main__":
    main()
