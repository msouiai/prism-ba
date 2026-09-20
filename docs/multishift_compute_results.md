# Multi-shift compute investigation: implementation and results

2026-09-07. All changes remain opt-in; the broad benchmark queue stays paused. These are bounded exploratory comparisons, not a publication verdict or a new Caspar comparison.

Timed work: 49 runs, 0 failures, 5.43 cumulative solver minutes. Diagnostic, profiling and capture runs are separate.

## 1. Progressive Krylov depth

`OCA_PROGRESSIVE_DEPTH=1` checks the central shifted residual against the existing Eisenstat–Walker target. At its first crossing, it scores all current shifts that were not already scored at that depth. It stops the sweep only if a finite accepted candidate reduces true cost by more than `max(1e-4, 10*ftol)` relative. Otherwise, it continues the existing CG ladder. Curvature checks, true-cost acceptance, alpha search and the existing post-sweep Armijo safeguard remain in place. It does not impose a fixed depth cap or add an early backtracking probe. This changes both scoring coverage and the work policy.

Initial prototype (V1). Three contrasting smaller scenes: 60 outer iterations, N=2 per arm, same frozen binary, rotating arm order, serial GPU. Large transfer: final-4585, 20 outers, N=1. Each process has a 60-second cap after acquiring the GPU lock. All use Config A, cached factors, multi-RHS scoring and diagonal norm optimization; backtracking has eight probes.

| Scene | Arm | N | Seconds, median | Final cost, median | Matvecs | Retries | Total scored |
|---|---|---:|---:|---:|---:|---:|---:|
| dubrovnik-173 | single | 2 | 5.463 | 374,958.39 | 2615 | 12.5 | 392 |
| dubrovnik-173 | multi | 2 | 6.072 | 374,908.68 | 2808.5 | 15 | 785.5 |
| dubrovnik-173 | progressive | 2 | 5.376 | 374,885.86 | 2301.5 | 0 | 817 |
| ladybug-1197 | single | 2 | 6.503 | 366,289.69 | 3490.5 | 0 | 629 |
| ladybug-1197 | multi | 2 | 12.747 | 366,607.53 | 6977 | 99.5 | 1647.5 |
| ladybug-1197 | progressive | 2 | 7.019 | 365,919.28 | 3523.5 | 7 | 1424.5 |
| venice-52 | single | 2 | 4.538 | 259,447.05 | 3656.5 | 0 | 634 |
| venice-52 | multi | 2 | 6.581 | 255,498.29 | 5476.5 | 0 | 1082 |
| venice-52 | progressive | 2 | 4.733 | 249,942.98 | 3580 | 0 | 1333 |
| final-4585 | single | 1 | 8.250 | 8,842,123.00 | 139 | 0 | 114 |
| final-4585 | multi | 1 | 11.750 | 8,492,146.75 | 249 | 0 | 217 |
| final-4585 | progressive | 1 | 14.148 | 8,079,598.61 | 293 | 0 | 287 |

Relative to existing multi-shift, progressive depth is faster on all three small screens and has equal or lower median endpoint cost. N=2 does not resolve a formal speed verdict; Venice baseline variation is substantial. Guarded single shift remains competitive and is often fastest at looser quality targets. The large run takes longer at a fixed outer budget but reaches a lower endpoint, so compare cost-matched times too.

### Quality bands

For this exploratory table only, the reference is the lowest median endpoint cost among the three arms on that scene. Targets are 1%, 3%, 5% above that reference. Values are median first recorded outer-boundary crossing times when every repeat reaches the target; `reached x/N` retains failures to reach within the cap. These retrospective references are not certified optima.

| Scene | Arm | Within 1% (s) | Within 3% (s) | Within 5% (s) |
|---|---|---:|---:|---:|
| dubrovnik-173 | single | 0.605 | 0.490 | 0.387 |
| dubrovnik-173 | multi | 1.065 | 0.767 | 0.361 |
| dubrovnik-173 | progressive | 0.894 | 0.340 | 0.340 |
| ladybug-1197 | single | 0.744 | 0.440 | 0.295 |
| ladybug-1197 | multi | 1.800 | 0.860 | 0.710 |
| ladybug-1197 | progressive | 0.893 | 0.608 | 0.487 |
| venice-52 | single | reached 0/2 | reached 0/2 | 2.863 |
| venice-52 | multi | reached 1/2 | reached 1/2 | 1.729 |
| venice-52 | progressive | 2.696 | 1.771 | 1.188 |
| final-4585 | single | reached 0/1 | reached 0/1 | reached 0/1 |
| final-4585 | multi | reached 0/1 | reached 0/1 | reached 0/1 |
| final-4585 | progressive | 11.624 | 11.196 | 10.160 |

