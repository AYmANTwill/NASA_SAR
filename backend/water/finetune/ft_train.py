"""Fine-tuning step 3: fine-tune the operational model on NISAR with DSWx labels (site split).

- start: the operational checkpoint (heldout_eval.json variant -> evaluate.METHODS), same input normalisation
- BatchNorm running statistics frozen (keeps the AdaBN NISAR statistics); dropout active; AdamW lr 2e-5
- augmentation: flips + rot90; random 256 crops, half of them centred on DSWx water
- labels: DSWx 1/0, 255 ignored; loss = masked BCE + soft Dice (train.masked_loss)
- variants: "nisar" (NISAR batches only) and "mix" (each batch half NISAR, half Sentinel-1 chips)
- validation site (fixed before training: VAL_SITE) -> early stopping on pooled IoU at the operational
  probability threshold; the held-out case reservoir is never read here
v2 options (--run v2): variants "name:lambda" add lambda * soft area term (|sum p - sum y| / valid pixels, per crop)
to the loss; the kept epoch is the best validation IoU among epochs whose |area bias| <= BIAS_TOL of the
validation DSWx water area (fallback before any epoch qualifies: best IoU); the probability threshold is then
re-chosen on the validation site (grid THR_GRID, minimum |area bias|). Outputs go to outputs/finetune/<run>/ and
NASA_DATA/models/unet_ft_<run>_<variant>.pt (the v1 files are not touched).
Writes NASA_DATA/models/unet_ft_<variant>.pt, outputs/finetune/train_log_<variant>.csv, outputs/finetune/choice.json
Usage: python finetune/ft_train.py [--variants nisar mix] [--epochs 25] [--iters 150]
       python finetune/ft_train.py --run v2 --variants base:0 area:5
v3: a variant "name:lambda:inc" adds the incidence angle as a 3rd input channel ((deg - INC_MEAN) / INC_STD;
first-layer weights of the new channel start at zero, so training starts from the 2-channel model's predictions);
--test-sites removes reservoirs from training and validation (fixed before training, reported separately).
       python finetune/ft_train.py --run v3 --variants noinc:0 inc:0:inc --test-sites Oued_El_Makhazine
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import rasterio  # noqa: E402
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402

from adabn import norm_scene, predict_scene  # noqa: E402
from common import MODELS, OUTPUTS, dpath  # noqa: E402
from data_s1 import IGNORE, S1Dataset, load_stats  # noqa: E402
from evaluate import METHODS  # noqa: E402
from model import load_model  # noqa: E402
from train import masked_loss  # noqa: E402

FT_BASE = OUTPUTS / "finetune"
FT_OUT = FT_BASE  # FT_BASE / <run> when --run is given (set in main)
THR_GRID = np.round(np.arange(0.20, 0.701, 0.05), 2)
BIAS_TOL = 0.05  # |val area bias| <= 5% of the validation DSWx water area
VAL_SITE = "Al_Massira"  # chosen before training (one of the two other case candidates)
CROP = 256
INC_MEAN, INC_STD = 40.0, 5.0  # incidence-angle channel scaling (degrees)


def inc_channel(path, window=None) -> np.ndarray:
    with rasterio.open(dpath(path)) as s:
        a = s.read(1, window=window).astype(np.float32)
    return np.nan_to_num((a - INC_MEAN) / INC_STD, nan=0.0)[None]


class NisarCrops(torch.utils.data.Dataset):
    """Random 256 crops read on demand from the LOCAL GeoTIFF cache (windowed reads), so DataLoader workers
    stay light. Half the crops are centred on DSWx water. Augmentation: flips + rot90. Labels 255 = ignore."""

    def __init__(self, rows: pd.DataFrame, mode: str, s1: dict, length: int, max_water_pts: int = 20000, inc: bool = False):
        from adabn import scene_stats

        self.scenes, self.length, self.inc = [], length, inc
        rng = np.random.default_rng(0)
        for _, r in rows.iterrows():
            xp, yp = str(dpath(r["nisar_tif"])), str(dpath(r["label_tif"]))
            with rasterio.open(xp) as s:
                x = s.read().astype(np.float32)
            with rasterio.open(yp) as s:
                y = s.read(1)
            valid = np.all(np.isfinite(x), 0)
            y = np.where(valid, y, IGNORE)
            if (y != IGNORE).mean() < 0.5 or min(y.shape) < CROP:
                continue
            mean, std = scene_stats(x) if mode == "scene" else (s1["mean_db"], s1["std_db"])
            water = np.argwhere(y == 1).astype(np.int32)
            if len(water) > max_water_pts:
                water = water[rng.choice(len(water), max_water_pts, replace=False)]
            self.scenes.append({"x": xp, "y": yp, "shape": y.shape, "mean": list(map(float, mean)),
                                "std": list(map(float, std)), "water": water,
                                "inc": r["inc_tif"] if inc else None})

    def __len__(self):
        return self.length

    def __getitem__(self, i):
        from rasterio.windows import Window

        from data_s1 import normalize

        rng = np.random.default_rng((torch.initial_seed() + i) % 2**32)
        sc = self.scenes[rng.integers(len(self.scenes))]
        h, w = sc["shape"]
        if len(sc["water"]) and rng.random() < 0.5:
            cy, cx = sc["water"][rng.integers(len(sc["water"]))]
            r0 = int(np.clip(cy - CROP // 2 + rng.integers(-64, 65), 0, h - CROP))
            c0 = int(np.clip(cx - CROP // 2 + rng.integers(-64, 65), 0, w - CROP))
        else:
            r0, c0 = int(rng.integers(0, h - CROP + 1)), int(rng.integers(0, w - CROP + 1))
        win = Window(c0, r0, CROP, CROP)
        with rasterio.open(sc["x"]) as s:
            x = s.read(window=win).astype(np.float32)
        with rasterio.open(sc["y"]) as s:
            y = s.read(1, window=win)
        a, valid = normalize(x, sc["mean"], sc["std"])
        if sc["inc"] is not None:
            a = np.concatenate([a, inc_channel(sc["inc"], win)]).astype(np.float32)
        b = np.where(valid, y, IGNORE).astype(np.uint8)
        if rng.random() < 0.5:
            a, b = a[:, :, ::-1], b[:, ::-1]
        if rng.random() < 0.5:
            a, b = a[:, ::-1], b[::-1]
        k = int(rng.integers(4))
        return torch.from_numpy(np.rot90(a, k, (1, 2)).copy()), torch.from_numpy(np.rot90(b, k).copy())


def loader(ds, bs, workers):
    return torch.utils.data.DataLoader(ds, batch_size=bs, shuffle=False, num_workers=workers, pin_memory=True,
                                       persistent_workers=workers > 0, drop_last=True)


def freeze_bn(m: nn.Module) -> None:
    for mod in m.modules():
        if isinstance(mod, nn.modules.batchnorm._BatchNorm):
            mod.eval()
            for p in mod.parameters():
                p.requires_grad_(False)


def area_term(logits, target):
    """Mean over crops of |soft predicted water - label water| / valid pixels."""
    v = (target != IGNORE).float()
    p = torch.sigmoid(logits[:, 0]) * v
    y = (target == 1).float() * v
    return ((p.sum((1, 2)) - y.sum((1, 2))).abs() / v.sum((1, 2)).clamp_min(1)).mean()


@torch.no_grad()
def validate_grid(model, val_rows, mode, s1, device, grid=THR_GRID):
    inc = getattr(model, "in_channels", 2) == 3
    """Pooled IoU and mean area bias (km2) at every threshold of the grid, plus the mean DSWx water area."""
    tp, fp, fn = (np.zeros(len(grid)) for _ in range(3))
    bias, water = [], []
    for _, r in val_rows.iterrows():
        with rasterio.open(dpath(r["nisar_tif"])) as s:
            x, tr = s.read().astype(np.float32), s.transform
        with rasterio.open(dpath(r["label_tif"])) as s:
            y = s.read(1)
        xn, valid = norm_scene(x, mode, s1)
        if inc:
            xn = np.concatenate([xn, inc_channel(r["inc_tif"])]).astype(np.float32)
        prob, _ = predict_scene(model, xn, device)
        v = valid & (y != IGNORE)
        px = abs(tr.a * tr.e) / 1e6
        pv, tv = prob[v], (y == 1)[v]
        b = []
        for k, thr in enumerate(grid):
            p = pv >= thr
            tp[k] += int((p & tv).sum()); fp[k] += int((p & ~tv).sum()); fn[k] += int((~p & tv).sum())
            b.append((int(p.sum()) - int(tv.sum())) * px)
        bias.append(b); water.append(int(tv.sum()) * px)
    model.eval()
    return {"thr": [float(g) for g in grid], "iou": (tp / np.maximum(tp + fp + fn, 1)).tolist(),
            "bias": np.mean(bias, 0).tolist(), "water_km2": float(np.mean(water))}


def at(g, thr):
    k = int(np.argmin(np.abs(np.array(g["thr"]) - thr)))
    return g["iou"][k], g["bias"][k]


def validate(model, val_rows, mode, s1, thr, device):
    return at(validate_grid(model, val_rows, mode, s1, device, grid=[thr]), thr)


def run_variant(variant, train_rows, val_rows, a, device, base_ck, mode, s1, thr, lam=0.0, run="", inc=False):
    from model import widen_input

    torch.manual_seed(0)
    model = load_model(MODELS / base_ck, device)
    if inc:
        model = widen_input(model)
    g0 = validate_grid(model, val_rows, mode, s1, device, grid=sorted(set(THR_GRID.tolist()) | {thr}))
    base_iou, base_bias = at(g0, thr)
    tol = BIAS_TOL * g0["water_km2"]
    print(f"[{variant}] start: val IoU {base_iou:.4f}, val area bias {base_bias:+.3f} km2", flush=True)
    n_bs = a.bs // 2 if variant.startswith("mix") else a.bs
    nis = NisarCrops(train_rows, mode, s1, length=a.iters * n_bs, inc=inc)
    nis_dl = loader(nis, n_bs, a.workers)
    s1_dl = None
    if variant.startswith("mix"):
        s1_ds = S1Dataset("train", s1, augment=True, crop=CROP)
        s1_dl = torch.utils.data.DataLoader(s1_ds, batch_size=a.bs - n_bs, shuffle=True, num_workers=a.workers,
                                            pin_memory=True, persistent_workers=a.workers > 0, drop_last=True)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr, weight_decay=1e-4)
    scaler = torch.amp.GradScaler(enabled=device.type == "cuda")
    log, best, bad = [{"epoch": 0, "train_loss": None, "val_iou": base_iou, "val_area_bias_km2": base_bias, "sec": 0}], base_iou, 0
    ck_path = MODELS / (f"unet_ft_{run}_{variant}.pt" if run else f"unet_ft_{variant}.pt")
    best_ok, best_grid = -1.0, None  # v2: best IoU among epochs within the bias tolerance; grid of the kept epoch
    ck = torch.load(MODELS / base_ck, map_location="cpu", weights_only=False)
    for ep in range(1, a.epochs + 1):
        model.train(); freeze_bn(model)
        t0, losses = time.time(), []
        s1_iter = iter(s1_dl) if s1_dl is not None else None
        for xn, yn in nis_dl:
            if s1_iter is not None:
                try:
                    xs, ys = next(s1_iter)
                except StopIteration:
                    s1_iter = iter(s1_dl); xs, ys = next(s1_iter)
                xn, yn = torch.cat([xn, xs]), torch.cat([yn, ys])
            x, y = xn.to(device, non_blocking=True), yn.to(device, non_blocking=True)
            opt.zero_grad(set_to_none=True)
            with torch.autocast(device.type, enabled=device.type == "cuda"):
                lg = model(x)
            loss = masked_loss(lg.float(), y)
            if lam:
                loss = loss + lam * area_term(lg.float(), y)
            scaler.scale(loss).backward(); scaler.step(opt); scaler.update()
            losses.append(loss.item())
        g = validate_grid(model, val_rows, mode, s1, device, grid=sorted(set(THR_GRID.tolist()) | {thr}))
        iou, bias = at(g, thr)
        log.append({"epoch": ep, "train_loss": float(np.mean(losses)), "val_iou": iou, "val_area_bias_km2": bias,
                    "within_bias_tol": abs(bias) <= tol, "sec": round(time.time() - t0)})
        pd.DataFrame(log).to_csv(FT_OUT / f"train_log_{variant}.csv", index=False)
        flag = ""
        # v1: keep the best IoU. v2: keep the best IoU within the bias tolerance (best IoU until one qualifies).
        keep = iou > best if not run else ((abs(bias) <= tol and iou > best_ok) or (best_ok < 0 and iou > best))
        if iou > best:
            best, bad = iou, 0
        else:
            bad += 1
        if keep:
            flag = " *kept"
            if run and abs(bias) <= tol:
                best_ok = iou
            best_grid = {**g, "epoch": ep}
            torch.save({**ck, "state_dict": model.state_dict(), "in_channels": model.in_channels, "finetune": {
                "variant": variant, "run": run, "area_weight": lam, "incidence_input": inc, "epoch": ep, "val_site": VAL_SITE,
                "val_iou": iou, "val_area_bias_km2": bias, "train_sites": sorted(train_rows["site"].unique().tolist()),
                "n_train_scenes": len(nis.scenes), "lr": a.lr, "bn": "frozen (AdaBN NISAR statistics)",
                "base_checkpoint": base_ck}}, ck_path)
        print(f"[{variant}] ep {ep:2d} loss {np.mean(losses):.4f} val IoU {iou:.4f} bias {bias:+.3f} ({log[-1]['sec']}s){flag}", flush=True)
        if bad >= a.patience:
            break
    if not run:
        return {"variant": variant, "best_val_iou": best, "start_val_iou": base_iou, "start_val_area_bias_km2": base_bias,
                "improved": best > base_iou, "checkpoint": ck_path.name if best > base_iou else None,
                "best_epoch": int(pd.DataFrame(log).iloc[1:]["val_iou"].idxmax()) if len(log) > 1 else 0}
    res = {"variant": variant, "area_weight": lam, "incidence_input": inc, "start_val_iou": base_iou, "start_val_area_bias_km2": base_bias,
           "val_water_km2": g0["water_km2"], "bias_tolerance_km2": tol, "improved": False, "checkpoint": None}
    if best_grid is None:
        print(f"[{variant}] no epoch beat the start", flush=True)
        return res
    kept_iou, kept_bias = at(best_grid, thr)
    # threshold re-chosen on the validation site for the kept epoch: minimum |area bias|, ties -> higher IoU
    k = min(range(len(best_grid["thr"])), key=lambda i: (round(abs(best_grid["bias"][i]), 3), -best_grid["iou"][i]))
    res.update({"kept_epoch": best_grid["epoch"], "kept_within_bias_tol": best_ok >= 0,
                "kept_val_iou": kept_iou, "kept_val_area_bias_km2": kept_bias,
                "val_threshold": best_grid["thr"][k], "val_iou_at_val_threshold": best_grid["iou"][k],
                "val_bias_at_val_threshold": best_grid["bias"][k], "val_grid": best_grid,
                "improved": kept_iou > base_iou})
    res["checkpoint"] = ck_path.name if res["improved"] else None
    print(f"[{variant}] kept epoch {res['kept_epoch']} (within tol {tol:.2f} km2: {res['kept_within_bias_tol']}); "
          f"val thr {res['val_threshold']}: IoU {res['val_iou_at_val_threshold']:.4f} bias {res['val_bias_at_val_threshold']:+.3f}",
          flush=True)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", nargs="+", default=["nisar", "mix"])
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--iters", type=int, default=150)
    ap.add_argument("--bs", type=int, default=8)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--patience", type=int, default=5)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--run", default="", help="run name (e.g. v2): outputs in outputs/finetune/<run>/")
    ap.add_argument("--test-sites", nargs="*", default=[], help="reservoirs kept out of training and validation")
    ap.add_argument("--case-after", default="", help="v3site: also train on case-reservoir dates strictly after this date")
    a = ap.parse_args()
    global FT_OUT
    FT_OUT = FT_BASE / a.run if a.run else FT_BASE
    FT_OUT.mkdir(parents=True, exist_ok=True)
    from common import gpu_start
    device = gpu_start(__file__)
    held = json.loads((OUTPUTS / "heldout_eval.json").read_text())
    op = held["variant_selected_on_selection_track"]
    base_ck, mode = METHODS[op]
    thr = held["probability_threshold"]
    s1 = load_stats()
    ds = pd.read_csv(FT_BASE / "dataset.csv")
    held_res = json.loads((FT_BASE / "sites.json").read_text())["held_out"]
    assert not ds["site"].eq(held_res).any(), "held-out reservoir must not be in the fine-tuning data"
    if (FT_BASE / "incidence.csv").exists():
        inc = pd.read_csv(FT_BASE / "incidence.csv")
        inc = inc[inc["error"].isna()] if "error" in inc else inc
        ds = ds.merge(inc[["tag", "inc_tif"]], on="tag", how="left")
    ds = ds[~ds["site"].isin(a.test_sites)]
    val_rows, train_rows = ds[ds["site"] == VAL_SITE], ds[ds["site"] != VAL_SITE]
    if a.case_after:
        # site adaptation (v3site): add the case reservoir's own clear dates STRICTLY AFTER a.case_after, with their
        # DSWx labels; every date up to a.case_after (the displayed case period) stays out of training.
        hp = pd.read_csv(OUTPUTS / "heldout_per_date.csv")
        hp = hp[hp["use"]] if "use" in hp else hp
        ns = pd.read_csv(OUTPUTS / "nisar_scenes.csv")
        cr = ns[ns["tag"].isin(hp["tag"]) & (ns["date"] > a.case_after)].rename(columns={"dswx_tif": "label_tif"})
        cr = cr.assign(site=held_res).merge(inc[["tag", "inc_tif"]], on="tag", how="left") if "inc" in dir() else cr.assign(site=held_res)
        assert (cr["date"] > a.case_after).all() and len(cr), "no case-reservoir dates after the case period"
        train_rows = pd.concat([train_rows, cr[["tag", "site", "track", "date", "nisar_tif", "label_tif"]
                                               + (["inc_tif"] if "inc_tif" in cr else [])]], ignore_index=True)
        print(f"site adaptation: + {len(cr)} {held_res} dates after {a.case_after}: {sorted(cr['date'].unique())}", flush=True)
    print(f"train sites {sorted(train_rows['site'].unique())} ({len(train_rows)} scenes); val {VAL_SITE} ({len(val_rows)} scenes); "
          f"base {base_ck} ({op}), norm {mode}, thr {thr}", flush=True)
    specs = [(v.split(":")[0], float(v.split(":")[1]) if ":" in v else 0.0, v.endswith(":inc")) for v in a.variants]
    if any(i for *_, i in specs):
        need = pd.concat([train_rows, val_rows])
        assert "inc_tif" in need and need["inc_tif"].notna().all(), "run finetune/ft_incidence.py first"
    res = [run_variant(v, train_rows, val_rows, a, device, base_ck, mode, s1, thr, lam, a.run, inc) for v, lam, inc in specs]
    winners = [r for r in res if r["improved"]]
    if a.run:
        choice = min(winners, key=lambda r: (not r["kept_within_bias_tol"], abs(r["val_bias_at_val_threshold"]),
                                             -r["val_iou_at_val_threshold"])) if winners else None
        rule = ("among variants that beat the start on the validation site: prefer a kept epoch within the bias "
                "tolerance, then the lowest |area bias| at the validation-chosen threshold, then the highest IoU")
    else:
        choice = max(winners, key=lambda r: r["best_val_iou"]) if winners else None
        rule = "variant with the highest validation-site IoU; must beat the starting checkpoint on the validation site"
    (FT_OUT / "choice.json").write_text(json.dumps({
        "rule": rule, "run": a.run, "n_train_scenes": int(len(train_rows)), "n_val_scenes": int(len(val_rows)),
        "test_sites": a.test_sites,
        "case_dates_in_training_after": a.case_after or None,
        "chosen_threshold": (choice.get("val_threshold", thr) if choice else None),
        "val_site": VAL_SITE, "train_sites": sorted(train_rows["site"].unique().tolist()),
        "base_method": op, "base_checkpoint": base_ck, "input_norm": mode, "probability_threshold": thr,
        "variants": res, "chosen": choice["variant"] if choice else None,
        "chosen_checkpoint": choice["checkpoint"] if choice else None}, indent=2, default=float))
    print("chosen:", choice["variant"] if choice else "none (no variant beat the starting model on the validation site)")


if __name__ == "__main__":
    main()
