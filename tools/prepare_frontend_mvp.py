"""Assemble the demo's case files from committed results; never rerun scientific processing.

Run with the backend's Python environment from any directory:
    python tools/prepare_frontend_mvp.py --panama-preview
The optional Panama fit is Anass's documented +1 run: unstable, draft, no magnitude finding.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panama-preview", action="store_true")
    args = parser.parse_args()
    if args.panama_preview:
        source = ROOT / "results/panama-2026/fault/sign_plus"
        report = json.loads((source / "panama-2026.json").read_text(encoding="utf-8"))
        # This is an explicitly inconclusive preview, never a choice of the best-fitting sign.
        if report["los_sign"] != 1 or report["stable"] or report["findings"]:
            raise RuntimeError("Panama preview changed: review the scientific result before importing it.")
        target = ROOT / "backend/cases/out"
        target.mkdir(parents=True, exist_ok=True)
        for name in ["panama-2026.json", "panama-2026_fit.png"]:
            destination = target / name
            if destination.exists() and destination.read_bytes() != (source / name).read_bytes():
                raise RuntimeError(f"Existing input preserved: {destination}")
            shutil.copy2(source / name, destination)
        print("Panama: documented +1 preview, unstable; no magnitude claimed.", flush=True)
    subprocess.run([sys.executable, "-m", "science.cases", "--offline"], cwd=ROOT / "backend", check=True)


if __name__ == "__main__":
    main()
