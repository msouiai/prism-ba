# Compact FP64 fragment buffers — 2026-09-07

PRISM now fits the largest BAL case on the 16 GB RTX 2000 Ada while preserving
FP64 storage and the full-step guard. The preferred tested option is
`OCA_COMPACT_FRAGMENTS=2`; it removes the duplicate coupling store and streams
both GPU passes in camera order. Default remains 0 (the original two copies).

## Storage and numerical behavior

`Gp` and `Gc` previously held identical 27-double camera–point coupling values
per observation in two permutations. Mode 1 retains the point-major copy and
adds a camera-to-point slot map, so camera reads gather scattered values.
Mode 2 retains camera-major values, adds one camera ID per observation, and
streams both passes contiguously; point contributions scatter in camera order.
`Bo` and all arithmetic remain FP64. Damping, alpha search, backtracking,
rearming, and candidate selection are unchanged. Mode 2 changes the arrival
order of atomic sums, which was already nondeterministic; full trajectories
are not promised bitwise identical. The camera reductions retain their order.

On final-13682 (13,682 cameras, 4,456,117 points, 28,987,644 observations), either
mode saves exactly **6,145,380,528 bytes = 5.723 GiB**. The three largest
observation stores plus the new index use **7.235 GiB instead of 12.958 GiB**,
a 44.17% reduction for those buffers (not a measured whole-process percentage).
The previous guarded multi and single FP64 configurations both ran out of memory.
FP32 storage is explicitly rejected when compact mode is enabled, rather than
silently changing the numerical configuration. This option applies to the
pinhole shifted-CG solver; the separate rig/fisheye path is unchanged.

## Fixed-iteration runtime screens

N=1 per cell, no timing medians. Each layout has its own fresh reference run;
do not pool the two cohorts. Both use the selected guarded multi + rearm policy.

| Layout | Scene | Outer iterations | Old seconds | Compact seconds | Time change | CPU cost change |
|---|---|---:|---:|---:|---:|---:|
| 1 | ladybug-49 | 12 | 0.139669 | 0.148397 | +6.25% | -0.000145222% |
| 1 | dubrovnik-173 | 12 | 1.690817 | 2.962301 | +75.20% | +3.77249e-05% |
| 1 | final-4585 | 10 | 5.277853 | 10.480162 | +98.57% | +1.03828e-10% |
| 2 | ladybug-49 | 12 | 0.131447 | 0.123487 | -6.06% | +8.18365e-05% |
| 2 | dubrovnik-173 | 12 | 1.370897 | 1.461809 | +6.63% | -0.00127598% |
| 2 | final-4585 | 10 | 5.305277 | 5.948630 | +12.13% | -9.64562e-11% |

Mode 2 removes most of the first layout's overhead: on final-4585, mode 1 was
98.6% slower than its reference, while mode 2 was 12.1% slower. This is a memory
scalability improvement with residual runtime cost, not a universal speedup.
Atomic-order trajectory variation affects the smaller tests' work counts.

## Largest case: 30-second budget screen

N=1 per method/layout, including a fresh Caspar FP32 default run in each cohort.
Late candidates cannot commit, but an unfinished outer iteration can overshoot
substantially. Native solve clocks exclude parsing/audit and treat setup as in
[the prior fixed-policy comparison](fixed_policy_validation.md). These are not
hard 30-second return times or equal end-to-end latency measurements.

| Layout | Method | CPU FP64 final cost | Actual solve seconds | Overshoot seconds | Accepted | Rejected | Sampled GPU MiB |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | selected | 30,389,867.880 | 61.807 | 31.807 | 4 | 0 | 10868 |
| 1 | single | 30,577,317.532 | 46.313 | 16.313 | 11 | 0 | 10448 |
| 1 | caspar32 | 25,576,521.536 | 30.062 | 0.062 | 59 | 26 | 5776 |
| 2 | selected | 26,188,971.440 | 37.416 | 7.416 | 6 | 0 | 10868 |
| 2 | single | 25,967,052.572 | 33.277 | 3.277 | 14 | 0 | 10448 |
| 2 | caspar32 | 26,566,082.578 | 16.211 | 0.000 | 25 | 16 | 5776 |

For mode 2, selected multi's endpoint is -1.42%
relative to Caspar and +0.85% relative to single
(lower is better). Multi made 343 matvecs and single 228,
including unfinished over-budget work. Rearming fired 0 times in
the selected run, so do not credit the rearming feature for differences when
it did not activate. Memory values are sampled process usage, not certified
allocator peaks. Caspar remains FP32 with an epsilon-guarded projection;
PRISM is FP64 with raw-z projection. CPU scoring uses the common raw-z objective.
The same comparison caveats apply; this is not a matched-precision algorithm
ablation or a publication-grade superiority result.

Caspar in the mode-2 cohort stopped early at 16.21 s with exit reason 2
(`CONVERGED_DIAG_EXIT`): its damping exceeded the configured exit limit after
rejections. It did not use the full budget. The earlier largest-case screen
reached 25.21M and the mode-1 cohort 25.58M with this same frozen Caspar binary,
both below the mode-2 PRISM endpoints. Thus the last paired cell alone does
not establish PRISM superiority; it also exposes run/termination variability.
These prior endpoints are context, not a pooled median or a replacement for
the recorded fresh baseline.

## Validation and reproducibility

CLI and core library build successfully. Fixed-input tests cover both CD6 and
CD9, permutations of observation slots, empty cameras, invalid point factors,
camera pass2, fused RHS/diagonal, RHS-only, camera block Schur, and all scatter
consumers (single, multi-RHS, stride, RHS, both diagonal formulas, block Schur).
Camera gather tests are bitwise equal. Reordered scatter discrepancies are
at most 6.7e-15 under the test's absolute-error/(1+absolute-reference) metric.
Compute Sanitizer reports zero errors for both kernel gates and both compact
layouts on a real Ladybug49 solve. All 18 PRISM endpoints across the two
cohorts pass the independent CPU audit within 1e-7 relative; source/state/input
hashes and full logs are retained. End-to-end fixed-iteration checks remain
screens, not proofs against arbitrary trajectory variation.

Implementation: `gpu/oca_cuda.cu`; fixed-input gate:
`gpu/test_compact_fragments.cu`; reproducible driver: `bench/memory_screen.py`;
report generator: `bench/summarize_memory_screen.py`.
Artifacts: `/workspace/prism-memory/` (mode 1) and `/workspace/prism-memory-v2/`
(mode 2), each with frozen solver, source, protocol, manifests, exact exported
states, CPU audits, GPU samples, and results. The earlier failed baseline is
retained at `/workspace/prism-largest/`.

Example, with the existing policy flags also set:

```sh
OCA_COMPACT_FRAGMENTS=2 gpu/build/oca_cuda --problem /workspace/bal/final-13682.txt --algo mfree_shifted_cg --dof9 --zero_k2 --max_iter 20
```

Default off is retained because problems already fitting in memory may prefer
the original layout. No solver precision or policy defaults changed. Broad
experiments remain paused. Changes and reports are local, not pushed.
