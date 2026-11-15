"""Fine-tuning step 4: evaluate on the HELD-OUT case reservoir (never used in fine-tuning).

Compares the current operational model with the fine-tuned one (outputs/finetune/choice.json), each without
and with the water-level constraint at the T already chosen (water_level_eval.json; not re-tuned).
Dates: all clear, non-outlier dates of the case reservoir (heldout_per_date.csv "use"), all tracks; the
tracks never used for the current model's variant choice are reported separately.
Metrics: pooled IoU / precision / recall and mean area bias (model minus DSWx on DSWx-valid pixels), with
95% bootstrap intervals over dates and paired differences (fine-tuned minus current).
Replacement rule: the fine-tuned model replaces the current one only if, on the held-out reservoir, its
|area bias| is lower AND its IoU is not lower (both without the constraint, the operational setting).
Writes NASA_DATA/outputs/prob_ft_<tag>.tif and outputs/finetune/eval.json
Usage: python finetune/ft_eval.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402

from adabn import load_scene, norm_scene, predict_scene  # noqa: E402
from common import BIG_OUT, MODELS, OUTPUTS  # noqa: E402
from data_s1 import load_stats  # noqa: E402
from evaluate import slug  # noqa: E402
from model import load_model  # noqa: E402
from nisar_prep import write_tif  # noqa: E402
from water_level_eval import per_date_counts, summarize  # noqa: E402

FT_OUT = OUTPUTS / "finetune"
N_BOOT, SEED = 1000, 0


def main() -> None:
    choice = json.loads((FT_OUT / "choice.json").read_text())
    held = json.loads((OUTPUTS / "heldout_eval.json").read_text())
    wl = json.loads((OUTPUTS / "water_level_eval.json").read_text())
    T, thr, op = wl["T_chosen_on_selection_m"], held["probability_threshold"], held["variant_selected_on_selection_track"]
    hp = pd.read_csv(OUTPUTS / "heldout_per_date.csv")
    hp = hp[hp["use"]] if "use" in hp else hp
    scenes = pd.read_csv(OUTPUTS / "nisar_scenes.csv").set_index("tag")
    out = {"held_out_reservoir": held["reservoir"], "T_m": T, "probability_threshold": thr,
           "current_model": op, "finetuned_checkpoint": choice.get("chosen_checkpoint"), "n_dates": len(hp),
           "rule": "replace only if held-out |area bias| is lower AND IoU is not lower (no constraint)"}
    if not choice.get("chosen_checkpoint"):
        out["decision"] = "keep current model: no fine-tuned variant beat the starting model on the validation site"
        (FT_OUT / "eval.json").write_text(json.dumps(out, indent=2, default=float))
        print(out["decision"]); return

    from common import gpu_start
    device = gpu_start(__file__)
    model = load_model(MODELS / choice["chosen_checkpoint"], device)
    s1, mode = load_stats(), choice["input_norm"]
    for tag in hp["tag"]:
        p = BIG_OUT / f"prob_ft_{tag}.tif"
        if p.exists():
            continue
        x, prof = load_scene(scenes.loc[tag].nisar_tif)
        valid = np.all(np.isfinite(x), 0)
        prob, _ = predict_scene(model, norm_scene(x, mode, s1)[0], device)
        prob[~valid] = np.nan
        write_tif(p, prob, prof["crs"].to_epsg(), prof["transform"], np.nan, "float32", ["water_probability"])
    grid = [T, 1000]
    cur = per_date_counts(op, thr, hp, scenes, grid=grid).sort_values("tag").reset_index(drop=True)
    ft = per_date_counts(op, thr, hp, scenes, grid=grid,
                         prob_path=lambda tag: BIG_OUT / f"prob_ft_{tag}.tif").sort_values("tag").reset_index(drop=True)
    assert list(cur["tag"]) == list(ft["tag"])
    rng = np.random.default_rng(SEED)
    clean = lambda d: {k: v for k, v in d.items() if not k.startswith("_")}
    for subset, mask in (("all_tracks", np.ones(len(cur), bool)),
                         ("tracks_not_used_for_current_variant_choice", (cur["track"] != held["selection_track"]).to_numpy())):
        c, f = cur[mask].reset_index(drop=True), ft[mask].reset_index(drop=True)
        idx = rng.integers(0, len(c), size=(N_BOOT, len(c)))
        res = {}
        for name, df, Tk in (("current", c, 1000), ("current_water_level", c, T), ("finetuned", f, 1000), ("finetuned_water_level", f, T)):
            res[name] = summarize(df, Tk, idx)
        diffs = {}
        for a_, b_ in (("finetuned", "current"), ("finetuned_water_level", "current_water_level")):
            diffs[f"{a_}_minus_{b_}"] = {
                "iou": {"mean": res[a_]["iou"] - res[b_]["iou"], "ci95": np.percentile(res[a_]["_boot_iou"] - res[b_]["_boot_iou"], [2.5, 97.5]).tolist()},
                "abs_area_bias_km2": {"mean": res[a_]["abs_area_bias_km2"] - res[b_]["abs_area_bias_km2"],
                                      "ci95": np.percentile(np.abs(res[a_]["_boot_bias"]) - np.abs(res[b_]["_boot_bias"]), [2.5, 97.5]).tolist()}}
        out[subset] = {"n_dates": len(c), "tracks": sorted(c["track"].unique().tolist()),
                       **{k: clean(v) for k, v in res.items()}, "paired": diffs}
    a = out["all_tracks"]
    wins = a["finetuned"]["abs_area_bias_km2"] < a["current"]["abs_area_bias_km2"] and a["finetuned"]["iou"] >= a["current"]["iou"]
    out["replace_current"] = bool(wins)
    out["decision"] = ("fine-tuned model replaces the current one" if wins else
                       "keep current model: fine-tuned model does not lower |area bias| without lowering IoU on the held-out reservoir")
    (FT_OUT / "eval.json").write_text(json.dumps(out, indent=2, default=float))
    for k in ("current", "current_water_level", "finetuned", "finetuned_water_level"):
        r = a[k]
        print(f"{k:24s} IoU {r['iou']:.3f} {np.round(r['ci95']['iou'], 3)}  P {r['precision']:.3f}  R {r['recall']:.3f}  "
              f"bias {r['area_bias_km2']:+.2f} {np.round(r['ci95']['area_bias_km2'], 2)}")
    print(out["decision"])


if __name__ == "__main__":
    main()
