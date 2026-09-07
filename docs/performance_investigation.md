# Iteration-cost investigation (2026-09-07)

This investigation follows REPRODUCE.md's objective and experimental protocol,
with the user's override: investigate execution cost rather than implement the
proposed open-problem algorithms. The fp32-baseline and crossing-speed
retractions remain in force. No Caspar speedup is claimed.

The verdict is a verified reduction in execution cost, not a universally faster
converged solver. Cache + batched scoring + the forward-norm diagonal reduces
the repeated 60-outer final-4585 workload from 94.886 s to 70.830 s (25.4%),
with matching printed attempt traces and endpoints. Full-run trajectories vary,
so the new paths remain opt-in. All scheduled tests have finished; this is a
six-scene performance investigation, not the full 22-scene reproduction ledger.
See [all measured results and crossings](performance_results.md).

## Scope and reproducibility

- Repository cloned to `/workspace/prism-ba`; original commit and binary hashes
  are recorded with the experiment manifests in `/workspace/prism-results`.
- GPU: NVIDIA RTX 2000 Ada, 16 GB, 70 W; CUDA compiler 12.8.93; architecture 89;
  Release, `-O3`; fp64 state and fragments, SIMPLE_RADIAL (`--dof9 --zero_k2`).
- Frozen original executable: `/workspace/prism-results/baseline`.
- Fixed conservative optimization arm: `OCA_RETRY_CACHE=1 OCA_MULTI_RHS=1`.
  Both apply everywhere, without endpoint-based scene selection. The latter is
  an existing, previously opt-in kernel; the cache is new.
- Quality experiments use the exact Config A/B profiles, 600 outer budget,
  N=3, one GPU process at a time using `/tmp/prism_gpu.lock`. Most cells are
  interleaved. The conservative Config A final-3068 cell shares all three
  identical same-session controls from the forward-norm gate; this amendment
  was recorded before that cell's optimized runs and retains every control.
- final-4585 Config A has a separately labelled 60-outer timing gate; it must
  not be represented as a converged endpoint or compared with a 600-outer result.
- `bench/profile_iterations.py` independently evaluates every input in NumPy,
  asserts initial-cost agreement at relative 1e-6, records binary/data hashes,
  raw cost/time traces, endpoints, counts, ranges, medians and both crossings.
- `bench/download_bal.py` resolves filenames from the official BAL family pages.
  The explicit public scene list in REPRODUCE.md actually contains **22** files,
  despite the prose saying 20 public/23 total. This discrepancy is not silently
  resolved by inventing or dropping scenes.
- Caspar's generated `gen/` sources and library are absent in this checkout.
  Consequently this report compares Prism implementations and configurations,
  not a newly verified Caspar baseline. Local derivative scenes are also absent.

## What actually consumes the time

Nsight Systems trace of original Config A, final-4585, first 15 outers:
15 accepts, 94 rejects, 168 matvecs, 459 menu evaluations and 120 alpha evaluations.
Solve wall: 22.43 s. Kernel percentages include the CLI's small diagnostics cost.

| Kernel | GPU seconds | GPU share | Calls | Average |
|---|---:|---:|---:|---:|
| MFPass1 | 6.483 | 29.3% | 627 | 10.34 ms |
| MFDiagK | 6.016 | 27.2% | 109 | 55.20 ms |
| KernelCostBlockRed | 2.721 | 12.3% | 580 | 4.69 ms |
| MFPass2 | 1.814 | 8.2% | 168 | 10.80 ms |
| MFAssemble | 1.614 | 7.3% | 15 | 107.61 ms |
| MFRhsPrime | 1.203 | 5.4% | 109 | 11.04 ms |
| MFPointFactorObs | 0.874 | 4.0% | 15 | 58.30 ms |
| MFPointFactorTau | 0.329 | 1.5% | 109 | 3.02 ms |

The label "pointfactor+rhs" hides the largest individual rebuild cost: the
Schur diagonal, not the point QR factorization. Every attempt rereads 27 fp64
fragment values per observation and performs nine full triangular solves to
construct a diagonal. Each solve divides six times, yet the caller only needs
one quadratic form. Rejections multiply this cost even when the outer count is
small. A matvec count alone misses most of the storm's work.

Candidate scoring separately rereads those fragments for each shift's point
back-substitution. The five-shift menu shares the Krylov sweep, but its original
scoring path does not share the fragment reads. Batched multiplication addresses
that duplication while preserving the candidate list, ordering and fp64 scorer.
It still uses atomics, so it is mathematically equivalent, not bitwise identical.

Venice-52's 30-outer diagnostic has a different balance: 2.745 s of 3.484 s
wall is in Krylov work. Thus an optimization of retries or candidate scoring
cannot yield a universal large speedup. Existing `OCA_MENU_FUSE=1` was also
piloted there; it did not produce a useful wall improvement in that diagnostic.

## Implemented changes

