#!/usr/bin/env bash
# Gate: the embeddable core (oca_core) must reproduce the CLI (oca_cuda).
#
# Both run the same kernels through the same LM policy, so their final costs
# must agree -- but only DISTRIBUTIONALLY. atomicAdd ordering makes single runs
# differ by up to ~1e-2 relative over 60 iterations, and dubrovnik-142 at 9 DoF
# is bimodal (round 9 trap #7). Comparing single traces here would produce a
# flaky gate; compare the replicate ranges instead.
#
#   ./run_core_gate.sh /path/to/problem.txt [reps]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PROB=${1:?usage: run_core_gate.sh PROBLEM.txt [reps]}
REPS=${2:-3}
LOCK=${LOCK:-/workspace/bundle_adjustment/gpu.lock}
BIN="$HERE/build/oca_cuda"
GATE="$HERE/build/test_oca_core"

[ -x "$GATE" ] || { echo "build test_oca_core first (cmake --build build)"; exit 1; }

for mode in dof9 dof6; do
  flags="--mf-fp32"; [ "$mode" = dof9 ] && flags="--dof9 --mf-fp32"
  echo "=== $(basename "$PROB")  $mode  ($REPS replicates)"
  for i in $(seq "$REPS"); do
    flock "$LOCK" -c "$BIN --problem '$PROB' --algo mfree_shifted_cg --tau_pt 3e-3 \
      --cg-checkpoints 8,16,32,64,128 --zero_k2 $flags --max_iter 61 --quiet" 2>&1 \
      | grep -oE 'final_cost=[0-9.]+' | sed 's/final_cost=/  CLI  /'
  done
  for i in $(seq "$REPS"); do
    flock "$LOCK" -c "$GATE '$PROB' $mode 3e-3" \
      | grep -oE 'final_cost=[0-9.]+' | sed 's/final_cost=/  CORE /'
  done
done
echo
echo "PASS if the CORE values fall inside the CLI spread for each mode."
