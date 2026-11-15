#!/usr/bin/env bash
# v3 data: new reservoirs (search + reads), then incidence-angle rasters for every scene. Live log: $NASA_DATA/finetune/v3.log
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-$HOME/miniconda3/envs/torch-gpu/python.exe}"
unset PYTHONPATH
export PYTHONNOUSERSITE=1 PYTHONUTF8=1 PYTHONUNBUFFERED=1
LOG="${NASA_DATA:-$HOME/nasa_data}/finetune/v3.log"
step() { echo "=== $(date -u +%FT%TZ) $*" | tee -a "$LOG"; "$@" 2>&1 | grep --line-buffered -v -i "token\|warn" | tee -a "$LOG"; }
step "$PY" -u finetune/ft_sites.py
step "$PY" -u finetune/ft_prep.py --workers 3
echo "=== $(date -u +%FT%TZ) data done" | tee -a "$LOG"