Large cost-matched check: progressive reaches the existing multi-shift endpoint (8,492,146.75) in 9.170s versus 11.662s (21.4% sooner). N=1; this is not an independently CPU-audited endpoint.

### Isolating scoring from early stopping

`OCA_PROGRESSIVE_DEPTH=2` performs the same central-convergence scoring probe but continues the sweep. The following separate frozen-binary cohort uses N=1 per arm with the same 60/20 outer caps. It isolates the early-stop intervention; do not pool these timings into the earlier N=2 medians. This corrected V2 skips a redundant terminal menu when its exact candidates were already scored by the probe. The earlier V1 probe-only ablation is retained under `probe-screen` / `probe-large`, and is included in total experimental work but not pooled into this table.

| Scene | Arm | Seconds | Final cost | Matvecs | Retries |
|---|---|---:|---:|---:|---:|
| dubrovnik-173 | probe-only | 5.407 | 374,887.31 | 2344 | 0 |
| dubrovnik-173 | progressive | 4.678 | 374,905.05 | 1939 | 0 |
| ladybug-1197 | probe-only | 9.132 | 368,134.84 | 4743 | 27 |
| ladybug-1197 | progressive | 6.886 | 365,901.24 | 3479 | 7 |
| venice-52 | probe-only | 4.769 | 253,749.31 | 3624 | 0 |
| venice-52 | progressive | 4.748 | 249,936.65 | 3597 | 0 |
| final-4585 | probe-only | 13.011 | 8,474,217.40 | 244 | 0 |
| final-4585 | progressive | 13.879 | 8,079,598.89 | 293 | 0 |

The corrected small-case ablation supports useful early stopping: Ladybug has fewer retries and lower cost; Dubrovnik trades 0.0047% higher cost for less work; Venice wall is effectively tied while its endpoint is lower. The large case still uses more work and reaches lower cost. N=1 prevents a definitive speed claim.

## 2. Batched full-cost evaluation

`OCA_BATCH_COST=1` retains existing multi-RHS back-substitution inputs, materializes candidate states, and evaluates a full menu in one kernel with one host result transfer. The kernel shares observation indices and measurements across candidates; fp64 projection arithmetic and block reductions are retained. Back-substitution and retraction still run per candidate, and prepared steps are copied into the existing selection path. Thus this is a tested cost-batching prototype, not complete fusion of the entire candidate tail.

`OCA_BATCH_COST_CHECK=1` compares identical prepared states with the original evaluator. All observed cost errors were below 5e-16 relative. It checks finite/nonfinite agreement and ordering for candidate separations larger than 1e-10 relative; nearly tied ordering is not certified. For timing, each fixed menu is evaluated six times by each path in alternating order, using CUDA events; the first repeat is excluded below.

| Scene | Sequential costs, ms/menu | Batched costs, ms/menu |
|---|---:|---:|
| dubrovnik-173 | 1.687 | 1.659 |
| final-4585 | 23.511 | 23.543 |
| ladybug-49 | 0.170 | 0.101 |

The large fixed-menu cost timing is essentially unchanged. That is a reason to defer a larger fusion rewrite: current cost batching has no demonstrated large-case payoff. The earlier phase profile already bounded the whole candidate phase at about 13% of wall.

| Dubrovnik-173, 40 outers, N=2 | Seconds, median | Final cost, median |
|---|---:|---:|
| multi | 3.870 | 374,985.28 |
| batch | 3.874 | 375,010.81 |

The nonlinear batch screen is effectively tied in median wall time; its small trajectory difference must not be presented as an execution speedup. No batching default changed.

## 3. Synchronization profile and exact state/controller replay

