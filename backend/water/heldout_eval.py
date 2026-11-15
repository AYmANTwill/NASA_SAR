"""Held-out NISAR evaluation (headline) + model-minus-DSWx area bias.

Protocol (team rule 2026-11-14):
  - SELECTION set = the main track only (aoi.json "chosen", track 44 ascending for Bin El Ouidane).
    The method variant is chosen there (max pooled IoU), and the area-bias correction is fitted there.
  - HELD-OUT set = every other usable track. Never used for any choice. Its IoU / precision / recall,
    with 95% bootstrap intervals over dates (1000 resamples), is the headline NISAR number.
  - Probability threshold: 0.40, fixed on the Sentinel-1 validation split (thresholds.json); NISAR is
    not used to choose it. Global HV threshold (-23.6 dB) fixed on S1 train.
  - Dates used: DSWx >= 95% valid over SAR-valid pixels, not "partial coverage", not "dswx outlier".
  - AdaBN statistics were re-estimated on all NISAR tiles without labels (transductive, label-free).
  - Area bias = model water area minus DSWx water area on the same DSWx-valid pixels, per date.
    Correction fitted on the selection track only: additive (mean bias) and multiplicative
    (sum DSWx / sum model); both are tested on the held-out tracks.
Writes outputs/heldout_eval.json, outputs/heldout_per_date.csv, appends rows to outputs/results.csv.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from common import OUTPUTS, append_results
from evaluate import method_threshold

N_BOOT = 1000
SEED = 0
MIN_DSWX_VALID = 0.95
UNET = ["U-Net source-only", "U-Net + per-scene norm", "U-Net + AdaBN", "U-Net + AdaBN + per-scene norm"]
# The NISAR fine-tune is a candidate only when a run is active (evaluate.ft_run). v2 on 2026-11-15 won the track-44 selection and
# the held-out IoU (0.934 vs 0.763) but reported +0.50 km2 for the case pair where DSWx gives -1.98 (track-44 bias),
# so the shipped products keep the current variant (finetune/v2/, WATER_UNET.md).
from evaluate import FT_V2, ft_run  # noqa: E402
if ft_run():
    UNET.append(FT_V2)
BASE = ["Otsu (HV dB, per scene)", "Global HV threshold (fit on S1 train VH)"]


def pooled(df, m):
    tp, fp, fn = (df[f"{k}|{m}"].sum() for k in ("tp", "fp", "fn"))
    return tp / max(tp + fp + fn, 1), tp / max(tp + fp, 1), tp / max(tp + fn, 1)


def boot(df, m, rng):
    tp, fp, fn = (df[f"{k}|{m}"].to_numpy(float) for k in ("tp", "fp", "fn"))
    idx = rng.integers(0, len(df), size=(N_BOOT, len(df)))
    T, F, N = tp[idx].sum(1), fp[idx].sum(1), fn[idx].sum(1)
    out = {}
    for k, v in (("iou", T / np.maximum(T + F + N, 1)), ("precision", T / np.maximum(T + F, 1)),
                 ("recall", T / np.maximum(T + N, 1))):
        out[k] = np.percentile(v, [2.5, 97.5]).tolist()
    return out


def mean_ci(x, rng):
    x = np.asarray(x, float)
    b = x[rng.integers(0, len(x), size=(N_BOOT, len(x)))].mean(1)
    return float(x.mean()), np.percentile(b, [2.5, 97.5]).tolist()


def main() -> None:
    rng = np.random.default_rng(SEED)
    chosen = json.loads((OUTPUTS / "aoi.json").read_text())["chosen"]
    res, sel_track = chosen["reservoir"], int(chosen["track"])
    thr = json.loads((OUTPUTS / "thresholds.json").read_text())
    e = pd.read_csv(OUTPUTS / "nisar_eval_per_date.csv")
    from evaluate import ft_train_after
    until = ft_train_after()
    if until:  # site-adapted run: its training dates (after `until`) are never evaluated
        e = e[e["date"].astype(str) <= until]
    c = pd.read_csv(OUTPUTS / "candidate_scenes.csv")
    c = c[(c["reservoir"] == res) & c["usable"]][["date", "track", "dswx_flag"]].rename(columns={"dswx_flag": "cand_flag"})
    assert not c.duplicated(["date", "track"]).any(), "one usable granule per (date, track) expected"
    e = e.merge(c, on=["date", "track"], how="left", validate="one_to_one")
    e["use"] = e["dswx_valid_frac"].ge(MIN_DSWX_VALID) & e["cand_flag"].fillna("").eq("") \
        & e["dswx_flag"].fillna("").eq("")
    e["set"] = np.where(e["track"] == sel_track, "selection", "held-out")
    excluded = e[~e["use"]][["date", "track", "dswx_valid_frac", "cand_flag"]].to_dict("records")
    e = e[e["use"]].copy()
    sel, held = e[e["set"] == "selection"], e[e["set"] == "held-out"]

    # 1. choose the variant on the selection track only
    sel_scores = {m: pooled(sel, m)[0] for m in UNET}
    best = max(sel_scores, key=sel_scores.get)

    # 2. held-out metrics with date-bootstrap intervals
    rows, metrics = [], {}
    for m in BASE + UNET:
        for name, df in (("selection", sel), ("held-out", held)):
            iou, p, r = pooled(df, m)
            ci = boot(df, m, rng)
            metrics.setdefault(m, {})[name] = {"iou": iou, "precision": p, "recall": r, "ci95": ci,
                                               "n_dates": len(df), "tracks": sorted(df["track"].unique().tolist())}
            tag = "HEADLINE held-out" if (name == "held-out" and m == best) else name
            rows.append({"domain": f"NISAR {res} {name} (T{'/T'.join(map(str, sorted(df['track'].unique())))})",
                         "method": m, "iou": iou, "precision": p, "recall": r,
                         "iou_ci95_lo": ci["iou"][0], "iou_ci95_hi": ci["iou"][1],
                         "precision_ci95_lo": ci["precision"][0], "precision_ci95_hi": ci["precision"][1],
                         "recall_ci95_lo": ci["recall"][0], "recall_ci95_hi": ci["recall"][1],
                         "n_pixels": int(df[[f"tp|{m}", f"fp|{m}", f"fn|{m}"]].sum().sum()),
                         "notes": f"{tag}; {len(df)} dates; 95% CI bootstrap over dates; variant chosen on T{sel_track} only; "
                                  f"U-Net p>{method_threshold(m) if m in UNET else thr['unet_probability_threshold']}"})

    # 3. area bias (model minus DSWx on the same DSWx-valid pixels), correction fitted on selection only
    col = f"area_on_dswx_valid_km2|{best}"
    e["bias_km2"] = e[col] - e["dswx_water_km2"]
    sel, held = e[e["set"] == "selection"], e[e["set"] == "held-out"]
    add = float(sel["bias_km2"].mean())
    mult = float(sel["dswx_water_km2"].sum() / sel[col].sum())
    held = held.assign(bias_after_additive=held[col] - add - held["dswx_water_km2"],
                       bias_after_multiplicative=held[col] * mult - held["dswx_water_km2"])
    bias = {"method": best, "definition": "model area minus DSWx area on the same DSWx-valid pixels, per date (km2)"}
    for name, df, colname in (("selection", sel, "bias_km2"), ("held-out raw", held, "bias_km2"),
                              ("held-out after additive correction", held, "bias_after_additive"),
                              ("held-out after multiplicative correction", held, "bias_after_multiplicative")):
        mu, ci = mean_ci(df[colname], rng)
        rel = float((df[colname] / df["dswx_water_km2"]).mean())
        bias[name] = {"mean_km2": mu, "ci95_km2": ci, "mean_relative": rel,
                      "mean_abs_km2": float(df[colname].abs().mean()), "n_dates": len(df)}
    bias["correction_fitted_on_selection"] = {"additive_km2": add, "multiplicative_factor": mult}
    for name in ("additive", "multiplicative"):
        rows.append({"domain": f"NISAR {res} held-out area bias", "method": f"{best}, {name} bias correction (fit on T{sel_track})",
                     "iou": np.nan, "precision": np.nan, "recall": np.nan,
                     "bias_km2": bias[f"held-out after {name} correction"]["mean_km2"],
                     "bias_ci95_lo": bias[f"held-out after {name} correction"]["ci95_km2"][0],
                     "bias_ci95_hi": bias[f"held-out after {name} correction"]["ci95_km2"][1],
                     "notes": "model minus DSWx area per date; bootstrap over dates"})
    rows.append({"domain": f"NISAR {res} held-out area bias", "method": f"{best}, uncorrected",
                 "iou": np.nan, "precision": np.nan, "recall": np.nan,
                 "bias_km2": bias["held-out raw"]["mean_km2"], "bias_ci95_lo": bias["held-out raw"]["ci95_km2"][0],
                 "bias_ci95_hi": bias["held-out raw"]["ci95_km2"][1],
                 "notes": "model minus DSWx area per date; bootstrap over dates"})

    out = {"reservoir": res, "selection_track": sel_track,
           "heldout_tracks": sorted(held["track"].unique().tolist()),
           "variant_selected_on_selection_track": best, "selection_track_iou_by_variant": sel_scores,
           "probability_threshold": method_threshold(best),
           "threshold_source": (f"validation reservoir of the fine-tuning (Al Massira, run {ft_run()})" if best == "U-Net + AdaBN + NISAR fine-tune"
                                else "Sentinel-1 validation split"),
           "evaluation_dates_until": until,
           "headline_heldout": metrics[best]["held-out"], "metrics": metrics, "area_bias": bias,
           "excluded_dates": excluded,
           "notes": ["DSWx-HLS is an optical reference within 5 days, not ground truth.",
                     "AdaBN BatchNorm statistics were re-estimated on all NISAR tiles without labels."]}
    (OUTPUTS / "heldout_eval.json").write_text(json.dumps(out, indent=2, default=float))
    e.to_csv(OUTPUTS / "heldout_per_date.csv", index=False)
    # replace older pooled NISAR rows' label: keep them, but mark them as the selection-contaminated set
    r = pd.read_csv(OUTPUTS / "results.csv")
    pooled_mask = r["domain"].eq(f"NISAR {res}") & r["iou"].notna()
    r.loc[pooled_mask, "notes"] = "SELECTION SET (all tracks pooled; variant chosen on these dates, not independent). " \
        + r.loc[pooled_mask, "notes"].astype(str).str.replace("SELECTION SET (all tracks pooled; variant chosen on these dates, not independent). ", "", regex=False)
    r = r[~r["domain"].astype(str).str.contains("selection|held-out")]
    r.to_csv(OUTPUTS / "results.csv", index=False)
    append_results(rows)

    h = metrics[best]["held-out"]
    print(f"variant chosen on T{sel_track}: {best}  (selection IoU by variant: { {k: round(v, 3) for k, v in sel_scores.items()} })")
    print(f"HEADLINE held-out T{out['heldout_tracks']} ({h['n_dates']} dates): IoU {h['iou']:.3f} {np.round(h['ci95']['iou'], 3)}, "
          f"P {h['precision']:.3f} {np.round(h['ci95']['precision'], 3)}, R {h['recall']:.3f} {np.round(h['ci95']['recall'], 3)}")
    for m in BASE + UNET:
        hh = metrics[m]["held-out"]
        print(f"  held-out {m:45s} IoU {hh['iou']:.3f} [{hh['ci95']['iou'][0]:.3f},{hh['ci95']['iou'][1]:.3f}]")
    print(json.dumps(bias, indent=1, default=float))
    print("excluded:", excluded)


if __name__ == "__main__":
    main()
