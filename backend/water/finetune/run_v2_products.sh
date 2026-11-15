#!/usr/bin/env bash
# Regenerate every water product with the v2 variant in the candidate set (variant still chosen on track 44 only).
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-$HOME/miniconda3/envs/torch-gpu/python.exe}"
export PYTHONPATH="${SCIENCE_PATH:-$HOME/NASA_SAR_water/backend}" PYTHONNOUSERSITE=1 PYTHONUTF8=1 PYTHONUNBUFFERED=1 WATER_FT_RUN=v2
LOG="${NASA_DATA:-$HOME/nasa_data}/finetune/v2.log"
step() { echo "=== $(date -u +%FT%TZ) $*" | tee -a "$LOG"; "$@" 2>&1 | grep --line-buffered -v -i "token\|warn" | tee -a "$LOG"; }
for s in evaluate.py heldout_eval.py timeseries.py save_probs.py water_level_eval.py "change_detect.py --mc 20" \
         "haouz_flood.py --mc 20" haouz_open_water.py output_assets.py clouds_figure.py outlier_figure.py gallery.py \
         diagnose_mask.py case_map_layers.py reservoir_case.py handoff_doc.py; do
  step "$PY" -u $s
done
echo "=== $(date -u +%FT%TZ) products done" | tee -a "$LOG"
