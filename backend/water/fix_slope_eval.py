"""Proposed fix, evaluated without leakage: terrain-consistency filter (standing water is flat).

Rule: predicted water is kept only where the DEM slope (OPERA DSWx B10_DEM layer, 30 m Copernicus-based,
bilinear to the NISAR 10 m grid, slope from a 3x3 smoothed DEM) is <= S degrees.
S is chosen on the SELECTION track only (max pooled IoU vs DSWx); the held-out tracks are then scored once
with that S, with 95% date-bootstrap intervals, next to the unfiltered model. Also reports the area bias
before/after on held-out tracks. Operational outputs are NOT changed; results go to
outputs/fix_slope_eval.json.
Usage: python fix_slope_eval.py
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import Resampling
from scipy.ndimage import uniform_filter

from common import BIG_OUT, DATA, OUTPUTS, dpath
from diagnose_mask import read_to_grid
from evaluate import slug

GRID_S = [3, 5, 7, 10, 12, 15, 20, 25, 30, 90]  # 90 = no filter
N_BOOT, SEED = 1000, 0


def main() -> None:
    import earthaccess

    held = json.loads((OUTPUTS / "heldout_eval.json").read_text())
    m, thr, sel_track = held["variant_selected_on_selection_track"], held["probability_threshold"], held["selection_track"]
    hp = pd.read_csv(OUTPUTS / "heldout_per_date.csv")
    hp = hp[hp["use"]] if "use" in hp else hp
    scenes = pd.read_csv(OUTPUTS / "nisar_scenes.csv").set_index("tag")
    cand = pd.read_csv(OUTPUTS / "candidate_scenes.csv")
    cand = cand[(cand["reservoir"] == held["reservoir"]) & cand["usable"]].set_index(["date", "track"])
    fs = None
    slopes = {}
    rows = []
    for _, r in hp.iterrows():
        tag = r["tag"]
        with rasterio.open(BIG_OUT / f"prob_{slug(m)}_{tag}.tif") as s:
            prob, crs, tr = s.read(1), s.crs, s.transform
        key = (tuple(round(v, 3) for v in tr[:6]), prob.shape)
        if key not in slopes:
            cache = DATA / "hls" / f"dem_T{int(r['track']):03d}.npz"
            if cache.exists():
                dem = np.load(cache)["dem"]
            else:
                if fs is None:
                    earthaccess.login(strategy="environment")
                    fs = earthaccess.get_fsspec_https_session()
                c = cand.loc[(scenes.loc[tag].date, int(r["track"]))]
                url = c["wtr_urls"].split(";")[0].replace("_B01_WTR.tif", "_B10_DEM.tif")
                dem = read_to_grid(url, fs, crs, tr, prob.shape, Resampling.bilinear)
                cache.parent.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(cache, dem=dem)
            d = uniform_filter(np.nan_to_num(dem, nan=np.nanmedian(dem)), 3)
            gy, gx = np.gradient(d, abs(tr.a))
            slopes[key] = np.degrees(np.arctan(np.hypot(gx, gy)))
        slope = slopes[key]
        with rasterio.open(dpath(scenes.loc[tag].dswx_tif)) as s:
            ref = s.read(1)
        v = np.isfinite(prob) & (ref != 255)
        ours = np.nan_to_num(prob) >= thr
        y = ref == 1
        px = abs(tr.a * tr.e) / 1e6
        row = {"tag": tag, "track": int(r["track"]), "set": r["set"], "dswx_km2": float((y & v).sum() * px)}
        for S in GRID_S:
            p = ours & (slope <= S)
            row[f"tp|{S}"], row[f"fp|{S}"], row[f"fn|{S}"] = int((p & y & v).sum()), int((p & ~y & v).sum()), int((~p & y & v).sum())
            row[f"area|{S}"] = float((p & v).sum() * px)
        rows.append(row)
        print(tag, "done", flush=True)
    df = pd.DataFrame(rows)

    def pooled(d, S):
        tp, fp, fn = d[f"tp|{S}"].sum(), d[f"fp|{S}"].sum(), d[f"fn|{S}"].sum()
        return tp / (tp + fp + fn), tp / (tp + fp), tp / (tp + fn)

    sel, ho = df[df["track"] == sel_track], df[df["track"] != sel_track]
    sel_iou = {S: pooled(sel, S)[0] for S in GRID_S}
    S_best = max(sel_iou, key=sel_iou.get)
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(ho), size=(N_BOOT, len(ho)))

    def boot(S):
        T, F, N = (ho[f"{k}|{S}"].to_numpy(float)[idx].sum(1) for k in ("tp", "fp", "fn"))
        return {"iou": np.percentile(T / (T + F + N), [2.5, 97.5]).tolist(),
                "precision": np.percentile(T / (T + F), [2.5, 97.5]).tolist(),
                "recall": np.percentile(T / (T + N), [2.5, 97.5]).tolist()}

    def bias(S):
        b = (ho[f"area|{S}"] - ho["dswx_km2"]).to_numpy()
        bb = b[idx].mean(1)
        return {"mean_km2": float(b.mean()), "ci95_km2": np.percentile(bb, [2.5, 97.5]).tolist()}

    # paired IoU difference (filtered minus unfiltered) on held-out, same resamples
    def iou_res(S):
        T, F, N = (ho[f"{k}|{S}"].to_numpy(float)[idx].sum(1) for k in ("tp", "fp", "fn"))
        return T / (T + F + N)
    diff = iou_res(S_best) - iou_res(90)
    out = {"rule": "keep predicted water only where DEM slope <= S degrees", "dem": "OPERA DSWx B10_DEM (30 m), bilinear to 10 m, 3x3 smoothed",
           "method": m, "selection_track": sel_track, "heldout_tracks": sorted(ho["track"].unique().tolist()),
           "selection_iou_by_S": {str(k): v for k, v in sel_iou.items()}, "S_chosen_on_selection": S_best,
           "heldout_unfiltered": dict(zip(("iou", "precision", "recall"), pooled(ho, 90)), ci95=boot(90), area_bias=bias(90)),
           "heldout_filtered": dict(zip(("iou", "precision", "recall"), pooled(ho, S_best)), ci95=boot(S_best), area_bias=bias(S_best)),
           "heldout_paired_iou_difference": {"mean": float(pooled(ho, S_best)[0] - pooled(ho, 90)[0]),
                                             "ci95": np.percentile(diff, [2.5, 97.5]).tolist(), "p_le_0": float((diff <= 0).mean())},
           "n_dates": {"selection": len(sel), "heldout": len(ho)},
           "heldout_iou_by_S_for_information_only": {str(S): pooled(ho, S)[0] for S in GRID_S}}
    (OUTPUTS / "fix_slope_eval.json").write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps({k: out[k] for k in ("selection_iou_by_S", "S_chosen_on_selection", "heldout_unfiltered",
                                          "heldout_filtered", "heldout_paired_iou_difference", "n_dates")}, indent=1, default=float))


if __name__ == "__main__":
    main()
