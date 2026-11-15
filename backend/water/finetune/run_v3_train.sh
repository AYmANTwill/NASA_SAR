#!/usr/bin/env bash
# v3: incidence rasters, then two variants on the enlarged data (noinc = 2 channels, inc = + incidence angle),
# test reservoir Oued_El_Makhazine fixed before training, then the v3 evaluation. Live log: $NASA_DATA/finetune/v3.log
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-$HOME/miniconda3/envs/torch-gpu/python.exe}"
unset PYTHONPATH
export PYTHONNOUSERSITE=1 PYTHONUTF8=1 PYTHONUNBUFFERED=1
LOG="${NASA_DATA:-$HOME/nasa_data}/finetune/v3.log"
step() { echo "=== $(date -u +%FT%TZ) $*" | tee -a "$LOG"; "$@" 2>&1 | grep --line-buffered -v -i "token\|warn" | tee -a "$LOG"; }
step "$PY" -u finetune/ft_incidence.py --workers 3
# the two variants train in parallel (about 2.3 GB of GPU memory each): v3 = + incidence angle, v3noinc = data only
step "$PY" -u finetune/ft_train.py --run v3noinc --variants noinc:0 --test-sites Oued_El_Makhazine --epochs 25 --iters 200 &
P1=$!
step "$PY" -u finetune/ft_train.py --run v3 --variants inc:0:inc --test-sites Oued_El_Makhazine --epochs 25 --iters 200
wait $P1
# v3site: + Bin El Ouidane dates more than one revisit (12 d) after the case period end 2026-09-21, i.e. after 2026-10-03;
# tested only on dates up to 2026-09-21
step "$PY" -u finetune/ft_train.py --run v3site --variants inc:0:inc --test-sites Oued_El_Makhazine --case-after 2026-10-03 --epochs 25 --iters 200
step "$PY" -u finetune/ft_eval_v3.py
echo "=== $(date -u +%FT%TZ) v3 done" | tee -a "$LOG"
