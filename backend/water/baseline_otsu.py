"""Step 4: threshold baselines on Sen1Floods11 (water = backscatter below threshold).

1. Per-chip Otsu on VH dB and on VV dB (weak: always splits a chip into two classes).
2. Global VH dB threshold: one threshold fitted on the TRAIN split (maximizing train IoU), applied
   unchanged to the test split and later to NISAR HV (saved to outputs/global_threshold.json).

Usage: python src/baseline_otsu.py [--split test]
"""
from __future__ import annotations

import argparse
import json

import numpy as np
from skimage.filters import threshold_otsu

from common import OUTPUTS, append_results, confusion, scores
from data_s1 import CLIP_DB, available, load_chip, to_db_if_linear

BINS = np.arange(CLIP_DB[0], CLIP_DB[1] + 0.05, 0.05)


def otsu_water(band_db: np.ndarray, valid: np.ndarray) -> np.ndarray:
    v = np.clip(band_db[valid], *CLIP_DB)
    if v.size < 10 or v.min() == v.max():
        return np.zeros_like(valid)
    return (np.clip(band_db, *CLIP_DB) < threshold_otsu(v)) & valid


def fit_global_threshold(band: int = 1) -> dict:
    """Histogram water / dry dB values on train; pick t maximizing pooled IoU of (x < t)."""
    hw = np.zeros(len(BINS) - 1)
    hd = np.zeros(len(BINS) - 1)
    for c in available("train"):
        x, y = load_chip(c)
        x = to_db_if_linear(x)
        valid = np.all(np.isfinite(x), 0) & (y != -1)
        v = np.clip(x[band][valid], CLIP_DB[0], CLIP_DB[1] - 1e-6)
        hw += np.histogram(v[y[valid] == 1], BINS)[0]
        hd += np.histogram(v[y[valid] == 0], BINS)[0]
    tp = np.cumsum(hw)  # threshold at upper edge of bin i
    fp = np.cumsum(hd)
    fn = hw.sum() - tp
    iou = tp / np.maximum(tp + fp + fn, 1)
    i = int(np.argmax(iou))
    return {"band": ["VV", "VH"][band], "threshold_db": round(float(BINS[i + 1]), 3),
            "train_iou": round(float(iou[i]), 4), "fitted_on": "Sen1Floods11 train split (hand labels)"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    a = ap.parse_args()

    g = fit_global_threshold(band=1)
    (OUTPUTS / "global_threshold.json").write_text(json.dumps(g, indent=2))
    print("global threshold:", g)

    ids = available(a.split)
    acc = {"Otsu (VH dB, per chip)": [0, 0, 0], "Otsu (VV dB, per chip)": [0, 0, 0],
           "Global VH threshold (fit on train)": [0, 0, 0]}
    npx = 0
    for c in ids:
        x, y = load_chip(c)
        x = to_db_if_linear(x)
        valid = np.all(np.isfinite(x), 0) & (y != -1)
        npx += int(valid.sum())
        preds = {"Otsu (VV dB, per chip)": otsu_water(x[0], valid),
                 "Otsu (VH dB, per chip)": otsu_water(x[1], valid),
                 "Global VH threshold (fit on train)": (np.nan_to_num(x[1], nan=0) < g["threshold_db"]) & valid}
        for name, p in preds.items():
            tp, fp, fn = confusion(p, y == 1, valid)
            acc[name] = [acc[name][0] + tp, acc[name][1] + fp, acc[name][2] + fn]
    rows = []
    for name, (tp, fp, fn) in acc.items():
        note = f"{len(ids)} chips, pooled pixels, no-data ignored"
        if name.startswith("Global"):
            note += f"; t = {g['threshold_db']} dB"
        rows.append({"domain": f"S1 {a.split}", "method": name, **scores(tp, fp, fn), "n_pixels": npx, "notes": note})
        print(rows[-1])
    append_results(rows)


if __name__ == "__main__":
    main()
