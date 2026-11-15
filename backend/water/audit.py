"""Audit NISAR orbit hold-out and geometric sensitivity to DSWx alignment."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import Resampling, reproject

from common import BIG_OUT, OUTPUTS, dpath
from evaluate import slug


def main():
    rows = pd.read_csv(OUTPUTS / "nisar_eval_per_date.csv")
    clear = rows[rows.dswx_valid_frac >= .95]
    methods = [c[3:] for c in clear if c.startswith("tp|")]

    def score(group, method):
        tp = group[f"tp|{method}"].sum()
        fp = group[f"fp|{method}"].sum()
        fn = group[f"fn|{method}"].sum()
        return float(tp / (tp + fp + fn))

    select = clear[clear.track.isin([44, 95])]
    holdout = clear[clear.track == 116]
    chosen = max(methods, key=lambda m: score(select, m))
    orbit = {m: {"selection_iou": score(select, m), "held_out_T116_iou": score(holdout, m)}
             for m in methods}
    scenes = pd.read_csv(OUTPUTS / "nisar_scenes.csv").set_index("tag")
    alignment = {}
    for date in ("2026-06-17", "2026-06-29"):
        row = clear[(clear.track == 44) & (clear.date == date)].iloc[0]
        ref_path = dpath(scenes.loc[row.tag, "dswx_tif"])
        pred_path = BIG_OUT / f"prob_{slug(chosen)}_{row.tag}.tif"
        with rasterio.open(pred_path) as pred_src, rasterio.open(ref_path) as ref_src:
            prob = pred_src.read(1)
            ref = np.full(prob.shape, 255, np.uint8)
            reproject(ref_src.read(1), ref,
                      src_transform=ref_src.transform, src_crs=ref_src.crs,
                      dst_transform=pred_src.transform, dst_crs=pred_src.crs,
                      src_nodata=255, dst_nodata=255, resampling=Resampling.nearest)
            water = prob >= .4
            valid = (ref != 255) & np.isfinite(prob)
            truth = ref == 1
            scores = {}
            for dy in range(-5, 6):
                for dx in range(-5, 6):
                    shifted = np.roll(water, (dy, dx), axis=(0, 1))
                    if dy > 0: shifted[:dy] = False
                    elif dy < 0: shifted[dy:] = False
                    if dx > 0: shifted[:, :dx] = False
                    elif dx < 0: shifted[:, dx:] = False
                    inter = np.count_nonzero(shifted & truth & valid)
                    union = np.count_nonzero((shifted | truth) & valid)
                    scores[(dx, dy)] = inter / union
            best_shift = max(scores, key=scores.get)
            alignment[date] = {"native_iou": scores[(0, 0)], "best_5px_iou": scores[best_shift],
                               "best_shift_pixels_x_y": best_shift,
                               "pixel_size_m": [abs(pred_src.transform.a), abs(pred_src.transform.e)],
                               "crs": str(pred_src.crs)}
    result = {"clear_dates": len(clear), "selection_dates": len(select), "held_out_dates": len(holdout),
              "chosen_on_T44_T95": chosen, "orbit_holdout": orbit,
              "june_alignment_sensitivity": alignment,
              "caveat": "T116 was excluded from DSWx variant selection, but AdaBN used unlabeled tiles from all tracks."}
    (OUTPUTS / "audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
