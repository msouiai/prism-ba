# Reference ranking and Schur accumulation — 2026-09-09

**Verdict: guarded projected TR remains the large-scene PRISM winner; Caspar FP32 remains faster.** Reference ranking restores the 96-step inner stop, but its nonlinear winner misses the large-scene target within budget. Nine point-owned accumulation variants pass accuracy checks, but none beats the existing first pass.

## Reference-based ranking

The previous FP32-products prototype discarded projected candidates when the reconstructed reduced model disagreed with a reference FP64 Schur product by more than 1e-7. The new candidate treats the reduced model as a proposal generator. The reference product, already computed, supplies prediction `b^T x - 0.5 x^T S x`, gradient `S x - b`, curvature, and the existing FW-gap stopping measure. Step norm is measured explicitly.

Only finite, radius-feasible proposals with positive reference prediction enter the bank. Reference-residual checks/fallback and full nonlinear acceptance remain. Reduced-model disagreement is diagnostic. The FW measure is a convex-model bound only if the reference Schur operator is PSD; this is not an unconditional global certificate.

This explicitly changes a ranking policy; it does not relax nonlinear acceptance. The candidate starts from the reliable FP32-products prototype. Comparisons below are against guarded TR, so differences combine precision, reference-check costs and ranking policy; they do not isolate ranking alone.

### Small/medium paired timing

Three repeats per arm, alternating order, original-observation FP64 endpoint audits. No diagnostic trace in timed runs; mandatory reference checks are charged.

| Scene | Guarded TR median | Reference-ranking median | Time change | Paired wins |
|---|---:|---:|---:|---:|
| Trafalgar-126 | 0.48295 s | 0.43013 s | -10.9% | 3/3 |
| Dubrovnik-88 | 0.77586 s | 0.61824 s | -20.3% | 3/3 |
| Final-1936 | 2.98774 s | 3.13914 s | +5.1% | 0/3 |

All 18 timed endpoints qualified. A separate four-run diagnostic screen also qualified. N=3 is a screen rather than strong statistical evidence.

### Largest scene: fresh bounded N=1

| Arm | Time to audited target | Endpoint cost |
|---|---:|---:|
| Guarded projected TR | 16.33400 s | 27,232,344.420 |
| Reference-ranking FP32 products | Missed 20 s | 27,391,032.363 |
| Caspar FP32 | 8.34879 s | 27,282,129.214 |

Target: 27,318,392.35812812 (nominal times 1-1e-8). Caspar FP32 retains the fixed 0.1% tighter native stopping margin and receives credit only at that stricter crossing after original-observation endpoint qualification. Solver-native timing excludes CLI loading, with existing differences in solver-local setup inclusion; these are not application latency measurements. Do not infer a Caspar regression from this single run versus earlier 7.79 s results.

The ranking candidate finishes the seventh inner solve after **96 steps**, restoring the early stop. Its bank contains projected candidates, but final nonlinear selection still chooses **legacy shift 0, depth 64**. Seven steps are accepted, zero rejected; the seventh endpoint remains above target. An eighth attempt is computed but not committed when the boundary budget check fires. Recorded products: 267. Native time: 22.786483 s, including boundary overshoot. No equal-quality speed ratio is assigned to the miss.

Reference ranking resolves the reduced-model disagreement gate, but does not guarantee that the nonlinear winner is the projected direction or preserve the incumbent's useful nonlinear trajectory. Selection/safeguarding interactions deserve inspection if this branch resumes; the log alone does not establish their complete causal contribution.

## Hardware-counter attempt

Nsight Compute targeted only the two reference Schur kernels in the saved fixed system, requesting SpeedOfLight, MemoryWorkloadAnalysis, ComputeWorkloadAnalysis and SchedulerStats. The driver denied access with **ERR_NVGPUCTRPERM**. No counter measurements were obtained and no driver settings were changed. An initial invocation matched no kernels; both that log and the corrected invocation's permission error are retained.

The results below establish timing and accuracy, not a hardware-counter decomposition of bandwidth, atomics or instruction stalls.

