"""Step 9b: pre/post water change + MC-dropout uncertainty with the best NISAR method.

Pair = two dates of the chosen (selection) track with the largest |DSWx water area| difference,
using only dates with DSWx >= 95% valid that are not flagged "partial coverage", "dswx outlier"
or "possible wind effect"
(see water_area_timeseries.csv); if no DSWx difference is available, the earliest and latest dates.
gain = water_post AND NOT water_pre (refilling); loss = water_pre AND NOT water_post (drawdown).

Writes NASA_DATA/outputs/{water_pre,water_post,change,uncertainty_pre,uncertainty_post}.tif,
       outputs/change_pair.json and PNG quicklooks in outputs/.
Usage: python src/change_detect.py [--mc 20]
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd
import torch

from adabn import load_scene, norm_scene, predict_scene
from common import BIG_OUT, MODELS, OUTPUTS
from data_s1 import load_stats
from evaluate import METHODS, method_threshold
from model import load_model
from nisar_prep import write_tif
from timeseries import MIN_DSWX_VALID, best_method  # MIN_DSWX_VALID = 0.95


def choose_pair(per_date: pd.DataFrame, track: int) -> tuple[pd.Series, pd.Series, str]:
    g = per_date[per_date["track"] == track].sort_values("date")
    fixed = OUTPUTS / "case_pair.json"  # the case's event dates, fixed when the case was defined (model-independent)
    if fixed.exists():
        fx = json.loads(fixed.read_text())
        pre, post = (g[g["date"] == fx[k]].iloc[0] for k in ("pre", "post"))
        return pre, post, fx["why"]
    ts = pd.read_csv(OUTPUTS / "water_area_timeseries.csv")
    # SAR-side artefacts must not become headline endpoints either: wind-flagged dates are excluded
    clean = set(ts.loc[(ts["track"] == track) & ts["dswx_water_km2"].notna()
                       & ~ts["flag"].fillna("").str.contains("wind"), "date"])
    ok = g[(g["dswx_valid_frac"] >= MIN_DSWX_VALID) & g["date"].isin(clean)]
    if len(ok) >= 2 and ok["dswx_water_km2"].max() > ok["dswx_water_km2"].min():
        a, b = ok.loc[ok["dswx_water_km2"].idxmin()], ok.loc[ok["dswx_water_km2"].idxmax()]
        pre, post = (a, b) if a["date"] < b["date"] else (b, a)
        return pre, post, "largest DSWx water-area difference"
    return g.iloc[0], g.iloc[-1], "earliest and latest dates (no DSWx difference)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc", type=int, default=20, help="MC-dropout passes (0 to skip uncertainty)")
    a = ap.parse_args()
    from common import gpu_start
    device = gpu_start(__file__)
    meta = json.loads((OUTPUTS / "aoi.json").read_text())["chosen"]
    pthr = method_threshold(best_method())
    per_date = pd.read_csv(OUTPUTS / "nisar_eval_per_date.csv")
    scenes = pd.read_csv(OUTPUTS / "nisar_scenes.csv").set_index("tag")
    pre, post, why = choose_pair(per_date, meta["track"])
    m = best_method()
    if m not in METHODS:  # Otsu won: still use the best U-Net variant for uncertainty
        r = pd.read_csv(OUTPUTS / "results.csv")
        r = r[r["domain"].str.startswith("NISAR") & r["method"].isin(list(METHODS))]
        m = r.sort_values("iou", ascending=False).iloc[0]["method"]
    ck, mode = METHODS[m]
    model = load_model(MODELS / ck, device)
    s1 = load_stats()
    masks, info = {}, {"method": m, "probability_threshold": pthr,
                       "threshold_fitted_on": "Sen1Floods11 validation split",
                       "pair_rule": why, "mc_passes": a.mc}
    for name, row in (("pre", pre), ("post", post)):
        x_db, prof = load_scene(scenes.loc[row["tag"], "nisar_tif"])
        valid = np.all(np.isfinite(x_db), 0)
        xn, _ = norm_scene(x_db, mode, s1, src=scenes.loc[row["tag"], "nisar_tif"])
        prob, std = predict_scene(model, xn, device, mc=a.mc)
        w = ((prob > pthr) & valid).astype(np.uint8)
        w[~valid] = 255
        masks[name] = w
        epsg, tr = prof["crs"].to_epsg(), prof["transform"]
        write_tif(BIG_OUT / f"water_{name}.tif", w, epsg, tr, 255, "uint8", ["water(1)/not(0)/nodata(255)"])
        if a.mc:
            std[~valid] = np.nan
            write_tif(BIG_OUT / f"uncertainty_{name}.tif", np.stack([prob, std]), epsg, tr, np.nan, "float32",
                      ["mc_mean_probability", "mc_std"])
        info[name] = {"date": row["date"], "tag": row["tag"], "dswx_water_km2": row.get("dswx_water_km2")}
        _quicklook(x_db, w, std if a.mc else None, row["date"], OUTPUTS / f"quicklook_{name}.png")
    both = (masks["pre"] != 255) & (masks["post"] != 255)
    change = np.full(masks["pre"].shape, 255, np.uint8)
    change[both] = 0
    change[both & (masks["post"] == 1) & (masks["pre"] == 0)] = 1  # gain
    change[both & (masks["pre"] == 1) & (masks["post"] == 0)] = 2  # loss
    write_tif(BIG_OUT / "change.tif", change, epsg, tr, 255, "uint8", ["0 none, 1 gain (post&~pre), 2 loss"])
    px = abs(tr.a * tr.e) / 1e6
    info["gain_km2"] = float((change == 1).sum() * px)
    info["loss_km2"] = float((change == 2).sum() * px)
    info["water_pre_km2"] = float((masks["pre"] == 1).sum() * px)
    info["water_post_km2"] = float((masks["post"] == 1).sum() * px)
    (OUTPUTS / "change_pair.json").write_text(json.dumps(info, indent=2, default=str))
    _change_png(change, info, OUTPUTS / "change_map.png")
    print(json.dumps(info, indent=2, default=str))


def _quicklook(x_db, water, std, date, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = 4 if std is not None else 3
    fig, ax = plt.subplots(1, n, figsize=(4.2 * n, 4))
    ax[0].imshow(x_db[0], cmap="gray", vmin=-25, vmax=0); ax[0].set_title(f"HH dB {date}")
    ax[1].imshow(x_db[1], cmap="gray", vmin=-32, vmax=-8); ax[1].set_title("HV dB")
    ax[2].imshow(np.ma.masked_equal(water, 255), cmap="Blues", vmin=0, vmax=1); ax[2].set_title("predicted water")
    if std is not None:
        im = ax[3].imshow(std, cmap="magma", vmin=0, vmax=0.3); ax[3].set_title("MC-dropout std")
        fig.colorbar(im, ax=ax[3], fraction=0.046)
    for a_ in ax:
        a_.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _change_png(change, info, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    rgb = np.ma.masked_equal(change, 255)
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.imshow(rgb, cmap=ListedColormap(["#eeeeee", "#1f77b4", "#d62728"]), vmin=0, vmax=2, interpolation="nearest")
    ax.set_title(f"{info['pre']['date']} → {info['post']['date']}: gain (blue) {info['gain_km2']:.2f} km², "
                 f"loss (red) {info['loss_km2']:.2f} km²", fontsize=9)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    main()
