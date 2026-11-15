"""Figures for MODEL.md: architecture, training curves, reservoirs used, version comparison.

Every number is read from files written by the pipeline (checkpoint metadata, outputs/finetune/*/).
Usage (from backend/water/): python model/model_figures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

from common import OUTPUTS  # noqa: E402

FIG = HERE / "figures"
FT = OUTPUTS / "finetune"
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e4e3de"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False})


def box(ax, x, y, w, h, text, fc, ec=None, fs=8.5, tc=INK):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=ec or fc, lw=1))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=tc)


def arrow(ax, a, b, color=MUTED, style="-|>", ls="-", rad=0.0):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=10, color=color, lw=1.2, ls=ls,
                                 connectionstyle=f"arc3,rad={rad}"))


def architecture() -> None:
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.set_xlim(0, 12.2); ax.set_ylim(-0.3, 6.6); ax.axis("off")
    W, H, dy, y0 = 1.9, 0.62, 0.95, 4.65          # level k sits at y0 - k*dy; decoder 5 at k = -1
    yk = lambda k: y0 - k * dy
    for i, (t, c) in enumerate((("HH (dB)", "#cde2fb"), ("HV (dB)", "#cde2fb"), ("incidence angle (°)", "#fde3c8"))):
        box(ax, 0.1, 4.3 - i * 0.6, 1.5, 0.48, t, c, fs=8)
    ax.text(0.85, 5.0, "NISAR GCOV input\n3 × 512 × 512, 10 m", ha="center", fontsize=8.5, color=INK)
    enc = ["conv 7×7 + BN\n64 @ 256²", "ResNet layer 1\n3 blocks · 64 @ 128²", "layer 2\n4 blocks · 128 @ 64²",
           "layer 3\n6 blocks · 256 @ 32²", "layer 4\n3 blocks · 512 @ 16²"]
    dec = {3: "decoder 1\n256 @ 32²", 2: "decoder 2\n128 @ 64²", 1: "decoder 3\n64 @ 128²", 0: "decoder 4\n32 @ 256²",
           -1: "decoder 5\n16 @ 512²"}
    ex = lambda k: 2.1 + k * 0.32
    dxk = lambda k: 7.3 - k * 0.32
    for k, t in enumerate(enc):
        box(ax, ex(k), yk(k), W, H, t, "#86b6ef", fs=8)
    for k, t in dec.items():
        box(ax, dxk(k), yk(k), W, H, t, "#9edfc4", fs=8)
    arrow(ax, (1.6, 3.95), (ex(0), yk(0) + H / 2))
    for k in range(4):  # encoder down
        arrow(ax, (ex(k) + W / 2, yk(k)), (ex(k + 1) + W / 2, yk(k + 1) + H))
    arrow(ax, (ex(4) + W, yk(4) + H / 2), (dxk(3) + W / 2, yk(3)), rad=0.25)  # bottleneck -> decoder 1
    for k in range(4):  # skips at the same resolution
        arrow(ax, (ex(k) + W, yk(k) + H / 2), (dxk(k), yk(k) + H / 2), color=BLUE, ls="--")
    for k in (3, 2, 1, 0):  # decoder up
        arrow(ax, (dxk(k) + W / 2, yk(k) + H), (dxk(k - 1) + W / 2, yk(k - 1)))
    ax.plot([], [], ls="--", color=BLUE, label="skip connection (concatenation)")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.02), frameon=False, fontsize=8.5)
    ax.text(ex(2) + W / 2, 0.35, "Encoder: ResNet-34 (ImageNet init., trained on Sentinel-1)\n"
            "BatchNorm statistics re-estimated on NISAR (AdaBN), then frozen", ha="center", fontsize=8.5, color=INK)
    ax.text(dxk(1) + W / 2, 0.35, "U-Net decoder\n(upsampling ×2 + skip, 2 convs each)", ha="center", fontsize=8.5, color=INK)
    hx = 10.1
    heads = [("Dropout2d (p = 0.2)", "#e4e3de"), ("1×1 conv → 1 logit", "#e4e3de"), ("sigmoid ≥ 0.35 → water", "#f7c6d8")]
    for i, (t, c) in enumerate(heads):
        box(ax, hx, yk(-1) - i * 0.85, 1.9, 0.55, t, c, fs=8)
        if i:
            arrow(ax, (hx + 0.95, yk(-1) - (i - 1) * 0.85), (hx + 0.95, yk(-1) - i * 0.85 + 0.55))
    arrow(ax, (dxk(-1) + W, yk(-1) + H / 2), (hx, yk(-1) + 0.28))
    ax.set_title("Water U-Net v3: 24.5 M parameters, 3 input channels, per-pixel water probability",
                 fontsize=11, color=INK, loc="left")
    fig.tight_layout(); fig.savefig(FIG / "architecture.png", dpi=200); plt.close(fig)


def training() -> None:
    log = pd.read_csv(FT / "v3site" / "train_log_inc.csv")
    ch = json.loads((FT / "v3site" / "choice.json").read_text())
    kept = ch["variants"][0]["kept_epoch"]
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.4))
    t = log.dropna(subset=["train_loss"])
    axs[0].plot(t["epoch"], t["train_loss"], "-o", color=BLUE, ms=3, lw=2)
    axs[0].set(title="Training loss (BCE + Dice)", xlabel="epoch")
    axs[1].plot(log["epoch"], log["val_iou"], "-o", color=BLUE, ms=3, lw=2)
    axs[1].set(title="Validation IoU (Al Massira, never trained on)", xlabel="epoch", ylim=(0, 1))
    axs[2].plot(log["epoch"], log["val_area_bias_km2"], "-o", color=BLUE, ms=3, lw=2)
    axs[2].axhline(0, color=MUTED, lw=1)
    tol = ch["variants"][0]["bias_tolerance_km2"]
    axs[2].axhspan(-tol, tol, color=GRID, zorder=0, label=f"±5% of the DSWx water area ({tol:.1f} km²)")
    axs[2].set(title="Validation area bias (km², model − DSWx)", xlabel="epoch")
    v0 = log['val_area_bias_km2'].iloc[0]
    axs[2].set_ylim(-2 * tol, 2 * tol)
    axs[2].annotate(f'epoch 0: {v0:+.0f} km² (off scale)', (0, 2 * tol), xytext=(1.0, 1.6 * tol), fontsize=7.5, color=MUTED)
    axs[2].legend(fontsize=7.5, frameon=False, loc="upper right")
    for a in axs:
        a.axvline(kept, color=ORANGE, lw=1.2, ls="--")
        a.grid(color=GRID, lw=0.6)
    axs[1].text(kept + 0.3, 0.08, f"kept: epoch {kept}", color=ORANGE, fontsize=8)
    fig.suptitle(f"Fine-tuning on NISAR ({ch['n_train_scenes']} training scenes, lr 2e-5, frozen BatchNorm); "
                 f"epoch 0 = the Sentinel-1 model before fine-tuning", fontsize=10, x=0.01, ha="left", color=INK)
    fig.tight_layout(); fig.savefig(FIG / "training.png", dpi=200); plt.close(fig)


def sites() -> None:
    import contextily as cx

    meta = json.loads((FT / "sites.json").read_text())["sites"]
    aoi = json.loads((OUTPUTS / "aoi.json").read_text())
    case = aoi["chosen"]["reservoir"]
    ch = json.loads((FT / "v3site" / "choice.json").read_text())
    ds = pd.read_csv(FT / "dataset.csv")
    n = ds.groupby("site").size().to_dict()
    role = {s: "train" for s in ch["train_sites"]}
    role[ch["val_site"]] = "validation"
    for s in ch.get("test_sites", []):
        role[s] = "test"
    role[case] = "case"
    pts = {s: meta[s]["bbox"] for s in meta if s in role}
    pts[case] = aoi["aois"][case]["bbox"]
    style = {"train": (BLUE, "o", "training"), "validation": (ORANGE, "s", "validation (epoch, threshold)"),
             "test": (AQUA, "D", "test, never used"), "case": (MAGENTA, "*", "case reservoir (dates after 2026-10-03 only)")}
    fig, ax = plt.subplots(figsize=(8.5, 8))
    for r, (c, m, lab) in style.items():
        xs = [(pts[s][0] + pts[s][2]) / 2 for s in pts if role[s] == r]
        ys = [(pts[s][1] + pts[s][3]) / 2 for s in pts if role[s] == r]
        ax.scatter(xs, ys, s=170 if m == "*" else 70, c=c, marker=m, edgecolors="white", linewidths=1.5, zorder=5, label=lab)
    for s, b in pts.items():
        x, y = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        nm = {"Lalla_Takerkoust": "Yacoub el Mansour"}.get(s, s.replace("_", " "))  # OSM found this reservoir near the given centre + (f" ({n.get(s, '')})" if s in n else "")
        ax.annotate(nm, (x, y), xytext=(6, 4), textcoords="offset points", fontsize=7.5, color="white",
                    bbox=dict(boxstyle="round,pad=0.2", fc="#1f1f1ecc", ec="none"), zorder=6)
    ax.set(xlim=(-10.2, -1.6), ylim=(29.3, 35.8), xlabel="longitude (°)", ylabel="latitude (°)")
    try:
        cx.add_basemap(ax, crs="EPSG:4326", source=cx.providers.Esri.WorldImagery, attribution_size=6)
    except Exception as e:
        print("basemap failed:", e)
    ax.legend(loc="lower right", fontsize=8, framealpha=0.95)
    ax.set_title("Moroccan reservoirs used for v3 (number of NISAR dates with clear same-day DSWx labels)",
                 fontsize=10, loc="left", color=INK)
    fig.tight_layout(); fig.savefig(FIG / "reservoirs.png", dpi=200); plt.close(fig)


def comparison() -> None:
    ev = json.loads((FT / "v3" / "eval.json").read_text())["sets"]
    names = {"current": "v1", "v2": "v2", "v3noinc_noinc": "v3 (no angle)", "v3_inc": "v3", "v3site_inc": "v3site\n(shipped)"}
    test = next(k for k in ev if k.startswith("test:"))
    cols = [BLUE if k != "v3site_inc" else ORANGE for k in names]
    panels = [
        (ev["case_reservoir_case_period"], lambda r: r["iou"], lambda r: r["ci95"]["iou"],
         "IoU vs DSWx, Bin El Ouidane,\ncase period (no training date)", (0, 1)),
        (ev[test], lambda r: r["iou"], lambda r: r["ci95"]["iou"],
         f"IoU vs DSWx, {test.split(':')[1].replace('_', ' ')}\n(reservoir never used by v3)", (0, 1)),
        (ev["case_reservoir"], lambda r: abs(r["multitrack_change_km2"]["model"] - r["multitrack_change_km2"]["dswx"]), None,
         "|change − DSWx change| (km²), June → September,\n3 tracks (lower is better)", None),
    ]
    fig, axs = plt.subplots(1, 3, figsize=(12.5, 3.8))
    for a, (data, val, ci, title, ylim) in zip(axs, panels):
        v = [val(data[k]) for k in names]
        bars = a.bar(range(len(names)), v, color=cols, width=0.62, edgecolor="white", linewidth=2)
        if ci:
            lo = [v[i] - ci(data[k])[0] for i, k in enumerate(names)]
            hi = [ci(data[k])[1] - v[i] for i, k in enumerate(names)]
            a.errorbar(range(len(names)), v, yerr=[lo, hi], fmt="none", ecolor=INK, capsize=3, lw=1)
        tops = [ci(data[k])[1] for k in names] if ci else v
        for b, x, tp in zip(bars, v, tops):
            a.text(b.get_x() + b.get_width() / 2, tp + 0.01, f"{x:.2f}", ha="center", va="bottom", fontsize=8, color=INK)
        a.set_xticks(range(len(names)), list(names.values()), fontsize=8)
        a.set_title(title, fontsize=9, loc="left", color=INK)
        if ylim:
            a.set_ylim(*ylim)
        a.grid(axis="y", color=GRID, lw=0.6)
    fig.suptitle("Model versions on the same dates (95% bootstrap intervals over dates); orange = shipped", fontsize=10,
                 x=0.01, ha="left", color=INK)
    fig.tight_layout(); fig.savefig(FIG / "versions.png", dpi=200); plt.close(fig)


if __name__ == "__main__":
    FIG.mkdir(parents=True, exist_ok=True)
    architecture(); training(); sites(); comparison()
    print("figures:", sorted(p.name for p in FIG.glob("*.png")))