## Point-owned accumulation

The reference first pass reads camera-major float fragments, computes observation products in FP64 and scatters three FP64 atomic sums per observation. Two alternatives preserve FP64 arithmetic and change accumulation order:

- Direct point ownership: 1, 8 or 32 lanes per point gather fragments using CSR observation slots and write a unique result per point.
- Two-stage ownership: contiguous fragment reads produce three FP64 values per observation, then groups of 1, 2, 4, 8, 16 or 32 lanes reduce them by point.

Each variant was compared with the complete reference Schur application on four saved projected directions (depths 16, 32, 64 and 128) from one large-scene linearization. Each timing cell is the median of five CUDA-event measurements; figures below are medians across four directions. Baseline includes output zeroing; staged versions include both kernels.

| Variant | First-pass median | Ratio to paired reference |
|---|---:|---:|
| Reference | approximately 26.57 ms | 1.000x |
| Direct, 1 lane | 178.58 ms | 6.719x |
| Direct, 8 lanes | 88.72 ms | 3.338x |
| Direct, 32 lanes | 138.59 ms | 5.215x |
| Two-stage, 1 lane | 30.27 ms | 1.139x |
| Two-stage, 2 lanes | 28.60 ms | 1.077x |
| Two-stage, 4 lanes | 27.71 ms | 1.043x |
| Two-stage, 8 lanes | 28.79 ms | 1.083x |
| Two-stage, 16 lanes | 34.24 ms | 1.289x |
| Two-stage, 32 lanes | 49.38 ms | 1.858x |

All **36 candidate operator checks** passed. Maximum `norm(candidate-reference)/norm(b)` was **1.546e-14**. There were 48 timing cells including reference repeats. The reference kernels are extracted from the frozen guarded source; source and binary hashes are recorded for all three benchmark builds.

Direct ownership loses badly with the camera-major layout. Staging restores contiguous fragment reads, but the best four-lane version is still **4.3% slower**, requiring a 695,703,456-byte (~0.648 GiB) product temporary plus point-slot mapping storage. A full solver integration could reuse point offsets but would need mapped camera slots (~0.108 GiB). These candidates stop at the fixed-system gate; full BA integration/testing is not justified.

The local-product stage measured 18.912 ms and the eight-lane reduction stage 9.871 ms separately. These are different kernels/cache contexts; their difference from the baseline is not a pure atomic-contention measurement.

## Validation and reproduction

25 completed BA endpoints independently audited. No BA process failures. Accepted TR log entries checked for finite positive prediction, radius feasibility and rho >= 0.1. Completed BA native time: 75.413 s, including diagnostics and budget overshoot; excludes build/load/audit, fixed-system timing and profiling attempts.

Artifacts: `/workspace/prism-tr-reference/`, including `rank-audit`, `rank-timing`, `large`, `fixed`, `fixed-staged`, `fixed-tuned`, and `verification.json`. Historical harness labels `double` and `storage` mean incumbent and candidate.

Code:

- `bench/build_tr_reference_rank.py`: isolated ranking binary from frozen reliable FP32-products source/headers.
- `bench/tr_reference_study.py`, `bench/tr_reference_large.py`: bounded endpoint-audited comparisons.
- `gpu/point_owned_schur.cuh`: nine experimental FP64 accumulation variants.
- `bench/fixed_schur_bench.cu`, `bench/build_fixed_schur_bench.py`: fixed-system CUDA accuracy/timing harness; use fresh `--output` paths. `--staged` and `--tune` select variant subsets.
- `bench/summarize_tr_reference.py`: build integrity, acceptance checks and summaries.

All GPU work used the existing serialization lock. Counter collection needs a host configuration permitting NVIDIA performance counters. The production solver was unchanged and paused jobs were not resumed.

## Decision

Retain guarded projected TR for large-scene PRISM comparisons. Keep reference ranking as an opt-in research policy with small-scene benefits, not a universal improvement. Preserve the accumulation kernels and negative results without promoting them. Further execution work needs permitted counters or a focused new access-pattern hypothesis; removing atomics alone has not produced a win here.
