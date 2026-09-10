# COLMAP Caspar fp64 BAL comparison

Use COLMAP's generated f64 backend, pinned for the September 7 comparison to
`ed8080bcf42ef0e42d3f5d0cd21eeff0698dfde8`. This is the actual vendored backend,
called directly so every BAL observation and the fixed-principal-point
SIMPLE_RADIAL objective match Prism. It does not benchmark the rest of COLMAP.
COLMAP normally defaults to fp32; these results explicitly use fp64.

```sh
git clone https://github.com/colmap/colmap.git /workspace/colmap-caspar
git -C /workspace/colmap-caspar checkout ed8080bcf42ef0e42d3f5d0cd21eeff0698dfde8
cmake -S bench/caspar -B /workspace/caspar-build \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=89 \
  -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc \
  -DCASPAR_GENERATED_DIR=/workspace/colmap-caspar/src/thirdparty/Symforce-Caspar/generated/f64
cmake --build /workspace/caspar-build -j 12
cp /workspace/caspar-build/caspar_bal /workspace/caspar-f64-frozen
python3 bench/compare_caspar.py --binary /workspace/caspar-f64-frozen \
  --out /workspace/caspar-new-results --data /workspace/bal
python3 bench/summarize_caspar.py /workspace/caspar-new-results \
  --output docs/caspar_comparison_results.md
```

The reporting script expects the original retained Prism N=3 control directories
recorded in the manifest. To reproduce on another machine, rerun both fixed
Prism arms with `bench/profile_iterations.py` and pass their paths with `--prism-full` and `--prism-largest`;
do not mix timing results from different GPUs.

CMake uses upstream's build options (including `--use_fast_math`) and instruments
a build-local solver copy with one assignment to the otherwise unpopulated
`SolveResult.initial_score` field. No solver decisions change. The upstream
checkout is not edited. The driver uses COLMAP's default settings, including
its double-valued `diag_scaling_down=0.333333`; the optional `paper` CLI argument
is a different configuration and is not used in this comparison.

The driver prints full-precision costs and per-iteration solver timestamps from
Caspar's existing iteration data. It infers acceptance from cost decreases,
because the pinned upstream revision does not update its acceptance log field.
The last rejected damping-exit attempt can precede iteration logging; do not
interpret trace length or the zero-based exit iteration as a total attempt count.

Every run checks the final objective independently on the CPU from the returned
poses, intrinsics, and points. The harness also compares the initial objective
against NumPy's independent BAL projection at relative tolerance 1e-6. CPU
validation and output export are outside solver timing. Graph construction,
factor upload, and index preparation are timed separately. Report both solver
clock and setup-inclusive crossings when comparing against Prism's timer.

The harness keeps all repeats, alternates Caspar's 200/2,000 budgets by replicate,
serializes GPU access with `flock`, hashes binaries/data, and refuses to overwrite
an incomplete log. Prism controls in this experiment were collected earlier;
they are not interleaved controls. There is no best-per-scene Prism selection.


The FP32 checked driver also supports optional `CASPAR_TARGET_COST` (native
`score_exit_value`) and `CASPAR_STATE_OUT` (exclusive `PRISMS01` state export).
An independent raw-z CPU target check is required before claiming attainment;
Caspar's native guarded FP32 objective can differ materially. Graph setup
reporting excludes the initial CPU cost audit. See
[the short comparison](../../docs/short_caspar_results.md) for the tested scope.

For the checked FP64 driver with native target stopping and exported-state validation, configure `-DCASPAR_DRIVER_CHECKED_DOUBLE=ON` against generated/f64. Keep `CASPAR_DRIVER_FLOAT=OFF`. The latest comparison and timing limitations are documented in [current Caspar results](../../docs/current_caspar_results.md).
