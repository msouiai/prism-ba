# CG stopping and projected TR — 2026-09-09

**Verdict:** the guarded projected-TR variant reaches the largest scene’s verified quality target in 16.35s, where the frozen mixed-buffer TR misses its 20s cap. It roughly matches Caspar FP64 on this one run; Caspar FP32 remains about 2.1× faster. The new variant regresses on Dubrovnik, so retain it as a large-scene experimental candidate rather than replacing the control.

## Fresh largest-scene comparison

Final13682, original BAL input, nominal target 27,318,392.631312046; independent certification threshold 27,318,392.35812812. N1 per arm, 20s requested native cap, serialized GPU execution.

| Arm | Verified time to target | Audited endpoint |
|---|---:|---:|
| Guarded projected TR | 16.349s | 27,232,347.166 |
| Frozen mixed-buffer TR | Miss | 27,381,520.046 |
| Caspar FP64 | 16.688s | 27,198,720.095 |
| Caspar FP32, stopping margin | 7.797s | 27,182,149.052 |

The control returns after 22.099s because it checks the cap at solver boundaries; work completed after the deadline is discarded. Its endpoint is still about 0.231% above target. No successful crossing time or speed ratio is imputed to this miss.

Caspar FP32 uses the previously tested, fixed 0.1% tighter native stopping threshold, rounded to its float parameter type. Its reported time is the crossing of that stricter threshold, followed by an independent check against the original double-observation target. This avoids crediting an earlier unverified native crossing. Caspar FP64 uses the original effective target.

The 16.35s versus 16.69s difference is a single-run observation, not evidence of a statistically established win over Caspar FP64. The FP32 gap remains substantial. Native scopes remain those of the earlier comparison: TR includes solver-local allocation; Caspar excludes graph setup. Process wall times include input handling, auditing and GPU-lock waits and are not normalized application latencies.

## Smaller-scene trade-offs

Fresh N3 paired comparisons, frozen mixed-buffer control versus the guarded projected variant. All nine runs in each arm independently qualify. Historical harness labels are `double` = mixed-buffer control and `storage` = stopping candidate; neither label denotes a precision difference in this experiment.

| Scene | Control median | Guarded projection median | Runtime change |
|---|---:|---:|---:|
| trafalgar-126 | 0.500s | 0.521s | +4.3% |
| dubrovnik-88 | 0.626s | 0.777s | +24.1% |
| final-1936 | 2.997s | 2.989s | -0.2% |

The projected variant wins 0/3 Trafalgar pairs, 0/3 Dubrovnik pairs and 2/3 Final1936 pairs. The Final1936 difference is effectively a tie. Low single-digit regressions need not disqualify an approach, but the Dubrovnik slowdown is materially larger. Both changed trajectories and projection overhead can contribute; this batch does not isolate their shares.

## What the fixed-system investigation found

The captured system is outer iteration 6 on Final13682, including exact stored W, U, point factors, scaling E, RHS, sparse indices and CG snapshots. Replay checks apply that same GPU operator to the saved directions; no new scene or linearization is substituted.

