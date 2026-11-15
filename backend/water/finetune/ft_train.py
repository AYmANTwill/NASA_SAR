"""Fine-tuning step 3: fine-tune the operational model on NISAR with DSWx labels (site split).

- start: the operational checkpoint (heldout_eval.json variant -> evaluate.METHODS), same input normalisation
- BatchNorm running statistics frozen (keeps the AdaBN NISAR statistics); dropout active; AdamW lr 2e-5
- augmentation: flips + rot90; random 256 crops, half of them centred on DSWx water
- labels: DSWx 1/0, 255 ignored; loss = masked BCE + soft Dice (train.masked_loss)
- variants: "nisar" (NISAR batches only) and "mix" (each batch half NISAR, half Sentinel-1 chips)
- validation site (fixed before training: VAL_SITE) -> early stopping on pooled IoU at the operational
  probability threshold; the held-out case reservoir is never read here
Writes NASA_DATA/models/unet_ft_<variant>.pt, outputs/finetune/train_log_<variant>.csv, outputs/finetune/choice.json
Usage: python finetune/ft_train.py [--variants nisar mix] [--epochs 25] [--iters 150]
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

FT_OUT = OUTPUTS / "finetune"
VAL_SITE = "Al_Massira"  # chosen before training (one of the two other case candidates)
CROP = 256


class NisarCrops(torch.utils.data.Dataset):
    """Random 256 crops read on demand from the LOCAL GeoTIFF cache (windowed reads), so DataLoader workers
    stay light. Half the crops are centred on DSWx water. Augmentation: flips + rot90. Labels 255 = ignore."""

    def __init__(self, rows: pd.DataFrame, mode: str, s1: dict, length: int, max_water_pts: int = 20000):
        from adabn import scene_stats

        self.scenes, self.length = [], length
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
                                "std": list(map(float, std)), "water": water})

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


@torch.no_grad()
def validate(model, val_rows, mode, s1, thr, device):
    tp = fp = fn = 0
    bias = []
    for _, r in val_rows.iterrows():
        with rasterio.open(dpath(r["nisar_tif"])) as s:
            x, tr = s.read().astype(np.float32), s.transform
        with rasterio.open(dpath(r["label_tif"])) as s:
            y = s.read(1)
        xn, valid = norm_scene(x, mode, s1)
        prob, _ = predict_scene(model, xn, device)
        v = valid & (y != IGNORE)
        p, t = (prob >= thr) & v, (y == 1) & v
        tp += int((p & t).sum()); fp += int((p & ~t).sum()); fn += int((~p & t).sum())
        bias.append((p.sum() - t.sum()) * abs(tr.a * tr.e) / 1e6)
    model.eval()
    return tp / max(tp + fp + fn, 1), float(np.mean(bias))


def run_variant(variant, train_rows, val_rows, a, device, base_ck, mode, s1, thr):
    torch.manual_seed(0)
    model = load_model(MODELS / base_ck, device)
    base_iou, base_bias = validate(model, val_rows, mode, s1, thr, device)
    print(f"[{variant}] start: val IoU {base_iou:.4f}, val area bias {base_bias:+.3f} km2", flush=True)
    n_bs = a.bs // 2 if variant == "mix" else a.bs
    nis = NisarCrops(train_rows, mode, s1, length=a.iters * n_bs)
    nis_dl = loader(nis, n_bs, a.workers)
    s1_dl = None
    if variant == "mix":
        s1_ds = S1Dataset("train", s1, augment=True, crop=CROP)
        s1_dl = torch.utils.data.DataLoader(s1_ds, batch_size=a.bs - n_bs, shuffle=True, num_workers=a.workers,
                                            pin_memory=True, persistent_workers=a.workers > 0, drop_last=True)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr, weight_decay=1e-4)
    scaler = torch.amp.GradScaler(enabled=device.type == "cuda")
    log, best, bad = [{"epoch": 0, "train_loss": None, "val_iou": base_iou, "val_area_bias_km2": base_bias, "sec": 0}], base_iou, 0
    ck_path = MODELS / f"unet_ft_{variant}.pt"
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
            scaler.scale(loss).backward(); scaler.step(opt); scaler.update()
            losses.append(loss.item())
        iou, bias = validate(model, val_rows, mode, s1, thr, device)
        log.append({"epoch": ep, "train_loss": float(np.mean(losses)), "val_iou": iou, "val_area_bias_km2": bias,
                    "sec": round(time.time() - t0)})
        pd.DataFrame(log).to_csv(FT_OUT / f"train_log_{variant}.csv", index=False)
        flag = ""
        if iou > best:
            best, bad, flag = iou, 0, " *best"
            torch.save({**ck, "state_dict": model.state_dict(), "finetune": {
                "variant": variant, "epoch": ep, "val_site": VAL_SITE, "val_iou": iou, "val_area_bias_km2": bias,
                "train_sites": sorted(train_rows["site"].unique().tolist()), "n_train_scenes": len(nis.scenes),
                "lr": a.lr, "bn": "frozen (AdaBN NISAR statistics)", "base_checkpoint": base_ck}}, ck_path)
        else:
            bad += 1
        print(f"[{variant}] ep {ep:2d} loss {np.mean(losses):.4f} val IoU {iou:.4f} bias {bias:+.3f} ({log[-1]['sec']}s){flag}", flush=True)
        if bad >= a.patience:
            break
    return {"variant": variant, "best_val_iou": best, "start_val_iou": base_iou, "start_val_area_bias_km2": base_bias,
            "improved": best > base_iou, "checkpoint": ck_path.name if best > base_iou else None,
            "best_epoch": int(pd.DataFrame(log).iloc[1:]["val_iou"].idxmax()) if len(log) > 1 else 0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", nargs="+", default=["nisar", "mix"])
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--iters", type=int, default=150)
    ap.add_argument("--bs", type=int, default=8)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--patience", type=int, default=5)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    from common import gpu_start
    device = gpu_start(__file__)
    held = json.loads((OUTPUTS / "heldout_eval.json").read_text())
    op = held["variant_selected_on_selection_track"]
    base_ck, mode = METHODS[op]
    thr = held["probability_threshold"]
    s1 = load_stats()
    ds = pd.read_csv(FT_OUT / "dataset.csv")
    held_res = json.loads((FT_OUT / "sites.json").read_text())["held_out"]
    assert not ds["site"].eq(held_res).any(), "held-out reservoir must not be in the fine-tuning data"
    val_rows, train_rows = ds[ds["site"] == VAL_SITE], ds[ds["site"] != VAL_SITE]
    print(f"train sites {sorted(train_rows['site'].unique())} ({len(train_rows)} scenes); val {VAL_SITE} ({len(val_rows)} scenes); "
          f"base {base_ck} ({op}), norm {mode}, thr {thr}", flush=True)
    res = [run_variant(v, train_rows, val_rows, a, device, base_ck, mode, s1, thr) for v in a.variants]
    winners = [r for r in res if r["improved"]]
    choice = max(winners, key=lambda r: r["best_val_iou"]) if winners else None
    (FT_OUT / "choice.json").write_text(json.dumps({
        "rule": "variant with the highest validation-site IoU; must beat the starting checkpoint on the validation site",
        "val_site": VAL_SITE, "train_sites": sorted(train_rows["site"].unique().tolist()),
        "base_method": op, "base_checkpoint": base_ck, "input_norm": mode, "probability_threshold": thr,
        "variants": res, "chosen": choice["variant"] if choice else None,
        "chosen_checkpoint": choice["checkpoint"] if choice else None}, indent=2, default=float))
    print("chosen:", choice["variant"] if choice else "none (no variant beat the starting model on the validation site)")


if __name__ == "__main__":
    main()
