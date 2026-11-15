#!/usr/bin/env bash
# v2 fine-tuning chain: complete the data (v1 trained on 10 scenes after disk-guard refusals), then train the
# base (same loss, more data) and area (+ soft area term) variants, then evaluate on the held-out reservoir.
# Live log: $NASA_DATA/finetune/v2.log   (PowerShell: Get-Content -Wait <path>)
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-$HOME/miniconda3/envs/torch-gpu/python.exe}"
unset PYTHONPATH
export PYTHONNOUSERSITE=1 PYTHONUTF8=1 PYTHONUNBUFFERED=1
LOG_DIR="${NASA_DATA:-$HOME/nasa_data}/finetune"; mkdir -p "$LOG_DIR"; LOG="$LOG_DIR/v2.log"
step() { echo "=== $(date -u +%FT%TZ) $*" | tee -a "$LOG"; "$@" 2>&1 | grep --line-buffered -v -i "token" | tee -a "$LOG"; }

step "$PY" -u finetune/ft_prep.py --workers 3                                  # missing scenes only (cached skipped)
step "$PY" -u finetune/ft_train.py --run v2 --variants base:0 area:5 --epochs 25 --iters 150
step "$PY" -u finetune/ft_eval.py --run v2
echo "=== $(date -u +%FT%TZ) done" | tee -a "$LOG"
