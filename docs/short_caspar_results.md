# Short PRISM versus Caspar comparison — 2026-09-08

**On these two sampled scenes and quality targets, PRISM single shift and paired demand succeed consistently; Caspar FP32 defaults do not. Fixed multi-shift remains scene-dependent.** This is a 16-run, two-repeat implementation screen, not a general algorithm superiority claim.

Two previously studied contrasting BAL instances, unchanged targets and short native budgets:

- Ladybug-1197: CPU raw-z cost ≤366,600, 6 seconds.
- Dubrovnik-356: CPU raw-z cost ≤754,100, 8 seconds.

Four arms per scene, two repeats, with scene/method order reversed for repeat two. Total native solver time: **66.137 seconds**. Data parsing, independent CPU scoring and final state export are outside native timing. No large scene or new pointwise safeguard is included.

## Time to independently validated target

Medians are shown only when both runs qualify. Misses are retained; no cap-based speedup is computed.

| Implementation | Ladybug-1197 | Hits | Dubrovnik-356 | Hits |
|---|---:|---:|---:|---:|
| PRISM fixed single shift | **2.849 s** | 2/2 | 4.722 s | 2/2 |
| PRISM fixed five shifts | Miss | 0/2 | **1.617 s** | 2/2 |
| PRISM paired demand | **2.536 s** | 2/2 | 6.874 s | 2/2 |
| Caspar FP32 defaults | Miss; stopped early | 0/2 | Miss at cap | 0/2 |

Single shift is the simplest tested PRISM configuration that reaches both targets. Paired demand is faster on Ladybug but slower on Dubrovnik. Fixed five shifts are fastest on Dubrovnik and fail the Ladybug target. No post-hoc per-scene winner is presented as one universally superior PRISM configuration.

## Endpoint quality and stopping

Median independently scored endpoints and native return times:

| Scene | Arm | CPU final cost | Native return time |
|---|---|---:|---:|
| Ladybug | Single | 366,572 | 2.854 s |
| Ladybug | Multi | 367,014 | 6.122 s |
| Ladybug | Paired | 366,568 | 2.544 s |
| Ladybug | Caspar FP32 | **484,812** | **0.282 s** |
| Dubrovnik | Single | 754,052 | 4.732 s |
| Dubrovnik | Multi | 752,606 | 1.634 s |
| Dubrovnik | Paired | 754,099 | 6.896 s |
| Dubrovnik | Caspar FP32 | **1,154,072** | **8.004 s** |

Caspar's Ladybug run stops at its damping-limit exit, rather than using the entire 6-second allowance. Its early return is not an equal-quality speed advantage. Caspar runs to the 8-second budget on Dubrovnik. Budget checks can cause small return-time overshoots; unfinished overbudget candidates are discarded by the existing harness.

Both methods are checked on the same CPU raw-z objective from serialized returned states. Caspar's native Ladybug score is about **455,325**, versus raw CPU cost **484,812**, a **6.08%** gap. Both are above the target, so its miss is not a borderline target-classification issue. The gap is material and retained explicitly. Its Dubrovnik native/raw gap is below `4.8e-7` relative.

PRISM uses FP64/raw-z arithmetic; Caspar uses its native generated FP32 implementation and projection safeguard. Consequently these are practical implementation results, **not a matched-precision, identical-arithmetic algorithm ablation**. The numerical gap alone does not isolate which arithmetic/projection operation causes the divergence. Caspar FP64 was not tested in this short screen.

## Timing and driver changes

The Caspar driver exposes the existing `SolverParams.score_exit_value` through optional `CASPAR_TARGET_COST`; its solver update rules and defaults are unchanged. It stops on its native objective, then the exported endpoint must also satisfy the shared CPU target. PRISM uses its existing target hook. Reported crossings are timestamps of the terminating qualifying state, not a claim about Caspar's earliest possible raw-z crossing among unexported intermediate states.

`CASPAR_STATE_OUT` writes returned float poses/points as exact double values, with the BAL rotation/translation convention restored, for the same independent Python scorer used by PRISM. No normalization or optimization of the exported state is introduced.

Caspar graph setup takes approximately **0.214 s** on Ladybug and **0.227 s** on Dubrovnik (medians), excluding initial CPU auditing. Its setup-inclusive return times are therefore approximately **0.496 s** and **8.231 s**, still without meeting the targets. PRISM's native clock already includes its solver initialization; data preparation boundaries are not perfectly identical. Because Caspar has no validated crossings here, there are no setup-inclusive target speedup ratios to report.

## Verification and scope

- All **16 exported-state CPU audits pass**. Maximum discrepancy against the independent driver/solver CPU-equivalent reported cost is `1.18e-10`. This audit discrepancy is distinct from Caspar's larger native/raw objective gap above.
- Caspar target-stop and state-export smoke checks pass on Ladybug-49 before the screen.
- Binary/data hashes, exact commands, flags, states, native traces and every result are retained under `/workspace/prism-caspar-short/`. `plan.json` and `PROTOCOL.md` freeze the sample, arms and execution order.
- PRISM uses the frozen current audited binary with compact FP64 mode 2, original backtracking/rearm, and experimental subspace/pointwise/full-rho variants off. Caspar uses the same pinned generated FP32 backend as the earlier local comparison, with the native default profile (20 PCG iterations, initial damping 1, relative PCG tolerance 1e-4).
- Two repeats and two already-studied scenes are a short screen. These results do not establish performance on all BAL instances, publication-level novelty, or the value of the unimplemented pointwise GPU safeguard.
- Broad jobs remain paused, solver defaults remain unchanged, and nothing was pushed to GitHub.

Reproduction driver: `bench/short_caspar_comparison.py`. The Caspar driver additions are in `bench/caspar/caspar_bal32_checked.cc`; frozen driver/backend source and benchmark binaries are retained with the results.

**Verdict:** PRISM currently delivers the requested quality more reliably on this selected two-scene comparison. We can state that directly, while continuing to withhold a universal speedup or a claim that multi-shift consistently beats single shift.