1. **Retry cache, opt-in (`OCA_RETRY_CACHE=1`).** Reuse point factors, the
   equilibrated RHS, Jacobi scaling and the optional point prediction constant
   when the assembly and effective point damping are unchanged. Include the
   conditioning-selected floor in the cache key. Invalidate on every assembly;
   exclude shared-intrinsics, block and polynomial paths. Lambda-only changes
   alter the shift, not these cached quantities. No attempts are skipped.
2. **Optional fused camera RHS/diagonal (`OCA_RHS_DIAG_CAMERA=1`).** Reuse the
   existing camera-major fragments for both calculations; block reductions
   replace contended global atomics. Keep fp64 and the original per-observation
   formulas. This is deliberately excluded from the fixed optimization arm:
   the microbenchmark is slower at low camera counts.
3. **Optional forward-norm diagonal (`OCA_DIAG_NORM=1`).** For `V=R^T R`,
   `g^T V^-1 g = ||R^-T g||^2`; the backward solve is unnecessary. Halve the
   divisions without forming an inverse or reducing precision. This changes
   rounding and therefore requires a separate trajectory gate. It is ignored
   when the fused camera diagonal is selected.
4. **Correct profiling.** Include the batched menu's shared lift/multiplication
   in candidate time. Report the alpha-grid time and evaluation count separately;
   previously both were absent from the phase report. Preserve the legacy menu
   counter's meaning, since existing experimental policies consume it.
5. **Batched-buffer safety.** Size scratch buffers using the effective shift
   count after `OCA_NSHIFTS` is resolved, and replace the fixed 16-entry active
   list with a vector. Larger menus previously overran these buffers.
6. **Initial objective logging.** Print the fp64 `score_init` at 17 significant
   digits; the CSV initial row remains available for original binaries.
7. **Reproduction tools and numerical gate.** Add the downloader, interleaved
   benchmark harness and `test_rhs_diag` (6/9 camera dimensions, float/double
   fragment storage, invalid factors, empty camera, RHS-only and diagonal paths).

## Validation commands

The benchmark harness requires Python 3 and NumPy; the downloader and summary
script use the Python standard library. Nsight is only needed to repeat the
profiles, not to run the solver.

```sh
cmake -S gpu -B gpu/build -DOCA_CUDA_ARCHITECTURES=89
cmake --build gpu/build --target oca_cuda test_rhs_diag -j2
flock /tmp/prism_gpu.lock gpu/build/test_rhs_diag
flock /tmp/prism_gpu.lock compute-sanitizer --tool memcheck \
  --error-exitcode 99 gpu/build/test_rhs_diag
python bench/download_bal.py --dest /workspace/bal --scenes venice-52 final-3068
python bench/profile_iterations.py \
  --reference /workspace/prism-results/baseline \
  --optimized /workspace/prism-results/optimized \
  --data /workspace/bal --out /workspace/prism-results/new-run \
  --scenes venice-52 final-3068 --reps 3 --max-iter 600 --config A
```

Run timing verdicts without profiling or sanitizer instrumentation. Freeze each
binary before benchmarking and use a fresh output directory when changing the
configuration. All new execution paths remain off by default because the full-run
results do not establish a consistently superior configuration.

Hardware counter collection with Nsight Compute was unavailable
(`ERR_NVGPUCTRPERM`); the kernel timings above come from Nsight Systems.
No memory-throughput or instruction-utilization counter claim is made.

## Completed kernel and bounded storm gates

The final numerical kernel gate passed CD=6 and CD=9, fp32/fp64 fragment
storage with fp64 accumulation, invalid factors, an empty camera and RHS-only
execution. The fused/reference discrepancies were below 7e-14 relative to
`1+abs(reference)`. The forward-norm comparison passed its 1e-10 tolerance.
Compute Sanitizer reported **0 errors** for the kernel gate and for full CLI
runs with 1, 7 and 17 shifts on ladybug-49 (2 outers, checkpoint 1).

In the 1.047M-observation synthetic test, the original diagonal takes 5.577 ms
and the forward-norm diagonal 3.164 ms (**43.3% less kernel time**). These are
CUDA-event timings without sanitizer instrumentation, not whole-solver speedups.
The camera-fused RHS+diagonal takes 6.319 ms versus 8.407 ms for the pair of
original kernels, but is slower on the 53-camera tests; it stays excluded from
the fixed conservative arm.

Config A final-4585, **60-outer budget**, N=3 interleaved:

| Implementation | Median solve wall | Observed range | Endpoint |
|---|---:|---:|---:|
| Original | 94.886 s | 94.875–94.898 s | 12,109,193.0709588 |
| Retry cache + batched scoring | 83.411 s | 83.401–83.473 s | 12,109,193.0709588 |

Both arms execute exactly 60 accepts, 454 rejects, 722 matvecs and 1,764
menu evaluations in each recorded run. The 480 alpha evaluations bring the total
to 2,244: **8.57 attempts and 37.4 cost evaluations per outer**. Comparing this
outer directly with a single-candidate LM iteration obscures the amount of work. The gain comes from less work per
attempt, not fewer attempted steps or candidates.

