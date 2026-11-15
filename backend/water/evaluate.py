"""Step 8: evaluate all methods on NISAR against the DSWx-HLS reference; per-date water areas.

Methods (rows in results.csv, domain = "NISAR <reservoir>"):
  Otsu (HV dB, per scene) | U-Net source-only | U-Net + per-scene norm | U-Net + AdaBN | U-Net + AdaBN + per-scene norm
DSWx is an optical, weak reference at a nearby date (|dt| <= 5 days), not ground truth.

Writes: outputs/results.csv (appends NISAR rows), outputs/nisar_eval_per_date.csv,
        NASA_DATA/outputs/prob_<method>_<tag>.tif (water probability, for change detection)
Usage:  python src/evaluate.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import rasterio
import torch
from skimage.filters import threshold_otsu

from adabn import load_scene, norm_scene, predict_scene
from common import BIG_OUT, MODELS, OUTPUTS, append_results, confusion, dpath, scores
from data_s1 import CLIP_DB, load_stats
from model import load_model
from nisar_prep import write_tif

METHODS = {
    # name: (checkpoint, input normalization)
    "U-Net source-only": ("unet_s1.pt", "s1"),
    "U-Net + per-scene norm": ("unet_s1.pt", "scene"),
    "U-Net + AdaBN": ("unet_s1_adabn_s1norm.pt", "s1"),
    "U-Net + AdaBN + per-scene norm": ("unet_s1_adabn_scenenorm.pt", "scene"),
}
MIN_DSWX_VALID = 0.95
OTSU = "Otsu (HV dB, per scene)"
GLOBAL = "Global HV threshold (fit on S1 train VH)"


def slug(m: str) -> str:
    return m.lower().replace(" + ", "_").replace(" ", "-").replace("(", "").replace(")", "")


def otsu_scene(hv_db: np.ndarray, valid: np.ndarray) -> np.ndarray:
    v = np.clip(hv_db[valid], *CLIP_DB)
    return (np.clip(np.nan_to_num(hv_db, nan=0), *CLIP_DB) < threshold_otsu(v)) & valid


def pixel_area_km2(profile) -> float:
    t = profile["transform"]
    return abs(t.a * t.e) / 1e6


def main() -> None:
    from common import gpu_start
    device = gpu_start(__file__)
    s1 = load_stats()
    scenes = pd.read_csv(OUTPUTS / "nisar_scenes.csv")
    models = {m: load_model(MODELS / ck, device) for m, (ck, _) in METHODS.items()}
    reservoir = scenes["tag"].iloc[0].split("_T")[0]
    import json
    thresholds = json.loads((OUTPUTS / "thresholds.json").read_text())
    gthr = thresholds["global_vh_threshold_db"]
    pthr = thresholds["unet_probability_threshold"]
    acc = {m: [0, 0, 0] for m in [OTSU, GLOBAL, *METHODS]}
    npx = 0
    per_date = []
    for _, sc in scenes.iterrows():
        x_db, prof = load_scene(sc["nisar_tif"])
        valid_sar = np.all(np.isfinite(x_db), 0)
        ref, ref_valid = None, None
        if isinstance(sc.get("dswx_tif"), str) and sc["dswx_tif"]:
            with rasterio.open(dpath(sc["dswx_tif"])) as r:
                ref = r.read(1)
            ref_valid = (ref != 255) & valid_sar
        px = pixel_area_km2(prof)
        preds = {OTSU: otsu_scene(x_db[1], valid_sar),
                 GLOBAL: (np.nan_to_num(x_db[1], nan=0) < gthr) & valid_sar}
        for m, (_, mode) in METHODS.items():
            xn, _ = norm_scene(x_db, mode, s1)
            prob, _ = predict_scene(models[m], xn, device)
            prob[~valid_sar] = np.nan
            # Fixed on the Sentinel-1 validation split; never tune on NISAR.
            preds[m] = (prob > pthr) & valid_sar
        row = {"tag": sc["tag"], "date": sc["date"], "track": sc["track"], "direction": sc["direction"],
               "dswx_date": sc.get("dswx_date"), "sar_valid_frac": float(valid_sar.mean()),
               "dswx_valid_frac": float(ref_valid.sum() / valid_sar.sum()) if ref is not None else np.nan,
               "dswx_water_km2": float(((ref == 1) & ref_valid).sum() * px) if ref is not None else np.nan}
        clear_ref = ref is not None and row["dswx_valid_frac"] >= MIN_DSWX_VALID
        row["dswx_flag"] = "" if ref is None or clear_ref else "partial coverage"
        if clear_ref:
            npx += int(ref_valid.sum())
        for m, p in preds.items():
            row[f"area_km2|{m}"] = float(p.sum() * px)
            if ref is not None:
                tp, fp, fn = confusion(p, ref == 1, ref_valid)
                row[f"tp|{m}"], row[f"fp|{m}"], row[f"fn|{m}"] = tp, fp, fn
                if clear_ref:
                    acc[m] = [acc[m][0] + tp, acc[m][1] + fp, acc[m][2] + fn]
                row[f"iou|{m}"] = scores(tp, fp, fn)["iou"]
                row[f"area_on_dswx_valid_km2|{m}"] = float((p & ref_valid).sum() * px)
        per_date.append(row)
        print(sc["tag"], {k: round(v, 3) for k, v in row.items() if k.startswith("iou|")})
    pd.DataFrame(per_date).to_csv(OUTPUTS / "nisar_eval_per_date.csv", index=False)
    n_ref = sum(r["dswx_flag"] == "" and pd.notna(r["dswx_valid_frac"]) for r in per_date)
    rows = [{"domain": f"NISAR {reservoir}", "method": m, **scores(*acc[m]), "n_pixels": npx,
             "notes": (f"vs DSWx-HLS (weak optical ref, |dt|<=5 d), {n_ref} dates pooled, "
                       f">=95% DSWx valid; HH->VV, HV->VH; U-Net p>{pthr:.2f} fixed on S1 validation")}
            for m in acc]
    for r in rows:
        print(r)
    append_results(rows)

    best_row = max((r for r in rows if r["method"] in METHODS), key=lambda r: r["iou"])
    global_row = next(r for r in rows if r["method"] == GLOBAL)
    (OUTPUTS / "nisar_claim_gate.json").write_text(json.dumps({
        "claim": "Water U-Net beats the fixed global cross-pol threshold on pooled DSWx comparison",
        "passes": bool(best_row["iou"] > global_row["iou"]),
        "best_unet_method": best_row["method"], "best_unet_iou": best_row["iou"],
        "global_threshold_iou": global_row["iou"],
        "difference": best_row["iou"] - global_row["iou"]}, indent=2))

    # Keep probability rasters only for the best U-Net transfer variant.  The
    # remaining variants are metrics-only, which keeps the external data root
    # within the 2 GB project budget.
    best = best_row["method"]
    _, mode = METHODS[best]
    for _, sc in scenes.iterrows():
        x_db, prof = load_scene(sc["nisar_tif"])
        valid = np.all(np.isfinite(x_db), 0)
        xn, _ = norm_scene(x_db, mode, s1)
        prob, _ = predict_scene(models[best], xn, device)
        prob[~valid] = np.nan
        write_tif(BIG_OUT / f"prob_{slug(best)}_{sc['tag']}.tif", prob, prof["crs"].to_epsg(), prof["transform"],
                  np.nan, "float32", ["water_probability"])
    print(f"saved probability rasters for best U-Net variant only: {best}")


if __name__ == "__main__":
    main()
