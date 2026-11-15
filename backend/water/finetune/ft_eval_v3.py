"""v3 evaluation: current model vs v2 vs v3 on
  (a) the v3 TEST reservoir(s) (choice.json "test_sites"; never used to train or choose v3; v2 saw them in training),
  (b) the case reservoir Bin El Ouidane (all clear dates; NOT a clean test for v3: v3 was designed after v2's
      track-44 bias there was seen) and its case pair (outputs/case_pair.json) water-area change vs DSWx.
Pooled IoU / precision / recall, mean area bias (model minus DSWx on DSWx-valid pixels) with 95% bootstrap intervals
over dates, per-track bias, and paired differences vs the current model.
Writes outputs/finetune/v3/eval.json
Usage: python finetune/ft_eval_v3.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import rasterio  # noqa: E402

from adabn import norm_scene, predict_scene  # noqa: E402
from common import MODELS, OUTPUTS, dpath  # noqa: E402
from data_s1 import IGNORE, load_stats  # noqa: E402
from ft_train import inc_channel  # noqa: E402
from model import load_model  # noqa: E402

FT = OUTPUTS / "finetune"
N_BOOT, SEED = 1000, 0


def models() -> dict:
    held = json.loads((OUTPUTS / "heldout_eval.json").read_text())
    v2 = json.loads((FT / "v2" / "choice.json").read_text())
    v3 = json.loads((FT / "v3" / "choice.json").read_text())
    out = {"current": ("unet_s1_adabn_s1norm.pt", held["probability_threshold"]),
           "v2": (v2["chosen_checkpoint"], v2["chosen_threshold"])}
    for run in ("v3", "v3noinc", "v3site"):
        f = FT / run / "choice.json"
        if f.exists():
            for v in json.loads(f.read_text())["variants"]:
                if v.get("checkpoint"):
                    out[f"{run}_{v['variant']}"] = (v["checkpoint"], v["val_threshold"])
    return out, v3


def scene_rows() -> tuple[pd.DataFrame, pd.DataFrame]:
    inc = pd.read_csv(FT / "incidence.csv")
    inc = inc[inc["error"].isna()] if "error" in inc else inc
    ds = pd.read_csv(FT / "dataset.csv").merge(inc[["tag", "inc_tif"]], on="tag", how="left")
    hp = pd.read_csv(OUTPUTS / "heldout_per_date.csv")
    hp = hp[hp["use"]] if "use" in hp else hp
    ns = pd.read_csv(OUTPUTS / "nisar_scenes.csv")
    case = ns[ns["tag"].isin(hp["tag"])].rename(columns={"dswx_tif": "label_tif"}).merge(inc[["tag", "inc_tif"]], on="tag", how="left")
    case["site"] = json.loads((OUTPUTS / "aoi.json").read_text())["chosen"]["reservoir"]
    return ds, case


def per_date(rows: pd.DataFrame, ck: str, thr: float, s1, device) -> pd.DataFrame:
    model = load_model(MODELS / ck, device)
    inc = getattr(model, "in_channels", 2) == 3
    out = []
    for r in rows.itertuples():
        with rasterio.open(dpath(r.nisar_tif)) as s:
            x, tr = s.read().astype(np.float32), s.transform
        with rasterio.open(dpath(r.label_tif)) as s:
            y = s.read(1)
        xn, valid = norm_scene(x, "s1", s1)
        if inc:
            xn = np.concatenate([xn, inc_channel(r.inc_tif)]).astype(np.float32)
        prob, _ = predict_scene(model, xn, device)
        v = valid & (y != IGNORE) & (y != 255)
        p, t = (prob >= thr) & v, (y == 1) & v
        px = abs(tr.a * tr.e) / 1e6
        out.append({"tag": r.tag, "date": r.date, "track": int(r.track), "tp": int((p & t).sum()), "fp": int((p & ~t).sum()),
                    "fn": int((~p & t).sum()), "model_km2": int(p.sum()) * px, "dswx_km2": int(t.sum()) * px})
    d = pd.DataFrame(out)
    d["bias_km2"] = d["model_km2"] - d["dswx_km2"]
    return d


def summary(d: pd.DataFrame, idx: np.ndarray) -> dict:
    def pooled(g):
        s = g[["tp", "fp", "fn"]].sum()
        return s.tp / max(s.tp + s.fp + s.fn, 1), s.tp / max(s.tp + s.fp, 1), s.tp / max(s.tp + s.fn, 1)
    iou, p, r = pooled(d)
    tp, fp, fn, b = (d[c].to_numpy() for c in ("tp", "fp", "fn", "bias_km2"))
    biou = tp[idx].sum(1) / np.maximum((tp[idx] + fp[idx] + fn[idx]).sum(1), 1)
    bb = b[idx].mean(1)
    return {"n_dates": len(d), "iou": iou, "precision": p, "recall": r, "area_bias_km2": float(b.mean()),
            "ci95": {"iou": np.percentile(biou, [2.5, 97.5]).tolist(), "area_bias_km2": np.percentile(bb, [2.5, 97.5]).tolist()},
            "per_track_bias_km2": {int(k): round(float(v), 3) for k, v in d.groupby("track")["bias_km2"].mean().items()},
            "_boot_iou": biou, "_boot_bias": bb}


def main() -> None:
    from common import gpu_start
    device = gpu_start(__file__)
    s1 = load_stats()
    ms, v3 = models()
    ds, case = scene_rows()
    sets = {f"test:{s}": ds[ds["site"] == s] for s in v3.get("test_sites", [])}
    sets["case_reservoir"] = case
    # the case period only (no date of it is in any training set, including v3site's)
    sets["case_reservoir_case_period"] = case[case["date"] <= json.loads((OUTPUTS / "case_pair.json").read_text())["post"]]
    pair = json.loads((OUTPUTS / "case_pair.json").read_text())
    sel_track = int(json.loads((OUTPUTS / "aoi.json").read_text())["chosen"]["track"])
    rng = np.random.default_rng(SEED)
    out = {"models": {k: {"checkpoint": c, "threshold": t} for k, (c, t) in ms.items()},
           "note": ("v2 was trained with the v3 test reservoir(s); the case reservoir is not a clean test for v3 "
                    "(v3 was designed after v2's track-44 bias there was seen)"), "sets": {}}
    for name, rows in sets.items():
        rows = rows[rows["inc_tif"].notna()]
        idx = rng.integers(0, len(rows), size=(N_BOOT, len(rows)))
        res, dd = {}, {}
        for k, (ck, thr) in ms.items():
            dd[k] = per_date(rows, ck, thr, s1, device).sort_values("tag").reset_index(drop=True)
            res[k] = summary(dd[k], idx)
        for k in ms:
            if k != "current":
                res[k]["paired_vs_current"] = {
                    "iou": np.percentile(res[k]["_boot_iou"] - res["current"]["_boot_iou"], [2.5, 97.5]).tolist(),
                    "abs_bias": np.percentile(np.abs(res[k]["_boot_bias"]) - np.abs(res["current"]["_boot_bias"]), [2.5, 97.5]).tolist()}
        if name.startswith("case_reservoir"):
            for k, d in dd.items():  # multi-track change (reservoir_case.py rule: nearest pass within ±5 d per track)
                d2 = d.assign(dt=pd.to_datetime(d["date"]))
                ch = []
                for trk, g in d2.groupby("track"):
                    a_ = g[(g["dt"] - pd.Timestamp(pair["pre"])).abs() <= pd.Timedelta(days=5)]
                    b_ = g[(g["dt"] - pd.Timestamp(pair["post"])).abs() <= pd.Timedelta(days=5)]
                    if len(a_) and len(b_):
                        a_ = a_.loc[(a_["dt"] - pd.Timestamp(pair["pre"])).abs().idxmin()]
                        b_ = b_.loc[(b_["dt"] - pd.Timestamp(pair["post"])).abs().idxmin()]
                        ch.append((int(trk), b_["model_km2"] - a_["model_km2"], b_["dswx_km2"] - a_["dswx_km2"]))
                if len(ch) >= 2:
                    c = np.array([x[1] for x in ch]); dw = np.array([x[2] for x in ch])
                    res[k]["multitrack_change_km2"] = {"model": float(c.mean()), "model_se": float(c.std(ddof=1) / np.sqrt(len(c))),
                                                       "dswx": float(dw.mean()), "per_track": ch,
                                                       "abs_error_vs_dswx": float(abs(c.mean() - dw.mean()))}
            for k, d in dd.items():
                g = d[d["track"] == sel_track].set_index("date")
                if pair["pre"] in g.index and pair["post"] in g.index:
                    res[k]["case_pair_change_km2"] = {"model": float(g.loc[pair["post"], "model_km2"] - g.loc[pair["pre"], "model_km2"]),
                                                      "dswx": float(g.loc[pair["post"], "dswx_km2"] - g.loc[pair["pre"], "dswx_km2"])}
        out["sets"][name] = {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")} for k, v in res.items()}
        print(f"== {name} ({len(rows)} dates)")
        for k, r in res.items():
            cp = r.get("case_pair_change_km2")
            print(f"  {k:10s} IoU {r['iou']:.3f} {np.round(r['ci95']['iou'], 3)}  bias {r['area_bias_km2']:+.2f} "
                  f"{np.round(r['ci95']['area_bias_km2'], 2)}  per-track {r['per_track_bias_km2']}"
                  + (f"  case pair {cp['model']:+.2f} vs DSWx {cp['dswx']:+.2f}" if cp else "")
                  + (f"  3-track {r['multitrack_change_km2']['model']:+.2f} ± {r['multitrack_change_km2']['model_se']:.2f} vs DSWx "
                     f"{r['multitrack_change_km2']['dswx']:+.2f}" if "multitrack_change_km2" in r else ""), flush=True)
    (FT / "v3" / "eval.json").write_text(json.dumps(out, indent=2, default=float))


if __name__ == "__main__":
    main()
