"""Step 5: train the water U-Net on Sen1Floods11 hand labels (masked BCE + Dice).

Usage:
  python src/train.py --limit 20 --epochs 1          # smoke test
  python src/train.py --epochs 40                    # full run
  python src/train.py --eval-only                    # test-split IoU of the saved best checkpoint
"""
from __future__ import annotations

import argparse
import time

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from common import MODELS, OUTPUTS, append_results, scores
from data_s1 import IGNORE, S1Dataset, load_stats
from model import WaterUNet, load_model

CKPT = MODELS / "unet_s1.pt"


def masked_loss(logits, target):
    logits = logits[:, 0]
    valid = target != IGNORE
    if valid.sum() == 0:
        return logits.sum() * 0
    y = (target == 1).float()
    bce = F.binary_cross_entropy_with_logits(logits[valid], y[valid])
    p = torch.sigmoid(logits) * valid
    inter = (p * y * valid).sum()
    dice = 1 - (2 * inter + 1) / (p.sum() + (y * valid).sum() + 1)
    return bce + dice


@torch.no_grad()
def evaluate(model, loader, device):
    model.eval()
    tp = fp = fn = 0
    losses = []
    for x, t in loader:
        x, t = x.to(device), t.to(device)
        with torch.autocast(device.type, enabled=device.type == "cuda"):
            lg = model(x)
        losses.append(masked_loss(lg.float(), t).item())
        pred = lg[:, 0] > 0
        v = t != IGNORE
        y = t == 1
        tp += int((pred & y & v).sum())
        fp += int((pred & ~y & v).sum())
        fn += int((~pred & y & v).sum())
    return float(np.mean(losses)), scores(tp, fp, fn), int(tp + fp + fn)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--bs", type=int, default=8)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--crop", type=int, default=256)
    ap.add_argument("--dropout", type=float, default=0.2)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--eval-only", action="store_true")
    a = ap.parse_args()

    from common import gpu_start
    device = gpu_start(__file__)
    stats = load_stats()
    mk = lambda split, **kw: S1Dataset(split, stats, limit=a.limit, **kw)
    val_dl = DataLoader(mk("valid"), batch_size=4, num_workers=a.workers)
    test_dl = DataLoader(mk("test"), batch_size=4, num_workers=a.workers)

    if not a.eval_only:
        torch.manual_seed(0)
        np.random.seed(0)
        train_dl = DataLoader(mk("train", augment=True, crop=a.crop), batch_size=a.bs, shuffle=True,
                              num_workers=a.workers, drop_last=True, persistent_workers=a.workers > 0)
        model = WaterUNet(dropout=a.dropout).to(device)
        opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-4)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=a.epochs)
        scaler = torch.amp.GradScaler(enabled=device.type == "cuda")
        log, best = [], -1.0
        print(f"device={device} train={len(train_dl.dataset)} val={len(val_dl.dataset)} test={len(test_dl.dataset)}")
        for ep in range(1, a.epochs + 1):
            model.train()
            t0, tl = time.time(), []
            for x, t in train_dl:
                x, t = x.to(device), t.to(device)
                opt.zero_grad(set_to_none=True)
                with torch.autocast(device.type, enabled=device.type == "cuda"):
                    lg = model(x)
                loss = masked_loss(lg.float(), t)
                scaler.scale(loss).backward()
                scaler.step(opt)
                scaler.update()
                tl.append(loss.item())
            sched.step()
            vl, vs, _ = evaluate(model, val_dl, device)
            row = {"epoch": ep, "train_loss": np.mean(tl), "val_loss": vl, "val_iou": vs["iou"],
                   "val_precision": vs["precision"], "val_recall": vs["recall"], "sec": time.time() - t0}
            log.append(row)
            pd.DataFrame(log).to_csv(OUTPUTS / "train_log.csv", index=False)
            flag = ""
            if vs["iou"] > best:
                best = vs["iou"]
                torch.save({"state_dict": model.state_dict(), "dropout": a.dropout, "epoch": ep,
                            "val_iou": best, "norm": {"mean_db": stats["mean_db"], "std_db": stats["std_db"]},
                            "args": vars(a)}, CKPT)
                flag = " *best"
            print(f"ep {ep:3d} train {row['train_loss']:.4f} val {vl:.4f} IoU {vs['iou']:.4f} "
                  f"({row['sec']:.0f}s){flag}", flush=True)

    model = load_model(CKPT, device)
    _, ts, _ = evaluate(model, test_dl, device)
    ck = torch.load(CKPT, map_location="cpu", weights_only=False)
    print("test", ts)
    if a.limit:
        print("(--limit used: not writing results.csv)")
        return
    append_results([{"domain": "S1 test", "method": "U-Net (source-only)", **ts,
                     "n_pixels": None, "notes": f"best val IoU {ck['val_iou']:.4f} @ epoch {ck['epoch']}"}])


if __name__ == "__main__":
    main()
