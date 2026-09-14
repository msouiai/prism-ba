# FP32 fragment confirmation protocol

Registered 2026-09-14 before generating inputs or running either arm.

Both arms use the complete deterministic B6v7 derivative, the frozen Eta2
configuration, full FP64 state/arithmetic/acceptance and independent FP64
endpoint scoring.  They differ only in stored Jacobian fragments: FP32 versus
FP64. This confirms the already-FP32 frozen champion precision choice; it is
not a public option default change. Rig problems and rig defaults are explicitly
outside scope.

For each scene and repetition, PCG64 seed `910000 + 100*scene_index + rep`
generates one field-scaled BAL perturbation at epsilon `1e-10`. Both arms read
the exact same bytes. Arm order alternates by repetition. N=3 pairs are run on:

| Scene | Target | Cap |
|---|---:|---:|
| Ladybug49 | 13591.568354279514 | 5 s |
| Final3068 | 1744796.9841897595 | 45 s |
| Final4585 (largest feasible) | 7075838.613048037 | 60 s |

Dubrovnik356 is reserved as a replacement medium cell if Final3068 cannot run;
it will not be added after observing results. Final13682 is excluded because an
FP64-fragment allocation is unlikely to fit the 16 GiB device; Final4585 is the
largest preregistered feasible cell at 9,125,125 observations.

Primary outputs are paired target hit and FP64/FP32 target-time ratio on double
hits. Report every hit/miss and time range. FP32 passes confirmation if no scene
has a median target-time regression above 2%, endpoint audit error stays below
1e-6 relative, and it does not lose more than one hit of three in any cell.
The hit rule is a descriptive N=3 screen, not a 15-point noninferiority claim.
At least one double hit per scene is required to evaluate timing; otherwise the
timing gate is inconclusive. Algebraically, the 2% bound requires the reported
FP64/FP32 ratio to be at least `1/1.02`.
This N=3 confirmation does not supersede Wave-6 D3's N=35 Final3068 inference.
