# Ten-step backtracking investigation

**Guarded quadratic interpolation substantially improves Dubrovnik and Venice, but fails the large Final-4585 target that baseline reaches. There is no general replacement for baseline from this study.** `OCA_BACKTRACK_POLICY=3` remains opt-in, with solver defaults unchanged. It preserves the original first half-step and only interpolates after that step fails.

## Final guarded comparison

All times below measure the first accepted crossing of the same fixed cost target. The first three rows are medians of two interleaved repeats per arm; the large row is one run per arm.

| Scene | Target | Baseline | Guarded | Baseline / guarded | Hits baseline / guarded |
|---|---:|---:|---:|---:|---:|
| Ladybug-1197 | 366,600 | 2.990 s | 2.921 s | 1.024× | 2/2 / 2/2 |
| Dubrovnik-356 | 754,100 | 6.887 s | 2.615 s | 2.634× | 2/2 / 2/2 |
| Venice-52 | 252,000 | 4.421 s | 3.053 s | 1.448× | 2/2 / 2/2 |
| Final-4585 | 9,000,000 | 19.160 s | **Miss at 20 s budget** | — | 1/1 / 0/1 |

Final-4585 ends at cost **8,830,456.77** for baseline and **9,782,879.49** for guarded interpolation. The latter is 8.70% above the target; it is not a censored speedup estimate. Native solve-return times are 19.185 and 20.102 s respectively. The large case invalidates a claim of consensus across sizes.

The smaller-scene native solve-return medians are baseline/guarded: Ladybug **2.996 / 3.050 s**, Dubrovnik **7.061 / 2.625 s**, Venice **4.426 / 3.061 s**. In particular, Ladybug's tiny crossing-time gain becomes a tiny return-time loss: call it a tie at this sample size, not a proven speedup. Individual runs and both clocks are retained in the manifests/results.

| Scene | Backtracking probes baseline → guarded | Matvecs baseline → guarded | Total scores baseline → guarded |
|---|---:|---:|---:|
| Ladybug-1197 | 5 → 5.5 | 1,447.5 → 1,444 | 499.5 → 443.5 |
| Dubrovnik-356 | 839 → 41 | 799 → 388.5 | 1,368 → 282 |
| Venice-52 | 9 → 27 | 3,775 → 2,359.5 | 669.5 → 607.5 |
| Final-4585 | 38 → 55 | 419 → 401 | 234 → 245 |

Fractional counts are two-run medians. Dubrovnik removes **95.1%** of backtracking probes and **79.4%** of total scores while changing the trajectory. Venice's gain comes despite more backtracking probes, emphasizing that the optimization path matters more than a single work counter. The Final-4585 rows stop at different achieved quality and must not be interpreted as equal-quality work savings.

Across the full ten-step investigation: **44 runs, 175.203 seconds of native solve time, 26/27 target hits, all 44 exported states CPU-validated**, maximum relative objective discrepancy `3.39e-12`. The 17 non-target runs are traces or fixed-iteration screens. These totals exclude data parsing, CPU audits, builds and host tests.

## What the ten steps established

