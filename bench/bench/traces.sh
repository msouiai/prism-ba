#!/usr/bin/env bash
set -u
cd /workspace/bench
B=/workspace/mfree/gpu/build/oca_cuda
BASE="OCA_FORCE_UNSHARED=1 OCA_RHO_LAMBDA=1 OCA_GRID_DOWN=2 OCA_RHO_SHIFT=1 OCA_ALPHA_RHO=1 OCA_MENU_GATE=1e-2 OCA_FTOL=5e-5 OCA_FTOL_K=5 COLMAP_MFREE_VERBOSE=1"
mkdir -p traces
for f in problem-356-226730-pre problem-1723-156502-pre problem-257-65132-pre problem-1778-993923-pre problem-4585-1324582-pre problem-13682-4456117-pre; do
  X=""
  [ "$f" = problem-13682-4456117-pre ] && X="--mf-fp32"
  for arm in "block:OCA_BLOCKEQ=1 OCA_BLOCK_CM=1" "sched:OCA_BLOCKEQ=1 OCA_BLOCK_CM=1 OCA_PRECOND_SWITCH=1e-3"; do
    tag=${arm%%:*}; ENV=${arm#*:}
    env $BASE $ENV timeout 1800 stdbuf -oL -eL $B --problem /workspace/bal/$f.txt --algo mfree_shifted_cg --dof9 $X 2>&1       | python3 stamp.py > traces/${f}_${tag}.trace
    echo "TRACE $f $tag done" >> traces.out
  done
done
touch .traces_done
