# Lambda hysteresis experiment

Build the normal `oca_cuda` target. The feature is disabled by default.

- `OCA_LAMBDA_HYSTERESIS=0.95`: keep at least 95% of the best positive
  scored menu reduction, preferring the eligible absolute shift closest
  to the last accepted menu shift in log space.
- `OCA_LAMBDA_HYSTERESIS_LOG=1`: collect per-shift best checkpoint costs,
  absolute shifts, depths, prior, center, greedy/preferred/selected indices.
  Without the selection flag, this logs a hypothetical 95% choice only.

Both logging and selection keep a device snapshot of the best improving
full step for each shift and its model prediction. This costs `8*L*n` bytes
for fp64 steps (n is the full camera+point parameter count), plus copying
and diagnostics. The paired control pays the same instrumentation costs.
A separate logging-off arm measures practical overhead. No claim that
instrumentation leaves the floating-point trajectory bit-identical is made.

Supported scope: unshared dof9, fp64, full observation scoring. Other modes
fail explicitly when requested. Existing menu gating is respected; unscored
shifts do not qualify. Selection is across each shift's best scored depth,
then the original alpha search and acceptance run. History records the menu
shift label even if alpha subsequently rescales the step. Backtracking
rescues preserve history. A zero-depth/point-only candidate can have a shift
label without an informative camera-damping choice; logs retain its depth.

Run paired experiments:

```
python3 bench/lambda_hysteresis_experiment.py --binary /path/to/frozen \
  --out /path/to/results/main --scenes venice-52 ladybug-1197
python3 bench/lambda_hysteresis_experiment.py --binary /path/to/frozen \
  --out /path/to/results/stress --scenes final-3068 --max-iter 100
python3 bench/summarize_lambda_hysteresis.py --root /path/to/results \
  --out docs/lambda_hysteresis_results.md
python3 bench/plot_lambda_hysteresis.py --root /path/to/results
```

The summarizer checks the reduction and nearest-history guarantees in every
logged attempt. Host selection tests:

```
g++ -std=c++17 -O2 bench/test_lambda_hysteresis.cc -o /tmp/test-hysteresis
/tmp/test-hysteresis
```

The priority pilot protocol and raw results are under
`/workspace/prism-hysteresis`; frozen prior-study binaries are unchanged.