The original damped solve uses sigma = 6.25e-5. At depth 64 its relative CG residual is 0.381 against an Eisenstat–Walker-style tolerance of 0.169, so the tolerance is not unusually strict in this particular solve. The initial suspicion about oversolving from the forcing sequence was not supported by this measurement. The classical [forcing-term framework](https://users.wpi.edu/~walker/Papers/forcing_terms%2CSISC_17%2C1996%2C16-32.pdf) links linear accuracy to nonlinear progress; a high iteration count alone is insufficient evidence of oversolving.

The important defect is directional: the old method radially clips damped-CG snapshots. It runs to depth 128 but selects the depth-64 direction. For q(x) = 0.5 xᵀSx − bᵀx, the support/Frank–Wolfe gap is

```text
g = Sx − b
gap = gᵀx + R ||g||,    ||x|| ≤ R.
```

If S is positive semidefinite, convexity makes this an upper bound on q(x) − min q over the ball. The clipped depth-64 candidate has gap / achieved reduction = 2.469. Continuing CG to 128 leaves that selected candidate and gap unchanged. Therefore this bound does not justify simply stopping at 64.

A four-dimensional span of saved CG snapshots improves predicted reduction by about 6% at depth 128 but still has gap ratio 1.504. A separately constructed, fully reorthogonalized Krylov basis gives:

| Krylov depth | Predicted reduction | Gap / reduction | TR multiplier |
|---|---:|---:|---:|
| 16 | 1,820,458.7 | 10.3178 | 0 |
| 32 | 3,142,937.1 | 3.1025 | 0.0013384 |
| 64 | 3,521,168.3 | 0.2381 | 0.00357103 |
| 128 | 3,541,833.1 | 0.0010 | 0.00377285 |

The final projected multiplier is about 60× the seed shift. Solving the TR model within the basis is substantially better than clipping the original direction. These are local quadratic-model results, not nonlinear BA speedups.

## Implemented candidate

The implementation follows the established idea of [Lanczos/Krylov trust-region subproblem solvers](https://www.numerical.rl.ac.uk/media/people/nick-gould/GoulLuciRomaToin99_siopt.pdf). It adds a projected TR direction to the existing candidates; it does not claim a new GLTR algorithm or a full-space BA trust-region theorem.

The inexpensive basis construction reuses CG products:

```text
A = S + sigma I
p_j = r_j + beta_(j−1) p_(j−1)
S r_j = A p_j − beta_(j−1) A p_(j−1) − sigma r_j.
```

Normalized residuals form Q, and the corresponding SQ columns come from products already computed by CG. There is no additional Schur matvec per stored column. At checkpoints the code forms G = QᵀQ and H = sym(QᵀSQ), whitens the retained eigenspace of G, and solves the small radius-constrained quadratic. It does not assume that finite-precision CG residuals remain orthogonal. Gram eigenvalues below 1e-10 of the maximum are dropped.

Before adding a projected direction, one explicit Schur application checks its predicted reduction to relative tolerance 1e-7 and verifies the actual radius. Failed checks discard that direction. The candidate uses the projected solve only when the current best direction is near the radius (norm at least 0.8R) and the projected multiplier exceeds the seed shift. It compares nonlinear costs of the original and projected candidates before the existing point safeguard and full-model TR acceptance. The original point-damping controller remains in place; the projected multiplier is not fed into point damping.

The stopping test requires the verified projected candidate’s gap to be at most 5% of the best model reduction in the current bank. On the instrumented largest-scene repeat, gap ratios at depths 32, 48, 64, 80 and 96 are approximately 3.10, 0.82, 0.268, 0.084 and 0.0208. It stops at 96 rather than 128, and the improved direction reaches the nonlinear target in seven accepted steps. The fresh uninstrumented run has 160 total matvecs and zero rejected outer steps.

This is a combined direction-quality and stopping improvement, not merely a faster implementation of the old depth-64 choice. The new candidate also evaluates an additional nonlinear direction when appropriate; that work is charged.

## Numerical limits and negative experiments

FP32 fragment storage does not preserve an exact Gram factorization of the complete Schur operator, so global positive semidefiniteness is not certified. Consequently the gap is a mathematically motivated stopping measure here, not an unconditional global error certificate. The test suite verifies 200 convex quadratic bounds and retains an indefinite counterexample where the gap is zero but the point is not globally optimal. FP64 objective/full-model checks and the existing Cauchy candidate remain active.

The simple gap-only stopping experiment, N3 per scene, did not improve consistently:

| Scene | Frozen control | Gap-only candidate |
|---|---:|---:|
| trafalgar-126 | 0.444s | 0.501s |
| dubrovnik-88 | 0.713s | 0.642s |
| final-1936 | 2.986s | 3.021s |

The first unrestricted projected rollout was also unsuccessful. On Trafalgar, its diagnostic guard stopped the run at a projected-model discrepancy of 1.026e-7, just above the 1e-7 threshold; this failed run remains in the results. On Dubrovnik it terminated above target after 32 accepted and 45 rejected steps. The guarded version gates projection to radius-active cases, retains the original nonlinear-cost candidate, and discards failed model checks. Its full-target numerical screens pass, but its remaining Dubrovnik timing regression is retained rather than explained away.

## Validation and artifacts

53 completed BA endpoints were independently audited, including the fixed-system capture and the instrumented largest-scene repeat. Maximum endpoint agreement error is 3.33e-13. The earlier failed prototype has no exported endpoint and is not counted as a passing audit. There are 610 checked accepted TR trace records, 324 recurrence-curvature checks (maximum 7.18e-11), and 22 projected-model checks from completed diagnostic runs (maximum 9.06e-12). Four frozen-operator replay checks agree within 6.35e-13 of the RHS norm.

CSV costs are printed to ten decimal places. Reduction/rho consistency is checked in cost units with that serialization error accounted for, especially for tiny reductions in the stalled unsuccessful prototype. Positive reduction, rho threshold and radius feasibility remain separate checks.

The timed and smaller audited completed runs total 131.007s native solver time. Adding the fixed-system capture and instrumented large repeat gives 175.423s of recorded completed BA solve time. This excludes compilation, data loading, CPU audits, lock waits, standalone frozen-operator replays, and the failed run’s unavailable native timer. The failed process used 1.065s wall time. All 11 pre-existing paused jobs remain paused; the GPU is idle after completion.

The projected basis and retained legacy bank add approximately 0.30 GiB of device allocations on Final13682. These are additional to the mixed-buffer candidate, which saved 3.56 GiB of fragment allocations relative to FP64 storage. Neither number is a measured whole-process peak.

All new code is isolated from the production solver and frozen control:

- `bench/build_tr_cg_stop.py`, `gpu/tr_cg_stop.inc`: capture and initial gap-only experiment.
- `bench/analyze_cg_capture.py`, `bench/replay_cg_capture.cu`: fixed-system subspace analysis and GPU replay.
- `bench/build_cg_projection.py`, `gpu/cg_tr_projection.cuh`, `gpu/cg_tr_projection_step.inc`: CG-product reuse and projected TR.
- `bench/build_guarded_cg_projection.py`: final guards and retention of the original nonlinear candidate.
- `bench/tr_cg_study.py`, `bench/cg_stop_large.py`: bounded paired tests and the four-arm large comparison.
- `bench/test_cg_stop_bound.py`, `bench/verify_cg_stop.py`, `bench/write_cg_stop_report.py`: mathematical checks, independent verification and reporting.

Artifacts: `/workspace/prism-tr-cg-stop/`. The final opt-in executable is `guarded/prism-tr`; exact flags are in `guarded-timing/protocol.json` and `large/protocol.json`. The new path uses `OCA_CG_STOP=2`. Sources, headers, build manifests, logs and endpoint states are retained. `capture-files.json` hashes the exported fixed operator and snapshot files. Build order is the initial stopping build, projected build, then guarded build; existing completed artifacts are protected from overwrite.

**Decision:** keep the guarded variant as the strongest current large-scene TR challenger, keep frozen mixed-buffer TR as the smaller-scene control, and keep Caspar FP32 as the largest-scene speed leader. Before promotion, repeat the large result and investigate the Dubrovnik regression on matched states to separate additional projection work from changed trajectories.
