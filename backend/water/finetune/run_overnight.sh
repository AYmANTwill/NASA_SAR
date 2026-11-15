#!/usr/bin/env bash
# Overnight fine-tuning chain (stops at the first failure; every step resumes from its cached files).
# Isolated interpreter: PYTHON (default: the torch-gpu conda env), PYTHONPATH cleared, user site disabled.
# Live log: $NASA_DATA/finetune/overnight.log  (PowerShell: Get-Content -Wait <path>)
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-$HOME/miniconda3/envs/torch-gpu/python.exe}"
unset PYTHONPATH
export PYTHONNOUSERSITE=1 PYTHONUTF8=1 PYTHONUNBUFFERED=1
LOG_DIR="${NASA_DATA:-$HOME/nasa_data}/finetune"; mkdir -p "$LOG_DIR"; LOG="$LOG_DIR/overnight.log"
step() { echo "=== $(date -u +%FT%TZ) $*" | tee -a "$LOG"; "$@" 2>&1 | grep --line-buffered -v -i "token" | tee -a "$LOG"; }

echo "=== $(date -u +%FT%TZ) interpreter: $("$PY" -c 'import sys,torch;print(sys.version.split()[0], sys.prefix, "torch", torch.__version__, "cuda", torch.cuda.is_available())')" | tee -a "$LOG"
step "$PY" -u finetune/ft_sites.py
step "$PY" -u finetune/ft_prep.py --workers 5 --limit 6                       # a few scenes first
step "$PY" -u finetune/ft_train.py --variants nisar mix --epochs 1 --iters 5  # smoke test of the training loop
rm -f "$LOG_DIR/../models/unet_ft_nisar.pt" "$LOG_DIR/../models/unet_ft_mix.pt"
step "$PY" -u finetune/ft_prep.py --workers 5                                 # everything else (cached reads skipped)
step "$PY" -u finetune/ft_train.py --variants nisar mix --epochs 25 --iters 150
step "$PY" -u finetune/ft_eval.py
echo "=== $(date -u +%FT%TZ) done" | tee -a "$LOG"
