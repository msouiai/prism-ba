# Bounded backtracking cost screen

The first candidate-evaluation optimization does **not** show a convincing end-to-end win. Keep `OCA_BOUNDED_BACKTRACK` off by default. This is a short rejection-work screen, not a Caspar comparison.

## Change

Backtracking currently scores every proposed half-step over all observations. The opt-in plain-L2 path checks the accumulated nonnegative cost at the start of each CUDA block. Once it exceeds the Armijo rejection bound (plus a conservative `1e-10 * max(1, abs(bound))` roundoff margin), subsequent blocks skip projection. A partially evaluated candidate returns infinity and can only be rejected. Accepted candidates still receive complete objective evaluations. Robust losses and invalid bounds use the original path.

This keeps the candidate sequence, halving schedule and acceptance rule. It does not reduce the number of candidate calls, retractions, linear solves or retries. The floating-point reduction order remains nondeterministic; bitwise trajectory equivalence is not promised. The bound is rigorous for real nonnegative sums; the floating-point margin is conservative engineering protection, not a formal error bound.

`OCA_BOUNDED_BACKTRACK_AUDIT=1` independently computes the full GPU objective for every bounded call and aborts on an acceptance-decision mismatch or a material complete-cost mismatch. It is excluded from timed results.

## Short equal-quality results

Two interleaved repeats per arm, one shadow-audit run per scene first. Same binary, paired-demand mode 2, reuse off, five shifts, eight backtracking probes, compact fragment layout 2, FP64. Targets and caps were frozen before running: Ladybug 366,600 / 6 seconds; Dubrovnik 754,100 / 12 seconds. Native first accepted crossing includes solver initialization and excludes output/CPU audit. All eight timed runs reached their target within the cap.

| Scene | Baseline median | Bounded median | Baseline / bounded |
|---|---:|---:|---:|
| Ladybug-1197 | 2.7403 s | 2.9891 s | 0.917× |
| Dubrovnik-356 | 6.8877 s | 6.8405 s | 1.007× |

Individual crossings: Ladybug baseline 2.4991 / 2.9814 s, bounded 2.8268 / 3.1514 s; Dubrovnik baseline 6.9007 / 6.8747 s, bounded 6.8389 / 6.8421 s. Two repeats do not establish significance. Ladybug follows different atomics-sensitive CG trajectories; the observed 9.1% median time increase cannot be attributed solely to this kernel. Its bounded runs never skipped a block, so this mechanism provides no useful work saving there.

Dubrovnik provides the cleaner comparison: all timed runs have 85 accepted iterations, zero rejected outer iterations, 799 matvecs and 1,368 scores (393 menu, 136 alpha, 839 backtracking). Final costs agree within roughly `1e-5` absolute around 754,099.11763. Each bounded run rejects 361 backtracking probes early, but skips only **7.72% of backtracking observation blocks**. Most of the residual computation has already happened before the partial sum proves rejection. The remaining launches, synchronization and retractions still occur. The measured 0.7% gain is too small to call a reliable improvement.

## Validation and artifacts

The two shadow runs checked all 841 bounded calls (2 Ladybug, 839 Dubrovnik), with no acceptance-decision mismatches. All ten exported final states were independently scored on the CPU; maximum relative discrepancy was `5.09e-12`. Total native solve time across timed and shadow runs was 49.374 seconds.

The numerical CUDA gate covers an accepted candidate, equality at the bound, a near-bound rejection, strong rejection with actual skipped blocks, a partial final block, negative-bound and robust-loss fallback, and nonfinite projection. It passed under Compute Sanitizer with zero errors (six bounded calls, six full-cost audits, two early rejections). Both CLI and core-library builds passed.

Code: `gpu/oca_cuda.cu`; runner: `bench/bounded_backtrack_screen.py`. Artifacts: `/workspace/prism-bounded-cost/` contains frozen before/after source, binary, build logs, manifests, every run's log/CSV/state/CPU-audited JSON, `results.json`, and `summary.json`. Broad benchmark jobs remain paused. No solver defaults changed.

## Next implication

Most rejected work **cannot be certified until late in the observation traversal**, so this partial-sum bound has little opportunity to save work. These counts alone do not distinguish costs near the acceptance boundary from errors concentrated late in observation order. The next bounded experiment should address how many failed backtracking probes are proposed: use the previous successful backtracking scale as a starting guess, with a reset on changed damping/operator and safeguards against missing useful larger steps. That changes the search schedule and needs an explicit quality/retry comparison; it should not be presented as exact duplicate elimination. This screen does not justify a larger benchmark campaign or a default change.
