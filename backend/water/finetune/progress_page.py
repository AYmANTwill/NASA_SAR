"""Live progress image for the overnight fine-tuning (PNG only, no terminal needed).

Every PERIOD seconds: redraws NASA_DATA/finetune/progress/progress.png (one file, overwritten). Stops when the chain log says "done" or after --hours.
Panels: pipeline steps, dates per site, downloads (count + MB/s per NISAR read), training curves per variant
(validation IoU, validation area bias, training loss), held-out evaluation when available.
Usage: python finetune/progress_page.py [--period 60] [--hours 14]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import pandas as pd  # noqa: E402

from common import DATA, OUTPUTS  # noqa: E402

FT = OUTPUTS / "finetune"
LOG = DATA / "finetune" / "overnight.log"
OUT = DATA / "finetune" / "progress"
STEPS = [("ft_sites.py", "1 · find sites"), ("--limit 6", "2 · first downloads"), ("--epochs 1", "3 · smoke test"),
         ("ft_prep.py --workers 5\n", "4 · all downloads"), ("--epochs 25", "5 · training"), ("ft_eval.py", "6 · held-out eval")]



def parse_log():
    text = LOG.read_text(encoding="utf-8", errors="ignore") if LOG.exists() else ""
    last_restart = text.rfind("restart on torch-gpu")
    text = text[last_restart:] if last_restart >= 0 else text
    starts = [l for l in text.splitlines() if l.startswith("=== ")]
    done_flag = any(l.rstrip().endswith(" done") for l in starts)
    state = []
    for key, label in STEPS:
        idx = [i for i, l in enumerate(starts) if (key.strip() in l) and (key != "ft_prep.py --workers 5\n" or "--limit" not in l)]
        if not idx:
            state.append((label, "todo"))
        else:
            later = idx[-1] < len(starts) - 1
            state.append((label, "done" if later or done_flag else "running"))
    errors = [l for l in text.splitlines() if re.search(r"Traceback|Error|FAILED", l)][-3:]
    return state, done_flag, errors, text


def draw():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    state, done_flag, errors, text = parse_log()
    fig = plt.figure(figsize=(16, 9.5), facecolor="#0f1115")
    gs = fig.add_gridspec(3, 3, height_ratios=[0.55, 1, 1], hspace=0.55, wspace=0.28)
    style = {"color": "#e6e6e6"}

    def ax_(spec, title):
        a = fig.add_subplot(spec); a.set_facecolor("#171a21"); a.set_title(title, **style, fontsize=11)
        a.tick_params(colors="#bbbbbb"); [s.set_color("#444") for s in a.spines.values()]; return a

    # 1. pipeline steps
    a = ax_(gs[0, :], "Pipeline")
    col = {"done": "#2ca02c", "running": "#ff9f1c", "todo": "#3a3f4b"}
    for i, (label, st) in enumerate(state):
        a.barh(0, 1, left=i, color=col[st], edgecolor="#0f1115", linewidth=3)
        a.text(i + 0.5, 0, f"{label}\n{st}", ha="center", va="center", color="white", fontsize=10, weight="bold")
    a.set_xlim(0, len(state)); a.set_yticks([]); a.set_xticks([])
    if errors:
        a.text(0, -0.75, "last error lines: " + " | ".join(e[:90] for e in errors), color="#ff6b6b", fontsize=8)

    # 2. sites
    a = ax_(gs[1, 0], "Dates with clear same-day DSWx, per site")
    rows = []
    for f in sorted(FT.glob("site_*.json")):
        info = json.loads(f.read_text())
        rows.append((f.stem[5:].replace("_", " "), info.get("n_dates", 0), info.get("skipped")))
    if rows:
        names = [r[0] for r in rows]
        a.barh(names, [r[1] for r in rows], color=["#555" if r[2] else "#4aa3ff" for r in rows])
        for i, r in enumerate(rows):
            a.text(r[1] + 0.3, i, r[2] or str(r[1]), va="center", color="#cccccc", fontsize=8)
        a.invert_yaxis()
    else:
        cur = re.findall(r"\[([A-Za-z_0-9]+)\] OSM", text)
        a.text(0.5, 0.5, f"searching… {cur[-1].replace('_', ' ') if cur else ''}", ha="center", va="center", **style,
               transform=a.transAxes)
    a.set_xlabel("NISAR dates", **style)

    # 3. downloads
    a = ax_(gs[1, 1], "Downloads (NISAR windows + DSWx labels)")
    n_total = len(pd.read_csv(FT / "candidates.csv")) if (FT / "candidates.csv").exists() else None
    n_done = len(list((DATA / "finetune" / "nisar").glob("*.tif"))) if (DATA / "finetune" / "nisar").exists() else 0
    rl = pd.read_csv(FT / "read_log.csv") if (FT / "read_log.csv").exists() else pd.DataFrame()
    if len(rl) and "nisar_read_s" in rl and rl["nisar_read_s"].notna().any():
        r = rl.dropna(subset=["nisar_read_s"])
        a.plot(range(1, len(r) + 1), r["nisar_payload_mb"] / r["nisar_read_s"], "o-", color="#4aa3ff", ms=3)
        a.set_ylabel("MB/s per read (payload)", **style); a.set_xlabel("read #", **style)
    a.text(0.02, 0.92, f"{n_done} / {n_total if n_total is not None else '?'} scenes cached", transform=a.transAxes,
           color="white", fontsize=12, weight="bold")

    # 4. held-out evaluation (when available)
    a = ax_(gs[1, 2], "Held-out reservoir (Bin El Ouidane)")
    ev = FT / "eval.json"
    if ev.exists():
        e = json.loads(ev.read_text())
        if "all_tracks" in e:
            ks = ["current", "current_water_level", "finetuned", "finetuned_water_level"]
            ious = [e["all_tracks"][k]["iou"] for k in ks]; bias = [e["all_tracks"][k]["area_bias_km2"] for k in ks]
            x = range(len(ks))
            a.bar([i - 0.2 for i in x], ious, 0.4, color="#4aa3ff", label="IoU")
            a2 = a.twinx(); a2.bar([i + 0.2 for i in x], bias, 0.4, color="#ff9f1c", label="area bias km²")
            a2.tick_params(colors="#bbbbbb"); a2.axhline(0, color="#777", lw=0.8)
            a.set_xticks(list(x)); a.set_xticklabels(["current", "cur+WL", "fine-tuned", "ft+WL"], color="#ccc")
            a.set_title(f"Held-out: {e['decision']}", color="#e6e6e6", fontsize=9, wrap=True)
        else:
            a.text(0.5, 0.5, e.get("decision", ""), ha="center", va="center", wrap=True, **style, transform=a.transAxes)
    else:
        a.text(0.5, 0.5, "after training", ha="center", va="center", color="#888", transform=a.transAxes)

    # 5-7. training curves
    logs = {v: pd.read_csv(FT / f"train_log_{v}.csv") for v in ("nisar", "mix") if (FT / f"train_log_{v}.csv").exists()}
    colors = {"nisar": "#4aa3ff", "mix": "#ff9f1c"}
    for j, (col_, title, ylab) in enumerate([("val_iou", "Validation IoU (Al Massira)", "IoU"),
                                             ("val_area_bias_km2", "Validation area bias (model − DSWx)", "km²"),
                                             ("train_loss", "Training loss (BCE + Dice)", "loss")]):
        a = ax_(gs[2, j], title)
        for v, d in logs.items():
            d = d.dropna(subset=[col_])
            if len(d):
                a.plot(d["epoch"], d[col_], "o-", color=colors[v], ms=4, label={"nisar": "NISAR only", "mix": "NISAR + S1 50/50"}[v])
        if col_ == "val_iou" and logs:
            base = next(iter(logs.values()))["val_iou"].iloc[0]
            a.axhline(base, color="#bbbbbb", ls="--", lw=1, label="current model (start)")
        if col_ == "val_area_bias_km2":
            a.axhline(0, color="#777", lw=0.8)
        if not logs:
            a.text(0.5, 0.5, "waiting for training", ha="center", va="center", color="#888", transform=a.transAxes)
        else:
            a.legend(fontsize=8, facecolor="#171a21", labelcolor="#ddd")
        a.set_xlabel("epoch", **style); a.set_ylabel(ylab, **style)

    fig.suptitle(f"Fine-tuning progress · {datetime.now():%H:%M:%S}" + (" · DONE" if done_flag else ""), color="white", fontsize=14)
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "progress.tmp.png"
    fig.savefig(tmp, dpi=90, facecolor=fig.get_facecolor()); plt.close(fig)
    tmp.replace(OUT / "progress.png")
    return done_flag


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", type=int, default=60)
    ap.add_argument("--hours", type=float, default=14)
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    t_end = time.time() + a.hours * 3600
    while True:
        try:
            done = draw()
        except Exception as e:  # never kill the page because a file is mid-write
            print("progress draw failed:", e, flush=True); done = False
        if a.once or done or time.time() > t_end:
            break
        time.sleep(a.period)


if __name__ == "__main__":
    main()