Nsight Systems, Dubrovnik-173, five outers: `MFPass1` and `MFPass2` together consume 59.6% of GPU kernel time. cuBLAS dot/reduction kernels consume approximately 0.4%. The trace confirms frequent host transfers/synchronizations, but host API wait duration overlaps GPU execution and is not independently removable time. This profile does not justify a large device-side CG rewrite yet. Device scalar recurrences and freezing converged shifted systems remain deferred; no current production-depth nonfinite failure was observed.

The implemented checkpoint saves exact camera rotation matrices, translations, intrinsics, points and controller history: lambda, pre-retry lambda, point damping/ratchet, previous RHS norm, accept/reject streaks, stopping counters, confirmation flag and cost history. Derived assembly/factors are rebuilt. It supports only the plain fp64 unshared L2 diagonal configuration and rejects unsupported environment flags or mismatched settings. The runner additionally pins original input, binary and checkpoint SHA-256. Same binary and architecture are required; this is research replay, not a general persistence format.

A load/save roundtrip reproduced the checkpoint bytes exactly. On both scenes the first resumed attempt matched the uninterrupted run at logged precision, excluding elapsed time. Six-step endpoint differences were 0.0192% on Ladybug and 0.0000443% on Dubrovnik: exact restoration does not make subsequent GPU atomic reductions deterministic.

The table below starts both policies from the **same first-confirmation checkpoint** and preserves the disabled-backtracking flag. Each rollout has at most 20 additional outers, N=2, with alternating policy order. Counts exclude the saved prefix; solver wall includes checkpoint loading/setup while the CSV clock starts after restoration.

| Scene | Policy | Seconds, median | Final cost, median | Rollout retries | Rollout matvecs | Rollout rescues | Rearm events |
|---|---|---:|---:|---:|---:|---:|---:|
| dubrovnik-173 | original | 3.853 | 374,870.65 | 34 | 1791.5 | 0 | 0 |
| dubrovnik-173 | rearm | 3.720 | 374,868.81 | 33 | 1751.5 | 0 | 0 |
| ladybug-1197 | original | 5.755 | 366,783.53 | 60 | 3252 | 0 | 0 |
| ladybug-1197 | rearm | 1.751 | 367,141.56 | 9 | 820.5 | 17 | 3 |

Ladybug validates the mechanism: retry suppression is large, with about 0.10% higher endpoint cost over this short rollout. Dubrovnik never rearms within the budget, so its between-run differences cannot be attributed to the policy. There is no two-scene activation consensus in this checkpoint test. All replay Armijo and rearming eligibility trace checks pass.

## Validation and limits

* CUDA CLI and core library builds pass. Python compilation and `git diff --check` pass.
* Compute Sanitizer reports zero errors for the small combined progressive/batch diagnostic.
* True central shifted residuals agree with the recurrence within the declared 1e-5 RHS-relative diagnostic tolerance on Ladybug-49, Dubrovnik-173 and Ladybug-1197.
* Checkpoint bytes roundtrip exactly; changed-policy loads fail as expected; replay traces pass Armijo/confirmation checks.
* Cold-start timed initial objectives are independently checked in fp64. Replay restores the identical saved state and verifies its GPU objective; checkpoint and final endpoints have no new independent CPU audit. No fresh Caspar run was performed.
* N=1/N=2 and short caps are exploratory. Default settings are unchanged; source and reports are local and uncommitted.
* Broad study coordinators remain paused. No scene-specific mixture is presented as one universal configuration.

## Artifacts and reproduction

* Source: `gpu/oca_cuda.cu`, `gpu/replay_checkpoint.h`.
* Runners: `bench/progressive_screen.py`, `bench/depth_probe_screen.py`, `bench/replay_screen.py`; all accept `--binary` and `--out`.
* Frozen binaries, source snapshots, manifests and logs: `/workspace/prism-progressive`, `/workspace/prism-batch`, `/workspace/prism-sync`, `/workspace/prism-replay`.
* Replay capture: `OCA_REPLAY_SAVE=<file> OCA_REPLAY_AT=confirm OCA_REPLAY_STEPS=6`.
* Replay rollout: `OCA_REPLAY_LOAD=<file> OCA_REPLAY_STEPS=20`, optionally `OCA_BACKTRACK_REARM=1`, with the same original input and solver settings.
* Resume the broad queue only after choosing a fixed policy and a larger validation budget.
