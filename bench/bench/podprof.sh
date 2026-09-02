#!/usr/bin/env bash
set -u
cd /workspace/bench
mkdir -p prof
BASE="OCA_FORCE_UNSHARED=1 OCA_RHO_LAMBDA=1 OCA_GRID_DOWN=2 OCA_RHO_SHIFT=1 OCA_ALPHA_RHO=1 OCA_MENU_GATE=1e-2 OCA_FTOL=5e-5 OCA_FTOL_K=5 OCA_BLOCKEQ=1 OCA_BLOCK_CM=1 COLMAP_MFREE_VERBOSE=1 OCA_PROFILE=1"
for f in problem-257-65132-pre problem-1778-993923-pre problem-4585-1324582-pre problem-13682-4456117-pre; do
  X=""
  [ "$f" = problem-13682-4456117-pre ] && X="--mf-fp32"
  env $BASE timeout 1800 stdbuf -oL -eL /workspace/mfree/gpu/build/oca_cuda     --problem /workspace/bal/$f.txt --algo mfree_shifted_cg --dof9 --zero_k2 $X 2>&1     | python3 stamp.py > prof/${f}_block_pod.trace
  echo "$f done" >> podprof.out
done
touch .podprof_done
