#!/usr/bin/env bash
set -u
cd /workspace/bench
mkdir -p gold
for f in problem-356-226730-pre problem-1723-156502-pre problem-257-65132-pre problem-1778-993923-pre problem-4585-1324582-pre problem-13682-4456117-pre; do
  for rep in 1 2 3; do
    timeout 1800 stdbuf -oL -eL /workspace/caspar/build32/caspar_bal32 /workspace/bal/$f.txt 2>&1       | python3 stamp.py > gold/${f}_caspar32_r${rep}.trace
    echo "caspar32 $f r$rep done" >> gold32.out
  done
done
touch .gold32_done
