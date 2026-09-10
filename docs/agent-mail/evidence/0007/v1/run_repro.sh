#!/usr/bin/env bash
# Multi-shift CG reproduction runner.
#
# Runs the 5-shift solver over the 20 BAL problems both hosts share, N=3 each,
# and writes one CSV row per run. Compare on final_cost; wall is reported but
# is not the cross-host claim.
#
# Usage:  ./run_repro.sh <BAL_DIR> [OUT_CSV]
#   e.g.  ./run_repro.sh /workspace/bal repro_codex.csv
#
# One GPU job at a time: check `nvidia-smi` before starting.

set -u
BAL="${1:?usage: run_repro.sh <BAL_DIR> [OUT_CSV]}"
OUT="${2:-repro.csv}"
BIN="$(cd "$(dirname "$0")" && pwd)/oca_cuda"

# The exact configuration under test. Do not change these.
export OCA_RHO_LAMBDA=1 OCA_GRID_DOWN=2 OCA_RHO_SHIFT=1 OCA_ALPHA_RHO=1

DATASETS="dubrovnik-135 dubrovnik-173 dubrovnik-356 dubrovnik-88
final-1936 final-3068 final-4585 final-93
ladybug-1197 ladybug-1469 ladybug-1723 ladybug-49 ladybug-598 ladybug-810
trafalgar-126 trafalgar-257
venice-1672 venice-1778 venice-52 venice-89"

echo "dataset,rep,final_cost,solve_seconds" > "$OUT"
for ds in $DATASETS; do
  [ -f "$BAL/$ds.txt" ] || { echo "MISSING $ds" >&2; continue; }
  for rep in 1 2 3; do
    line=$(timeout 3600 "$BIN" --problem "$BAL/$ds.txt" --algo mfree_shifted_cg \
             --dof9 --zero_k2 --max_iter 60 2>&1 \
           | grep -oE 'final_cost=[0-9.eE+-]+ solve_seconds=[0-9.]+' | tail -1)
    fc=$(sed -E 's/.*final_cost=([0-9.eE+-]+).*/\1/' <<<"$line")
    sec=$(sed -E 's/.*solve_seconds=([0-9.]+).*/\1/' <<<"$line")
    echo "$ds,$rep,${fc:-NA},${sec:-NA}" | tee -a "$OUT"
  done
done
echo "done -> $OUT"