This is **12.1% less solve time**, with non-overlapping timing ranges and
endpoint agreement to approximately 3e-15 relative. It is a bounded workload
timing result, **not** a 600-outer quality verdict or a worst-case speed claim.
Full-budget results and both-direction crossings are in
[the results table](performance_results.md). Raw traces and manifests remain in
`/workspace/prism-results` and its experiment subdirectories.

The full-run repeats also expose substantial variation in this build. For
example, original Config A final-3068 in the forward-norm gate reaches
1,697,732 in 114.789 s in one run and 1,687,398 / 1,687,385 in 217.953 /
194.882 s in the other two. All input objective checks pass. The earlier
archive's near-determinism characterization therefore does not hold for these
repeats; neither the first fast control nor the deepest endpoint is selected
post hoc as the comparator. The full sample and both crossings are retained.

## Combined execution optimization on the storm workload

The fixed combination `OCA_RETRY_CACHE=1 OCA_MULTI_RHS=1 OCA_DIAG_NORM=1`
was additionally tested on Config A final-4585 at the same **60-outer budget**.
It shares all three controls from the earlier storm gate (same session, input,
original binary and configuration); these additional measurements are **not
interleaved** with those controls. The reuse is recorded in the manifest.

| Implementation | N | Median solve wall | Observed range |
|---|---:|---:|---:|
| Original, shared controls | 3 | 94.886 s | 94.875–94.898 s |
| Cache + batching + forward-norm diagonal | 3 | 70.830 s | 70.800–70.970 s |

This is **25.4% less solve time**. Every run has the same 60 accepts, 454 rejects,
722 matvecs and 1,764 menu evaluations; endpoints agree to floating-point noise
at 12,109,193.0709588. The optimization reduces execution work for the same
recorded sequence of decisions. It does not remove candidates or change the
point/camera damping policy. This remains a bounded workload result, with no
claim about the complete 600-outer endpoint or every BAL scene.

## Full-budget forward-norm gate

The same fixed cache + batching + forward-norm combination was run on three
scenes with Config A's 600-outer budget and quality stop, N=3 interleaved.

| Scene | Median cost change | Original median wall | Combined median wall | Observed timing ranges |
|---|---:|---:|---:|---|
| ladybug-1197 | −0.0485% | 35.750 s | 27.517 s | disjoint; combined faster |
| final-3068 | +0.4326% | 194.882 s | 118.014 s | overlap |
| venice-52 | +0.0175% | 31.289 s | 29.569 s | overlap |

All three cost ranges overlap, so none meets the protocol's criterion for a
resolved quality difference. The final-3068 median is nevertheless higher for
the combined arm: its shorter endpoint wall must not be advertised as an
equal-quality gain. The full traces and exact crossings make this visible.
These results support the kernel optimization and its bounded-workload gain,
but do not establish one universally faster end-to-end configuration.

A cost-model consistency check also explains the incremental gain. The
15-outer profiles put the forward-norm saving at approximately
`(8.510 − 5.730) / 109 = 25.5 ms` per rebuild. The cached 60-outer run performs
494 rebuilds, predicting about 12.60 s saved; adding the forward-norm kernel to
the measured cache/batching arm saves `83.411 − 70.830 = 12.581 s`. This is an
approximate consistency check against the profiles, not a separate timing
verdict. The full attempt-log comparison is recorded in
`/workspace/prism-results/storm-trace-audit.json` (the interleaved stderr CSV
announcement is removed before comparing the stdout attempt records).

## Completed full-budget conservative gates

The fixed cache + batching arm completed N=3 per arm on five Config A scenes
and five Config B scenes, including final-4585 under Config B. Every input's
independent initial objective check passed. The largest Config B cell has median
wall 1070.905 s original versus 802.501 s optimized (25.06% lower), with median
cost 0.0264% higher. The respective time ranges, 520.156–1282.168 s and
404.709–1055.359 s, overlap substantially. Only one of three optimized runs
crosses the original median endpoint. This does not establish an equal-quality
25% full-run speedup.

Other cells reinforce the limitation: conservative Config A has higher median
time on ladybug-1197 and trafalgar-257, while Config B final-3068 takes longer
and reaches a lower median cost. All conservative full-run timing ranges overlap,
and none resolves a cost difference under the prescribed criterion. Configuration
and floating-point trajectory changes can dominate the saved kernel work.

Recommendation: retain the safety and profiling corrections, and expose the
execution optimizations as opt-in. Use the combined flags for experiments on
retry-heavy workloads, with endpoint and common-cost checks. The next performance
question is how to reduce the measured 8.57 attempts and 37.4 cost evaluations
per outer while preserving quality; this study does not implement the open
problem's proposed algorithmic changes or claim to have solved convergence.
