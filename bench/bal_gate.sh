#!/usr/bin/env bash
# BAL regression gate for the mfree-parity branch of prism-ba.
# usage: bal_gate.sh <oca_cuda binary> <outdir>
# Runs the README champion configuration (gold.sh BASE + block arm) on a fixed
# scene list and records final_cost / accepted iterations / wall per run.
set -u
BIN=$1; OUT=$2; mkdir -p "$OUT"
BASE="OCA_FORCE_UNSHARED=1 OCA_RHO_LAMBDA=1 OCA_GRID_DOWN=2 OCA_RHO_SHIFT=1 OCA_ALPHA_RHO=1 OCA_MENU_GATE=1e-2 OCA_FTOL=5e-5 OCA_FTOL_K=5 OCA_BLOCKEQ=1 OCA_BLOCK_CM=1 COLMAP_MFREE_VERBOSE=1"
SCENES="ladybug-49 trafalgar-126 dubrovnik-88 ladybug-1197 final-1936"
: > "$OUT/summary.txt"
for s in $SCENES; do
  for rep in 1 2 3; do
    t0=$(date +%s.%N)
    env $BASE timeout 1200 "$BIN" --problem /workspace/bal/$s.txt --algo mfree_shifted_cg --dof9 --zero_k2 > "$OUT/${s}_r${rep}.log" 2>&1
    rc=$?
    t1=$(date +%s.%N)
    res=$(grep "^RESULT" "$OUT/${s}_r${rep}.log" | tail -1 | sed 's/RESULT algo=mfree_shifted_cg //')
    acc=$(grep -o "accepts=[0-9]* rejects=[0-9]* total_matvecs=[0-9]*" "$OUT/${s}_r${rep}.log" | tail -1)
    printf "%-16s r%d rc=%d %s %s wall=%.2f\n" "$s" "$rep" "$rc" "${res:-RESULT?}" "${acc:-?}" "$(echo "$t1-$t0" | bc)" | tee -a "$OUT/summary.txt"
  done
done
