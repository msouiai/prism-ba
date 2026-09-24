# Direct full-model prediction: large-scene transfer

2026-09-08. **The medium-scene single-shift improvement did not transfer to Final-4585.** Keep the correction opt-in; there is no case yet for promoting it or optimizing its extra pass. This is a short transfer screen, not a convergence benchmark.

The [previous mathematical investigation](point_trust_results.md) found single-shift improvements on two medium scenes. This follow-up uses the identical frozen `prism-v2` binary, one predeclared large scene, and the existing target cost of 9,000,000 with a 20-second native budget per arm. Final-4585 has 4,585 cameras, 1,324,582 points and 9,125,125 observations.

## Results

| Configuration | First time to target | Returned cost | Matvecs | Backtracking evaluations |
|---|---:|---:|---:|---:|
| Fixed single shift, original prediction | **7.507 s** | 8,891,388 | 107 | 25 |
| Fixed single shift, direct full prediction | **Miss**; returned at 20.258 s | 9,352,772 | 344 | 132 |
| Fixed five shifts, original prediction | 9.147 s | 8,995,528 | 172 | 35 |
| Fixed five shifts, direct full prediction | 9.390 s | 8,995,528 | 172 | 35 |
| Paired demand mode 2, original prediction | 19.226 s | 8,830,466 | 419 | 38 |

One run per configuration. Four of five runs reached the target; the corrected single-shift miss has no measured equal-quality speedup. Five-shift correction was 2.7% slower with the same work counts, a small difference that does not establish an optimization-trajectory regression. Original single shift was the fastest configuration tested here.

Times are native first-target crossings, include initialization and prediction overhead, and exclude final cleanup and independent CPU auditing. Budgets are checked at iteration/commit boundaries, so return times can exceed the nominal cap. The failed arm stopped before committing an additional step. Counts include work done before that budget stop. All configurations had zero rejected attempts; backtracking rescues can still be frequent.

## What failed, and what did not

The direct prediction remains the correct unregularized GN model quantity for the actual step, within numerical error. This result shows that substituting it into the existing hybrid damping controller does not guarantee faster optimization. The mathematical calculation and the policy consuming it are separate questions.

In corrected single shift, seven prediction passes took only **0.545 s** of the 20.258 s solve. Removing that cost alone would not explain the gap to the 7.507 s original. Matvecs rose from 107 to 344 and scoring calls from 100 to 230. Accepted steps rose from 18 to 41 without reaching equal quality.

The single-shift trajectories match through accepted iteration 6 to roundoff. At outer index 5, the logged actual reduction is 4,153,586.885, the old prediction 1,985,960.088 and the direct prediction 5,149,104.298. The corresponding rho values are approximately 2.091 and 0.807. Under the existing update and relative-gain override, the old calculation decays lambda by 1/3 whereas the corrected calculation decays it by 1/2. Subsequent trajectories diverge.

After accepted iteration 12, corrected single shift stays at camera lambda approximately 0.02315 through iteration 41. No further direct prediction calls occur in that interval: the rescued-step branch freezes lambda and bypasses the rho update. This observed interaction is a concrete mechanism to investigate, not proof that changing the freeze rule will solve the problem. Earlier attempts to infer camera damping directly from the rescue scale failed because camera-only damping cannot necessarily shrink the common point relaxation.

In five-shift mode, both versions used 15 accepted steps, 172 matvecs and 154 scoring calls. Three direct passes cost **0.234 s**, close to the 0.243 s difference in target-crossing time. Their endpoints differ by only about 0.0075 cost units. The evidence is consistent with overhead without a useful trajectory change in this case; one timing pair cannot isolate overhead precisely.

No direct model predictions were nonpositive. The original single-shift calculation had negative predictions during its opening steps; replacing those values did not immediately change the lambda trajectory because both updates reached the same decay bound.

## Protocol and checks

The five arms, target and budget were frozen before execution in `/workspace/prism-full-model-large/PROTOCOL.md` and `screen-plan.json`. Fixed-menu arms use one/five shifts with direct prediction off/on; the paired control uses demand mode 2 with the original prediction. All use FP64 unshared 9-parameter cameras, L2, zeroed k2, compact fragments 2, original bounded backtracking, and point feedback off. Direct prediction is intentionally incompatible with paired demand mode because that mode overrides the camera update.

The predeclared repeat gate required a corrected arm to hit and improve its matched control by over 10%, or hit when its control missed. Neither arm qualified; no repeat or threshold tuning followed. Total native solver time was 65.623 s. Every endpoint passed the independent CPU objective audit, with maximum relative discrepancy `7.37e-15`; monotonic accepted cost and bounded backtracking checks passed. Manifests retain binary/data hashes, commands and flags; `summary.json` also hashes the manifests, result files and exported states. The binary matches the previous tested source, so no implementation rebuild or repeated numerical unit test was needed.

All 11 broad-queue processes remain paused, verified by process identity and start time. No defaults changed and no GitHub publication or new Caspar comparison was performed.

To reproduce into a fresh output root, copy and update `screen-plan.json`, then run:

```sh
python3 bench/backtrack_investigation.py /path/to/copied-plan.json
```

## Decision

Do not optimize or promote this prediction correction based on the medium results alone. Retain the independent direct prediction as a diagnostic reference. The next useful experiment would isolate the frozen-damping rescue sequence on saved small linearizations and derive a consistent coupled damping/radius update before another end-to-end policy sweep. A correct rho denominator is necessary for interpreting rho, but it does not repair the remaining heuristic update rules or establish a multi-shift advantage.
