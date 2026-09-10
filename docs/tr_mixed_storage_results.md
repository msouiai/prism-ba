# TR mixed-storage investigation — 2026-09-09

The lead experimental TR configuration stores the compact cross blocks and point Jacobians in FP32 while retaining FP64 arithmetic, state, reductions, objective evaluation and full-model acceptance. It reduces Final1936 time to verified quality by 23% (1.30× speedup), improves Dubrovnik, and has a 1.6% median regression with substantial variability on Trafalgar. Keep it opt-in; this is a useful execution improvement, not a universal Caspar win or a new TR convergence theorem.

## Paired precision test

N3 per arm and scene, original BAL inputs, frozen quality targets and controller settings. These are uninstrumented native times to a target certified by an independently evaluated exported state. A miss has no imputed speed ratio.

| Scene | FP64 TR | FP32-buffer TR | FP32-buffer / FP64 runtime |
|---|---:|---:|---:|
| trafalgar-126 | 0.448s | 0.456s | 1.016× |
| dubrovnik-88 | 0.740s | 0.626s | 0.847× |
| final-1936 | 3.870s | 2.980s | 0.770× |
| final-13682 | 0/3 hits, 20s cap | 0/3 hits, 20s cap | — |

All nine runs on the three smaller scenes qualify in each arm; all three largest-scene runs miss in each arm. The candidate wins 6/9 individual smaller-scene pairs: 1/3 Trafalgar, 2/3 Dubrovnik, 3/3 Final1936. This is a small pilot, not a confidence claim over BAL scenes.

Trafalgar candidate crossings were 0.567, 0.456 and 0.434s. Its first slow run used 1,241 matvecs versus 888–890 in the other two; the median hides this tail. Dubrovnik likewise used 612 matvecs in its slow candidate run versus 476–477 in the others. Rounding can change the selected trajectory. Do not dismiss that variability as timer noise.

On Final13682, the median audited endpoint improves from 31,646,871.606 (15.8446% above the effective target) to 27,381,417.594 (0.2307% above it). The faster implementation commits a seventh successful step within the budget. An eighth attempt finishes after the deadline and is discarded. Both arms have zero rejected outer steps. Their approximately 22s actual solve times include the work that overshoots the 20s boundary-checked cap; neither is a successful time-to-target result.

## Caspar comparison

Two additional scenes were screened with the frozen mixed-buffer candidate and both pinned Caspar precisions, N1 per arm. These fresh screen results are not repeated estimates:

| Scene | Mixed-buffer TR | Caspar FP64 | Caspar FP32 |
|---|---:|---:|---:|
| ladybug-1197 | 5.045s | Miss (6s cap) | Miss (6s cap) |
| final-4585 | 7.103s | Miss (20s cap) | Miss (20s cap) |

Ladybug Caspar FP32 terminates early at roughly 0.279s, with audited cost 484,816 versus target 366,600. It did not consume its full cap and is not a fast equal-quality solve.

For context, the [preceding N3 Caspar comparison](fresh_tr_caspar_results.md) measured Final1936 Caspar FP32 at 2.681s and FP64 at 4.980s. The new mixed-buffer TR median is 2.980s, so FP32 Caspar remains faster there. These are separate batches, not a new interleaved three-arm N3 test on Final1936.

On Final13682, prior Caspar FP64 qualified 3/3 at 16.688s. FP32 qualified 2/3 at 8.073 and 8.275s; the third native crossing failed independent certification. A separately labelled stricter stopping-margin follow-up qualified 3/3 at 7.761s median. Mixed-buffer TR still misses the original 20s target. Caspar remains the leader on this largest scene. No overall winner is established.

## Where the time goes

Separate synchronized TR profiling runs (not timing samples):

| Scene | Assembly | Point factors + RHS | Krylov | Candidate timer | Total solver |
|---|---:|---:|---:|---:|---:|
| final-1936 | 0.458s | 0.606s | 2.123s | 0.081s | 3.886s |
| final-13682 | 2.605s | 3.008s | 13.722s | 0.447s | 22.708s |

The candidate timer does not include all full-GN model evaluation, TR bookkeeping, initialization and final diagnostics; do not infer that all scoring costs only 0.081s. Nsight on Final1936 attributes 32.0% of GPU kernel time to the first Schur pass, 27.9% to the second, 12.0% to assembly and 9.3% to direct full-model evaluation. The two operator passes dominate.

Caspar FP32 Nsight runs attribute 70.7% / 59.1% of GPU kernel time to its direct JᵀJ product on Final1936 / Final13682. The Final1936 product averages 4.89ms; TR’s first and second Schur passes average 6.55ms and 5.98ms, before the intervening point solve. These are different operators on different vector spaces, not equivalent operation counts. Caspar uses a joint-system product and has no separate Schur point-elimination phase.

The preceding uninstrumented Final1936 traces show TR reaching target with eight accepted steps and about 179–180 matvecs, versus Caspar FP32’s 15 accepted steps, five rejected steps and 386 PCG iterations. This supports prioritizing operator cost here. A Caspar PCG iteration must not be counted as the same work as a TR Schur matvec.