1. **Trace the bottleneck.** Short baseline traces on Ladybug-49, Dubrovnik-88, Dubrovnik-356, Venice-52 and Final-93. Three had no backtracking in the observed window. Dubrovnik-356 made 839 probes over 126 successful searches. These logging runs are diagnostic, not timing controls.
2. **Measure persistence and check prior art.** Dubrovnik accepted `alpha=1/128` in 114 searches; adjacent searches used the same successful scale in 119/125 pairs. Narrow and expanded menus both contribute to these counts, so they are not 125 independent nonlinear-iteration transitions. Interpolated Armijo line search is established practice: [Ceres documents Armijo, polynomial interpolation and contraction safeguards](https://ceres-solver.readthedocs.io/latest/nnls_solving.html). No novelty is claimed for interpolation itself.
3. **Implement history.** Separate narrow/wide records predict twice the previous successful scale. Changed camera/point damping or stale history resets the guess, and every eighth valid use restarts at the original half-step. This is a nonlinear step-size guess, not Krylov/operator reuse.
4. **Implement an independent quadratic alternative.** Fit the objective along the full BA direction using current cost, directional derivative and a measured failed candidate cost. Predict a smaller scale, with contraction safeguards, then map it to the existing dyadic menu.
5. **Validate.** Exhaustively test finite-menu coverage and uniqueness for lengths 1–12, all starting indices and modes; test recovery of an omitted larger successful step, invalid fits, damping/staleness resets and periodic full searches. Tests pass with AddressSanitizer and UBSan. Actual BA runs use complete objective acceptance, monotonic accepted-cost checks and independent CPU scoring of exported states.
6. **Screen two small scenes.** Two repeats each of baseline/history/quadratic, 40 outer iterations, on Ladybug-49 and Venice-52. Ladybug never used the new policies, making it a useful noise control. Venice median final cost was +0.33% with history and +2.33% with quadratic interpolation; both were within the predeclared 3% exploratory tolerance. Timing changes on the inactive control cannot be credited to the policies.
7. **Select using the hard case, then check equal quality.** History cut Dubrovnik probes 839→573 but target time only 6.889→6.685 s. Quadratic interpolation cut probes to 24 and target time to 2.349 s. A separate Venice target check hit with both methods (4.676 s baseline, 4.328 s quadratic), although quadratic's solver-return time was worse (5.359 versus 4.681 s); both clocks are retained.
8. **Repeat medium equal-quality comparisons.** Unguarded interpolation reproduced a 2.927× Dubrovnik speedup, but Ladybug median target time regressed 31%. All eight target runs hit. This mixed result ruled out treating the first large win as a universal improvement.
9. **Refine the guard and confirm it.** Before new runs, freeze mode 3: keep the first `alpha=1/2` probe and interpolate only after its failure. Repeat baseline/guarded twice on Ladybug-1197, Dubrovnik-356 and Venice-52. The recorded large-run gate requires all targets to hit, no scene >10% slower in median crossing time, and >10% improvement on Dubrovnik. It passed, permitting one Final-4585 pair at the existing target/cap. This amendment is recorded in `step9-amendment.json`; the earlier adverse results are retained.
10. **Record the decision and reproducibility evidence.** Retain all plans, versions, manifests, raw results and audits; build the CLI/core library, verify broad jobs remain paused, and leave the feature opt-in. These are exploratory results with two repeats on the smaller confirmation cases and one large pair, not a publication-grade benchmark.

## Search semantics

The original finite rescue menu is `1/2, 1/4, ..., 1/256` in this study. Modes 1–3 reorder that menu and may accept a different successful step; they do not preserve the original optimization trajectory. Each scale is evaluated at most once. If the predicted smaller scales all fail, omitted larger scales are tried before exhausting the same eight-evaluation budget. Thus a nonmonotone acceptance landscape cannot silently discard an original successful rescue merely because of the reordering, assuming identical finite objective evaluations.

For a failed scale `a`, objective `f(a)`, initial objective `f0` and negative slope `g`, the quadratic minimizer is `-g*a*a / (2*(f(a)-f0-a*g))`. The prediction is clamped to `[0.1*a, 0.5*a]` **before** rounding down to an available dyadic scale; the quantized contraction can therefore be stronger than 0.1. Invalid fits fall back to halving. Mode 2 also fits from the already-scored full step at `a=1`. Mode 3 waits for the actual half-step to fail, preserving easy half-step rescues. No extra matrix-vector product or GPU state buffer is introduced.

Acceptance still requires a finite full nonlinear cost that decreases the objective and satisfies the existing Armijo bound. Existing stop-confirmation logic is retained. Bounded-cost screening and Krylov reuse are off in this study. Floating-point atomics can still change CG trajectories between repeats, even on scenes where the experimental policy never fires.

## Reproduction

Source: `gpu/backtrack_schedule.h` and its integration in `gpu/oca_cuda.cu`. Options: `OCA_BACKTRACK_POLICY=0` baseline (default), `1` history, `2` unguarded quadratic, `3` guarded quadratic. `OCA_BACKTRACK_TRACE=1` logs per-probe context for diagnosis.

Runner: `bench/backtrack_investigation.py PLAN.json`. Summarizer: `bench/summarize_backtrack_investigation.py /workspace/prism-backtrack-ten`. Policy test: `g++ -std=c++17 -O2 -fsanitize=undefined,address bench/test_backtrack_schedule.cc -o /tmp/test-backtrack` followed by the executable.

Every run uses paired-demand mode 2, five shifts, full FP64 cost, compact fragment layout 2, the same established execution flags, and an independent CPU audit. Frozen source/binary versions, plans and all log/CSV/state/result files live under `/workspace/prism-backtrack-ten/`. `summary.json` includes both first target-crossing time and solver-return time, plus every failed or successful target run. The native clock includes initialization and excludes state export/CPU audit; caps are checked at solver boundaries and can overshoot. No Caspar run was made in this investigation.

## Interpretation and next step

Repeated failed **step lengths** were wasting work even when multishift CG successfully provided a direction. Guarded interpolation addresses that work without another Krylov sweep. On Dubrovnik it also changes subsequent accepted steps, so the end-to-end gain is a combination of fewer probes and a better observed optimization trajectory, not a pure cost-kernel speedup. Backtracking probes and rejected outer iterations are different quantities: the confirmed Dubrovnik baseline already had zero rejected outer iterations.

The immediate next hypothesis is that an accepted interpolated step can be unnecessarily small: the current recovery path checks omitted larger scales only if the smaller proposals fail. The Final-4585 logs establish slower quality progress, but do not prove that mechanism. A bounded follow-up should probe upward after a predicted success and measure whether retaining a larger, better Armijo-valid step recovers the large-scene progress without losing the Dubrovnik saving. Do not retune on a long large-scene run.

Once that behavior is reliable, give the same line-search policy to single-shift and paired multishift baselines on fixed equal-quality cases. That separates an ordinary line-search improvement from any benefit attributable to multishift selection. Repeated large comparisons and a precision/objective-matched Caspar benchmark remain necessary before publication claims.
