"""Write water-probability GeoTIFFs for the operational variant (chosen on the selection track only).

Rasters go to NASA_DATA/outputs/prob_<variant-slug>_<tag>.tif (outside the repo). Probability
rasters of other variants are deleted afterwards to stay inside the 2 GB data budget.
Usage: python save_probs.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch

from adabn import load_scene, norm_scene, predict_scene
from common import BIG_OUT, MODELS, OUTPUTS, dir_size
from data_s1 import load_stats
from evaluate import METHODS, slug
from model import load_model
from nisar_prep import write_tif
from timeseries import best_method


def main() -> None:
    from common import gpu_start
    device = gpu_start(__file__)
    m = best_method()
    ck, mode = METHODS[m]
    model = load_model(MODELS / ck, device)
    s1 = load_stats()
    scenes = pd.read_csv(OUTPUTS / "nisar_scenes.csv")
    keep = f"prob_{slug(m)}_"
    for _, sc in scenes.iterrows():
        x_db, prof = load_scene(sc["nisar_tif"])
        valid = np.all(np.isfinite(x_db), 0)
        prob, _ = predict_scene(model, norm_scene(x_db, mode, s1, src=sc["nisar_tif"])[0], device)
        prob[~valid] = np.nan
        write_tif(BIG_OUT / f"{keep}{sc['tag']}.tif", prob, prof["crs"].to_epsg(), prof["transform"],
                  np.nan, "float32", ["water_probability"])
    wanted = {f"{keep}{t}.tif" for t in scenes["tag"]}
    stale = [p for p in BIG_OUT.glob("prob_*.tif") if p.name not in wanted]
    for p in stale:
        p.unlink()
    print(f"{m}: wrote {len(scenes)} rasters, removed {len(stale)} stale; data root {dir_size()/1e9:.2f} GB")


if __name__ == "__main__":
    main()