The Caspar profiling runs use a fixed 0.1% tighter native stopping threshold to avoid the previously observed FP32 false crossing. They are solely for kernel attribution; their instrumented wall times and iteration totals are not substituted into the primary benchmark.

## Precision and mathematical limits

Write the damped point block as Vτ, camera block as U and camera–point cross block as W. The reduced operator is S = U − W Vτ⁻¹ Wᵀ. The experiment stores W and the point Jacobian rows as float; it computes derivatives, sums, QR point factors, both operator passes, CG recurrences and state updates in double. It halves these stored arrays; it does not deliver native FP32 arithmetic throughput.

For fixed Vτ and rounded W + ΔW, the Schur perturbation is

```text
ΔS = −ΔW Vτ⁻¹ Wᵀ − W Vτ⁻¹ ΔWᵀ − ΔW Vτ⁻¹ ΔWᵀ.
```

Rounding point Jacobians also perturbs Vτ. Small damping or an ill-conditioned point block can amplify these errors. Because U, W and Vτ are no longer rounded as one common Jacobian product, exact positive semidefiniteness is not guaranteed by the original Gram-matrix argument. Keeping FP64 accumulation does not restore lost storage bits. Existing negative-curvature handling and actual nonlinear/full-model acceptance remain active. Passing endpoint and recurrence audits is empirical evidence, not a global error bound.

The recurrence curvature audit compares the CG identity with an explicit application of the same stored operator. It checks recurrence consistency, not agreement of the rounded operator with the original FP64 operator.

A targeted ablation kept point Jacobian storage FP64 while retaining float W. It did not fix the variability or produce a clear advantage:

| Scene | Paired FP64 control | W32 / point64 |
|---|---:|---:|
| trafalgar-126 | 0.480s | 0.487s |
| dubrovnik-88 | 0.716s | 0.628s |
| final-1936 | 3.864s | 2.981s |

This separate N3 ablation has its own paired controls. It does not isolate W-only and all-float timing differences to high confidence across batches. Both variants retain small-scene trajectory variability; point precision alone is not a demonstrated remedy.

Compact W plus point Jacobian storage shrinks from 264 to 132 bytes per observation. On Final13682 this saves 3,826,369,008 bytes (3.564 GiB) in those allocations. This is an allocation calculation, not a measurement of whole-process peak VRAM.

## Validation and reproducibility

All 63 exported endpoints were independently re-audited: 58 experiment endpoints and five profiling endpoints. Maximum agreement error against the respective independent/native checker is 1.17e-10. There were 650 accepted TR feasibility checks, 589 checks of actual/predicted reduction (maximum relative discrepancy 1.24e-12), and 211 explicit-versus-recurrence curvature checks (maximum discrepancy 9.13e-11, threshold 1e-7). No process failures. Target misses remain misses.

The 58 experiment runs consumed 255.908s of native solver time, excluding the separately labelled profiles, input processing, auditing and any GPU-lock wait. GPU runs were serialized. All 11 pre-existing paused jobs remained paused. Process wall times include lock waits and unequal input/auditing scopes and are not comparable application latency.

Both generated solver sources reproduce byte-for-byte from the final repository builder. The existing production solver and packaged FP64 candidate remain unchanged. Research entry points:

- `bench/build_tr_mixed_storage.py`: isolated build; `--point-double` for the ablation, `--source-only` for source reproduction; refuses existing output.
- `bench/tr_mixed_study.py`: N3 paired timing, seven-iteration audit and full-target curvature audit.
- `bench/tr_mixed_caspar_screen.py`: the two additional N1 three-arm comparisons.
- `bench/profile_tr_caspar_kernels.py`: separate Caspar CUDA traces.
- `bench/verify_tr_mixed_study.py`: endpoint/hash/acceptance/curvature audit.
- `bench/write_tr_mixed_report.py`: this report.

Artifacts, binaries, exact commands/flags, input hashes, sources, endpoint states, CUDA traces, logs and JSON summaries: `/workspace/prism-tr-mixed/`. The lead executable is `/workspace/prism-tr-mixed/storage/prism-tr`. It runs with the frozen flags in `timing/protocol.json`; it is an opt-in camera TR build, not the production `--mf-fp32` mode.

## Decision and next bottleneck

Retain the all-float storage build as the lead memory-saving TR prototype. A low single-digit median regression alone does not justify discarding a 23% improvement on Final1936, but the slow tails must remain visible. Do not replace the default or claim reliable scene-wide superiority from N3.

The largest-scene trace identifies a concrete next target: outer iteration 6 spends 128 CG iterations but ultimately selects the depth-64 direction, then applies a point safeguard. FP32 storage makes that attempt fit inside the cap; the following attempt still finishes too late. Test a residual/model-gap stopping certificate at saved depth-64 states before shortening solves globally. More precision reduction is a separate hypothesis, since this experiment retained FP64 arithmetic. No matched-state full-space residual/preconditioner study or native FP32 arithmetic implementation was performed in this batch.
