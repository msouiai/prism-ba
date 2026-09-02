#!/usr/bin/env bash
# Prism on Caspar paper hardware (RTX 4090): their six BAL datasets, native
# Snavely dof9 objective, N=3 per arm. Arms: block stack (speed champion) and
# scheduler (quality champion). fp32 fragments on final-13682 only.
set -u
cd /workspace/bench
B=/workspace/mfree/gpu/build/oca_cuda
BASE="OCA_FORCE_UNSHARED=1 OCA_RHO_LAMBDA=1 OCA_GRID_DOWN=2 OCA_RHO_SHIFT=1 OCA_ALPHA_RHO=1 OCA_MENU_GATE=1e-2 OCA_FTOL=5e-5 OCA_FTOL_K=5"
: > run6.out
for f in problem-356-226730-pre problem-1723-156502-pre problem-257-65132-pre problem-1778-993923-pre problem-4585-1324582-pre problem-13682-4456117-pre; do
  X=""
  [ "$f" = problem-13682-4456117-pre ] && X="--mf-fp32"
  for arm in "block:OCA_BLOCKEQ=1 OCA_BLOCK_CM=1" "sched:OCA_BLOCKEQ=1 OCA_BLOCK_CM=1 OCA_PRECOND_SWITCH=1e-3"; do
    tag=${arm%%:*}; ENV=${arm#*:}
    for rep in 1 2 3; do
      env $BASE $ENV timeout 1800 $B --problem /workspace/bal/$f.txt --algo mfree_shifted_cg --dof9 $X --quiet 2>&1 \
        | grep -E "RESULT|DIAGNOSTICS" | sed "s/^/$f $tag rep$rep /" >> run6.out
    done
  done
  echo "DONE $f" >> run6.out
done
touch /workspace/bench/.run6_done
