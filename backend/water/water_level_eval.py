"""Evaluate the water-level constraint without leakage (team rule 2026-11-14 night).

T is chosen on the SELECTION track only, minimising |mean area bias| (model area minus DSWx area on the
same DSWx-valid pixels), over T in GRID_T; the optimum must not sit at a grid edge (reported).
Held-out tracks are then scored once: unfiltered vs constrained, IoU / precision / recall / area bias with
95% date-bootstrap intervals and the paired IoU and |bias| differences.
Adoption rule: adopt only if held-out |area bias| decreases AND held-out IoU does not decrease.
Writes outputs/water_level_eval.json (+ per-date levels in outputs/water_level_per_date.csv).
Usage: python water_level_eval.py
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import rasterio

import water_level as wl
from common import BIG_OUT, DATA, OUTPUTS, dpath
from evaluate import slug

GRID_T = [2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20, 25, 30, 1000]  # 1000 = unfiltered
N_BOOT, SEED = 1000, 0


def dem_for(track: int) -> np.ndarray:
    return np.load(DATA / "hls" / f"dem_T{track:03d}.npz")["dem"]


def per_date_counts(method: str, thr: float, dates: pd.DataFrame, scenes: pd.DataFrame, grid=GRID_T,
                    prob_path=None) -> pd.DataFrame:
    rows = []
    for _, r in dates.iterrows():
        tag = r["tag"]
        p = prob_path(tag) if prob_path else BIG_OUT / f"prob_{slug(method)}_{tag}.tif"
        with rasterio.open(p) as s:
            prob, tr = s.read(1), s.transform
        with rasterio.open(dpath(scenes.loc[tag].dswx_tif)) as s:
            ref = s.read(1)
        dem = dem_for(int(r["track"]))
        assert dem.shape == prob.shape, f"DEM grid mismatch for {tag}"
        v, y = np.isfinite(prob) & (ref != 255), ref == 1
        px = abs(tr.a * tr.e) / 1e6
        lvl = wl.surface_level(prob, dem)
        row = {"tag": tag, "track": int(r["track"]), "set": r.get("set", ""), "level_m": lvl,
               "dswx_km2": float((y & v).sum() * px)}
        for T in grid:
            m = wl.apply(prob, dem, thr, T, level=lvl)
            row[f"tp|{T}"], row[f"fp|{T}"], row[f"fn|{T}"] = int((m & y & v).sum()), int((m & ~y & v).sum()), int((~m & y & v).sum())
            row[f"area|{T}"] = float((m & v).sum() * px)
        rows.append(row)
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame, T, idx) -> dict:
    def met(tp, fp, fn):
        return tp / (tp + fp + fn), tp / (tp + fp), tp / (tp + fn)
    tp, fp, fn = (df[f"{k}|{T}"].to_numpy(float) for k in ("tp", "fp", "fn"))
    b = df[f"area|{T}"].to_numpy() - df["dswx_km2"].to_numpy()
    iou, p, r = met(tp.sum(), fp.sum(), fn.sum())
    TT, FF, NN = tp[idx].sum(1), fp[idx].sum(1), fn[idx].sum(1)
    bi, bb = met(TT, FF, NN), b[idx].mean(1)
    return {"iou": iou, "precision": p, "recall": r, "area_bias_km2": float(b.mean()),
            "abs_area_bias_km2": float(abs(b.mean())),
            "ci95": {"iou": np.percentile(bi[0], [2.5, 97.5]).tolist(), "precision": np.percentile(bi[1], [2.5, 97.5]).tolist(),
                     "recall": np.percentile(bi[2], [2.5, 97.5]).tolist(), "area_bias_km2": np.percentile(bb, [2.5, 97.5]).tolist()},
            "_boot_iou": bi[0], "_boot_bias": bb}


def main() -> None:
    held = json.loads((OUTPUTS / "heldout_eval.json").read_text())
    m, thr, sel_track = held["variant_selected_on_selection_track"], held["probability_threshold"], held["selection_track"]
    hp = pd.read_csv(OUTPUTS / "heldout_per_date.csv")
    hp = hp[hp["use"]] if "use" in hp else hp
    scenes = pd.read_csv(OUTPUTS / "nisar_scenes.csv").set_index("tag")
    df = per_date_counts(m, thr, hp, scenes)
    df[["tag", "track", "set", "level_m", "dswx_km2"]].to_csv(OUTPUTS / "water_level_per_date.csv", index=False)
    sel, ho = df[df["track"] == sel_track], df[df["track"] != sel_track]
    sel_bias = {T: float((sel[f"area|{T}"] - sel["dswx_km2"]).mean()) for T in GRID_T}
    search = [T for T in GRID_T if T != 1000]
    T_best = min(search, key=lambda T: abs(sel_bias[T]))
    at_edge = T_best in (search[0], search[-1])
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(ho), size=(N_BOOT, len(ho)))
    un, wc = summarize(ho, 1000, idx), summarize(ho, T_best, idx)
    d_iou = wc["_boot_iou"] - un["_boot_iou"]
    d_abs = np.abs(wc["_boot_bias"]) - np.abs(un["_boot_bias"])
    adopt = bool(wc["abs_area_bias_km2"] < un["abs_area_bias_km2"] and wc["iou"] >= un["iou"])
    clean = lambda d: {k: v for k, v in d.items() if not k.startswith("_")}
    out = {"rule": "reject predicted water with DEM elevation > water level + T; level = median DEM on the boundary of prob >= 0.9 core",
           "core_probability": wl.CORE_P, "method": m, "probability_threshold": thr,
           "selection_track": sel_track, "heldout_tracks": sorted(ho["track"].unique().tolist()),
           "selection_area_bias_by_T_km2": {str(k): v for k, v in sel_bias.items()},
           "T_chosen_on_selection_m": T_best, "T_at_grid_edge": at_edge, "grid_T_m": search,
           "heldout_unfiltered": clean(un), "heldout_water_level": clean(wc),
           "heldout_paired_differences": {
               "iou_constrained_minus_unfiltered": {"mean": wc["iou"] - un["iou"], "ci95": np.percentile(d_iou, [2.5, 97.5]).tolist()},
               "abs_bias_constrained_minus_unfiltered_km2": {"mean": wc["abs_area_bias_km2"] - un["abs_area_bias_km2"],
                                                             "ci95": np.percentile(d_abs, [2.5, 97.5]).tolist()}},
           "adopted": adopt,
           "adoption_rule": "held-out |area bias| decreases AND held-out IoU does not decrease",
           "n_dates": {"selection": len(sel), "heldout": len(ho)},
           "heldout_by_T_for_information_only": {str(T): {"iou": summarize(ho, T, idx)["iou"],
                                                          "area_bias_km2": float((ho[f'area|{T}'] - ho['dswx_km2']).mean())}
                                                 for T in GRID_T}}
    (OUTPUTS / "water_level_eval.json").write_text(json.dumps(out, indent=2, default=float))
    show = {k: out[k] for k in ("selection_area_bias_by_T_km2", "T_chosen_on_selection_m", "T_at_grid_edge",
                                "heldout_unfiltered", "heldout_water_level", "heldout_paired_differences", "adopted")}
    print(json.dumps(show, indent=1, default=lambda x: round(float(x), 4)))
    lv = pd.read_csv(OUTPUTS / "water_level_per_date.csv")
    print(lv.groupby("track")["level_m"].describe()[["mean", "std", "min", "max"]].round(1))


if __name__ == "__main__":
    main()
