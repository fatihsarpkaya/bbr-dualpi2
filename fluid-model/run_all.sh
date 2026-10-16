#!/usr/bin/env bash
# Run every configuration in configs/ (Figures 4 and 5, and in configs/sensitivity/ the sensitivity runs of
# Section V-B), JOBS at a time, then write the p'(t) traces to ../Experiment_Data/fluid-model/ with extract_pprime.py.
# One 40-s run takes a few minutes and about 5 GB (CUBIC), 10 GB (BBRv1) or 14 GB (BBRv2) of memory; a BBRv2
# configuration runs its three seeds one after another. The traces in results/ take about 5 GB in total.
# Usage: JOBS=4 ./run_all.sh
set -euo pipefail
shopt -s nullglob
cd "$(dirname "$0")"
JOBS=${JOBS:-4}
PYTHON=${PYTHON:-python3}
mkdir -p logs
export PYTHON
configs=(configs/bbr2_*.yaml configs/bbr1_*.yaml configs/cubic_*.yaml configs/sensitivity/*.yaml)  # longest first
printf '%s\n' "${configs[@]}" |
    xargs -P "$JOBS" -I{} sh -c '"$PYTHON" run_model.py -c "$1" > "logs/$(basename "$1" .yaml).log" 2>&1 && echo "done: $1"' _ {} ||
    echo "some runs failed; see logs/"
"$PYTHON" extract_pprime.py
