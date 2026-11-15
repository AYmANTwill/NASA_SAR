"""S1 evaluation with uncertainty (no training).

- Methods: per-chip Otsu (VH, VV), global VH threshold (fit on train), U-Net @ p=0.5,
  U-Net @ p* (p* maximizes pooled IoU on the VALIDATION split only).
- Splits: test, Bolivia hold-out (event never seen in training; 15 chips).
- 95% intervals: bootstrap over chips (1000 resamples, percentile), pooled-pixel metrics.
- Paired bootstrap: U-Net minus global threshold (same resampled chips).
Writes outputs/results.csv (S1 rows replaced), outputs/s1_paired_diff.csv,
       outputs/thresholds.json, outputs/train_config.json
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
import torch

from baseline_otsu import otsu_water
from common import MODELS, OUTPUTS, rel
from data_s1 import available, load_chip, load_stats, normalize, to_db_if_linear
from model import load_model

N_BOOT = 1000
SEED = 0
GLOBAL = "Global VH threshold (fit on train)"


def counts(pred, ref, valid):
    p, r = pred[valid], ref[valid]
    return int((p & r).sum()), int((p & ~r).sum()), int((~p & r).sum())


def metrics(c):  # c: (..., 3) summed tp, fp, fn
    tp, fp, fn = c[..., 0], c[..., 1], c[..., 2]
    return {"iou": tp / np.maximum(tp + fp + fn, 1), "precision": tp / np.maximum(tp + fp, 1),
            "recall": tp / np.maximum(tp + fn, 1)}


@torch.no_grad()
def chip_probs(model, ids, stats, device):
    out = []
    for c in ids:
        x, y = load_chip(c)
        x = to_db_if_linear(x)
        xn, valid_x = normalize(x, stats["mean_db"], stats["std_db"])
        with torch.autocast(device.type, enabled=device.type == "cuda"):
            p = torch.sigmoid(model(torch.from_numpy(xn)[None].to(device)))[0, 0].float().cpu().numpy()
        out.append((x, y, p, valid_x & (y != -1)))
    return out


def per_chip_counts(data, gthr, pthr):
    meths = {"Otsu (VH dB, per chip)": lambda x, p, v: otsu_water(x[1], v),
             "Otsu (VV dB, per chip)": lambda x, p, v: otsu_water(x[0], v),
             GLOBAL: lambda x, p, v: (np.nan_to_num(x[1], nan=0) < gthr) & v,
             "U-Net (source-only, p>0.5)": lambda x, p, v: (p > 0.5) & v,
             f"U-Net (source-only, p>{pthr:.2f} tuned on val)": lambda x, p, v: (p > pthr) & v}
    C = {m: np.array([counts(f(x, p, v), y == 1, v) for x, y, p, v in data]) for m, f in meths.items()}
    return C, np.array([int(v.sum()) for _, _, _, v in data])


def boot_rows(C, valid_pixels, domain, rng, note):
    n = len(next(iter(C.values())))
    idx = rng.integers(0, n, size=(N_BOOT, n))  # same resamples for every method (paired)
    rows, boots = [], {}
    for m, c in C.items():
        point = metrics(c.sum(0))
        b = metrics(c[idx].sum(1))
        boots[m] = b
        row = {"domain": domain, "method": m, **{k: float(v) for k, v in point.items()},
               "n_pixels": int(valid_pixels.sum()), "notes": note}
        for k in ("iou", "precision", "recall"):
            row[f"{k}_ci95_lo"], row[f"{k}_ci95_hi"] = np.percentile(b[k], [2.5, 97.5]).tolist()
        rows.append(row)
    return rows, boots


def main() -> None:
    from common import gpu_start
    device = gpu_start(__file__)
    stats = load_stats()
    ck_path = MODELS / "unet_s1.pt"
    model = load_model(ck_path, device)
    gthr = json.loads((OUTPUTS / "global_threshold.json").read_text())["threshold_db"]

    # probability threshold: VALIDATION split only
    val = chip_probs(model, available("valid"), stats, device)
    grid = np.round(np.arange(0.05, 0.96, 0.05), 2)
    vc = np.array([[sum(counts(p > t, y == 1, v)[k] for _, y, p, v in val) for k in range(3)] for t in grid])
    viou = metrics(vc)["iou"]
    pthr = float(grid[int(np.argmax(viou))])
    print("val IoU by threshold:", dict(zip(grid.tolist(), np.round(viou, 4).tolist())), "-> p* =", pthr)

    rng = np.random.default_rng(SEED)
    all_rows, diffs = [], []
    for split, domain in (("test", "S1 test"), ("bolivia", "S1 Bolivia hold-out")):
        ids = available(split)
        data = chip_probs(model, ids, stats, device)
        C, valid_pixels = per_chip_counts(data, gthr, pthr)
        rows, boots = boot_rows(C, valid_pixels, domain, rng,
                                f"{len(ids)} chips, pooled pixels, 95% CI = bootstrap over chips ({N_BOOT})")
        all_rows += rows
        for m in [k for k in boots if k.startswith("U-Net")]:
            for k in ("iou", "precision", "recall"):
                d = boots[m][k] - boots[GLOBAL][k]
                pt = rows[[r["method"] for r in rows].index(m)][k] - rows[[r["method"] for r in rows].index(GLOBAL)][k]
                lo, hi = np.percentile(d, [2.5, 97.5])
                diffs.append({"domain": domain, "comparison": f"{m} minus {GLOBAL}", "metric": k,
                              "diff": pt, "ci95_lo": lo, "ci95_hi": hi, "p_le_0": float((d <= 0).mean())})
    for r in all_rows:
        print(f"{r['domain']:20s} {r['method']:48s} IoU {r['iou']:.3f} [{r['iou_ci95_lo']:.3f},{r['iou_ci95_hi']:.3f}] "
              f"P {r['precision']:.3f} R {r['recall']:.3f}")
    dd = pd.DataFrame(diffs)
    dd.to_csv(OUTPUTS / "s1_paired_diff.csv", index=False)
    print(dd.to_string(index=False))

    f = OUTPUTS / "results.csv"
    old = pd.read_csv(f) if f.exists() else pd.DataFrame()
    if len(old):
        old = old[~old["domain"].astype(str).str.startswith("S1")]
    pd.concat([pd.DataFrame(all_rows), old], ignore_index=True).to_csv(f, index=False)

    (OUTPUTS / "thresholds.json").write_text(json.dumps({
        "global_vh_threshold_db": gthr, "global_vh_threshold_fitted_on": "Sen1Floods11 train (max train IoU)",
        "unet_probability_threshold": pthr, "unet_probability_threshold_fitted_on": "Sen1Floods11 valid (max pooled IoU)",
        "unet_val_iou_at_threshold": float(viou.max()), "grid": grid.tolist(),
        "rule": "fixed; reused unchanged for NISAR (never tuned on test or NISAR)"}, indent=2))

    ck = torch.load(ck_path, map_location="cpu", weights_only=False)
    sha = hashlib.sha256(ck_path.read_bytes()).hexdigest()
    (OUTPUTS / "train_config.json").write_text(json.dumps({
        "seed": 0, "checkpoint": rel(ck_path), "checkpoint_sha256": sha, "best_epoch": ck["epoch"],
        "best_val_iou": ck["val_iou"], "train_args": ck["args"], "normalization": ck["norm"],
        "architecture": "smp.Unet resnet34 (ImageNet init), in_channels=2 [VV,VH dB], classes=1, Dropout2d before head",
        "loss": "masked BCE + masked soft Dice (label -1 ignored)", "optimizer": "AdamW wd=1e-4, cosine LR",
        "augmentation": "random 256 crops, flips, rot90", "torch": torch.__version__}, indent=2, default=str))
    print("p* =", pthr, "sha256", sha[:16])


if __name__ == "__main__":
    main()
