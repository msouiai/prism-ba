# Corrected champion comparison and Schur numerical repair

The leading candidate is the frozen coupled-radius champion with `OCA_SCHUR_NUMERIC_GUARD=1`. The change repairs numerically nonpositive Schur directions by increasing **both camera and point damping** and restarting the linear solve at the same state. It retains FP32 fragment storage, FP64 state/arithmetic/acceptance, Hcc PCG, and the incumbent point safeguard. It introduces no multishift menu or residual Hessian.

The current four-scene, three-repeat results are below. These are fresh same-host pairs using the optimized implementation, not the original five-shift executable mistakenly used in the earlier Ladybug comparison. Every endpoint was scored independently on the original FP64 observations. Production defaults were not changed.

| Scene | Prism + numerical guard (s) | Caspar FP32 (s) | Caspar FP64 (s) |
|---|---:|---:|---:|
| ladybug-1723 | 0.445 [0.378, 0.451] | 0/3 hits | 1.394 [1.393, 1.411] |
| final-1936 | 0.565 [0.556, 0.569] | 1.163 [1.163, 1.173] | 2.559 [2.559, 2.564] |
| trafalgar-126 | 0.132 [0.130, 0.145] | 0/3 hits | 1.494 [1.194, 1.607] |
| final-4585 | 1.843 [1.837, 1.917] | 0/3 hits | 0/3 hits |

Entries are median [minimum, maximum] seconds; hit counts replace medians when any repeat misses. No finite speed ratio is assigned to a miss. Exact per-scene speed ratios and the geometric mean over **only jointly reached scenes** are in [evidence.json](/workspace/prism-model-followup/evidence.json). The FP32 common subset is particularly small and should not be presented as a broad benchmark average. Three executions are three repeats, not three independent datasets.

**Protocol and endpoint quality.** Host: `2237c6528e79`, RTX 2000 Ada 16 GB, one GPU process at a time under `/tmp/prism_gpu.lock`. The primary threshold is 1.01 times a historical quality anchor, fixed before testing this change. Ladybug's anchor is a retained audited Caspar FP64 endpoint; the other anchors are prior fixed benchmark targets. They are not certified optimal values. This convention implements a quality tolerance, rather than requiring a specific solver's final fractional-percent refinement.

| Scene | Historical anchor | Common target | Native cap, s |
|---|---:|---:|---:|
| ladybug-1723 | 448194.125000 | 452676.066250 | 8 |
| final-1936 | 5074937.972536 | 5125687.352261 | 8 |
| trafalgar-126 | 104534.241529 | 105579.583945 | 4 |
| final-4585 | 7488277.528211 | 7563160.303493 | 12 |

All arms use their driver's 600-iteration limit as a secondary bound. Prism counts accepted outer steps while Caspar counts attempted iterations; those caps are not identical work budgets. The native wall cap and common target are the comparison criteria. Numerical rebuilds are counted separately from nonlinear rejects and all their work is inside the timer. Export and independent CPU audits are outside it. Prism includes solver-local allocation/setup; Caspar excludes graph setup, which is separately retained in each result. Input parsing is excluded. This is the pinned standalone Caspar backend, not a full COLMAP reconstruction run.

Caspar FP32 uses a native stop threshold 0.1% below the common target as an empirical rounding margin; only the independent FP64 endpoint qualifies a hit. This margin is not a numerical certificate. Caspar FP32's Ladybug native cost and raw-observation audit differ substantially: the fast termination is not an equal-quality solve. The modest Trafalgar miss at the primary threshold should not be described as a meaningful quality failure; the separate relaxed target below checks that sensitivity.

| Scene | Solver | Median independently audited endpoint cost |
|---|---|---:|
| ladybug-1723 | Prism + numerical guard | 452,638.397 |
| ladybug-1723 | Caspar FP32 | 1,024,407.196 |
| ladybug-1723 | Caspar FP64 | 452,590.643 |
| final-1936 | Prism + numerical guard | 5,095,070.524 |
| final-1936 | Caspar FP32 | 5,103,595.544 |
| final-1936 | Caspar FP64 | 5,103,601.813 |
| trafalgar-126 | Prism + numerical guard | 105,234.230 |
| trafalgar-126 | Caspar FP32 | 105,674.449 |
| trafalgar-126 | Caspar FP64 | 105,577.396 |
| final-4585 | Prism + numerical guard | 7,531,039.166 |
| final-4585 | Caspar FP32 | 11,232,898.020 |
| final-4585 | Caspar FP64 | 12,279,225.826 |

The complete [final pair records](/workspace/prism-model-followup/final-caspar-pairs/results.json) retain all repeats, misses, endpoints, counters, native and process clocks, setup times, input/binary/state hashes and exact commands. The largest endpoint audit discrepancy is 4.4e-10 relative, below the 1e-7 validation limit.

**What changed relative to the actual champion.**

| Scene | Frozen champion (s) | Prism + numerical guard (s) |
|---|---:|---:|
| ladybug-1723 | 0/3 hits | 0.444 [0.442, 0.461] |
| final-1936 | 0.554 [0.551, 0.578] | 0.550 [0.549, 0.552] |
| trafalgar-126 | 0.131 [0.129, 0.138] | 0.130 [0.128, 0.131] |

In this matched development batch the original Ladybug arm missed all three targets; the repaired arm reached all three with one numerical rebuild and one nonlinear reject each. It used 18 accepted steps in every run. The Final-1936 and Trafalgar trajectories did not trigger the guard, and their speed differences are small. Across other retained baseline batches Ladybug occasionally reached the target, so the finding is improved observed reliability, not that the unguarded solver can never reach it. Final-4585 was held out for this change; the rule and constants were frozen before that validation, and the guard did not activate before its target.

**The quadratic problem was numerically inconsistent.** Two saved Ladybug PCG directions had negative curvature in the stored Schur operator. Rebuilding the point elimination from original FP64 Jacobians gave positive curvature for the same camera direction and damping:

| Captured outer | Stored pᵀAp | Original-Jacobian Schur energy | Stored point-equation relative residual |
|---|---:|---:|---:|
| 15 | -71.971990 | 273.672298 | 0.134 |
| 16 | -10.225014 | 40.295156 | 0.712 |

The independent reconstruction computes energy as a sum of squares plus damping, rather than subtracting nearly cancelling camera and eliminated-point energies. The rebuilt point solve's backward error is recorded in [model-analysis-final.json](/workspace/prism-model-followup/model-analysis-final.json). Hcc, rounded cross blocks and rounded point Jacobians need not form one coherent positive-semidefinite Gram matrix. Subtractive Schur evaluation and very small damping can then expose spurious negative curvature. FP64 fragments alone also eventually encounter the limits of tiny damping and did not fix the full trajectory; the measurements do not establish rounding as the only cause of every stall.

The bounded FP64-fragment experiment was rejected: its Ladybug arm missed all three targets, while Final-1936 changed from median 0.565 s to 0.681 s, about 21% slower. See [double-screen/results.json](/workspace/prism-model-followup/double-screen/results.json). Merely doubling fragment storage is not the selected fix.

**Why the new repair is mathematically justified.** With fixed Hcc scaling E and frozen stored blocks, write

\[
A(\lambda)=E[B-W(C+\lambda D_p)^{-1}W^T]E+\lambda I.
\]

For positive point damping and lambda′ ≥ lambda,

\[
A(\lambda')-A(\lambda)\succeq(\lambda'-\lambda)I.
\]

This monotonicity does not require the rounded blocks to be one exact Gram matrix. For a failed direction p, let q = pᵀA(lambda)p / pᵀp. The prototype chooses lambda′ = 4 max(lambda, lambda − q), subject to numerical limits. For q ≤ 0 this gives a strictly positive lower bound q + lambda′ − lambda on the repaired direction's Rayleigh quotient. The point factors and reduced RHS are rebuilt; the incompatible CG basis is discarded. No nonlinear candidate is accepted on the strength of this bound.

This is a directional guarantee for the frozen algebra in exact arithmetic, not a certificate for every direction or for floating-point factorizations. The next solve is checked again. The observed regularization floor is retained for the remainder of the solve, which avoids dropping immediately back into the problematic range but can overregularize later states. A 32-rebuild limit and the native time cap bound the extra work. All true-cost, positive-prediction, rho > 0.1, and camera-radius acceptance checks remain active.

The [independent dense check](/workspace/prism-ba/bench/check_schur_numeric_guard.py) passed 100 deliberately inconsistent block problems, checking monotonicity, the failed-direction bound and the coherent sum-of-squares identity. All 12 final candidate runs also passed coupled-damping, acceptance, radius and rebuild-accounting checks in [trajectory-validation.json](/workspace/prism-model-followup/trajectory-validation.json). A separate [flag-off check](/workspace/prism-model-followup/flag-off-check/results.json) matched the original Final-1936 control's four accepts, 22 products and audited cost. GPU atomic reductions prevent a general byte-for-byte repeatability claim; this checks the visited disabled path. This is a numerical safeguard for a BA-specific implementation; these tests do not establish a new trust-region convergence theorem or publication novelty.

**The residual-curve model was tested on saved real BA directions.** Let v=Jd and e=r(x⊕d)−r−v. The proposed residual interpolant r+alpha v+alpha²e matches the current and evaluated residual and the derivative at zero. Its squared norm is a quartic, so a scalar cubic gives candidate contractions without another global linear solve. Full nonlinear costs were recomputed on each suggested ray point.

| Saved failed direction | Top 1% of tracks' absolute model-error share | Curve alpha | Half-step cost | Curve-step cost |
|---|---:|---:|---:|---:|
| ladybug-1723, outer 6 | 99.64% | 0.5135 | 462,990.363 | 462,912.899 |
| ladybug-1723, outer 7 | 99.40% | 0.4525 | 460,562.883 | 460,487.730 |
| trafalgar-126, outer 4 | 97.27% | 0.4195 | 107,149.040 | 107,411.032 |

The two Ladybug proposals improve immediate cost slightly over a half step; the Trafalgar proposal is worse. All three half steps already pass the strict gain-ratio test, so these samples demonstrate no saved cost evaluations or linear retries. The quartic is therefore retained as an offline prototype, not added to the winning solver. Whole-track concentration supports investigating selective point corrections later, but it does not prove they will be faster.

Analytic directional derivatives were checked at a step-size ladder. Ladybug's very small finite-difference steps suffer cancellation: the best tested discrepancies are approximately 7e-5 and 3e-4 on its failed directions; Trafalgar checks reach approximately 1e-8 or better. The exact residual-defect identity closes near floating-point reduction error. These are fixed-state diagnostics, not evidence for a higher-order convergence rate.

**Where remaining time goes.** A separate instrumented Final-1936 run charged approximately 0.169 s to assembly, 0.132 s to point preparation/RHS, 0.147 s to Krylov work and 0.029 s to candidate scoring. It had four accepts and zero rejects. These categories do not include every part of the solver clock and should not be normalized as an exhaustive GPU profile. On this fast trajectory, eliminating nonlinear rejection work would save nothing. The next execution experiment should target assembly/point-preparation traffic or fuse actual-cost and full-step-model evaluation, with the current candidate as control.

**Target sensitivity.** A separately declared 2% threshold was tested before the repair: on Ladybug, the original champion took median 0.232 s [0.231, 0.240] versus Caspar FP64 0.607 s [0.606, 0.608]. On Trafalgar, it took 0.126 s versus Caspar FP32 1.091 s and FP64 0.676 s. See [sensitivity-2pct/results.json](/workspace/prism-model-followup/sensitivity-2pct/results.json). This explains why a statement that Prism is simply slower was too broad. The primary 1% target was not changed to rescue a failing candidate.

At the tighter 0.5% Ladybug target (450,435.095625), the repaired solver reached 3/3 in median 0.657 s [0.643, 0.726]; the matched original missed 3/3. Each repaired run still needed only one numerical rebuild. The retained floor therefore did not prevent this tighter accuracy in the tested runs. See [tighter Prism comparison](/workspace/prism-model-followup/sensitivity-halfpct-prism/results.json).

The initial tighter-target Caspar run failed the predeclared checker-agreement threshold: reported cost 450,394.444 versus independent FP64 exported-state cost 450,394.343, relative difference 2.25e-7. Long-double evaluation of that state gave 450,394.169, exposing sensitivity to arithmetic order near projection singularities. All are below the target, and the difference is negligible for practical quality, but the validation threshold was not relaxed after seeing the result. That partial side comparison was retained and excluded from speed claims; the Prism-only three-repeat tighter check was then completed. [Audit discrepancy](/workspace/prism-model-followup/sensitivity-halfpct/audit-discrepancy.json). The 36-run primary comparison passed its checks and is unaffected.

**Code and reproduction.**

- [Candidate source and binary](/workspace/prism-model-followup/candidate/manifest.json), binary SHA256 `117773562d33949cdbfdc27905d1f23a2cc1faedb7f77c3e619c17caa50a86dc`.
- [Builder](/workspace/prism-ba/bench/build_model_followup.py), [target harness](/workspace/prism-ba/bench/current_champion_targets.py), [capture helper](/workspace/prism-ba/gpu/model_followup_capture.cuh), [model analysis](/workspace/prism-ba/bench/analyze_model_followup.py).
- [Frozen builds archive](/workspace/prism-model-followup/frozen-builds.tar.gz) contains the verified parent, diagnostic, FP64 ablation and selected candidate source/headers/binaries. [Captured states and directions](/workspace/prism-model-followup/model-captures.tar.gz) preserve the inputs to the CPU checks.
- [Final protocol](/workspace/prism-model-followup/final-caspar-pairs/protocol.json) records fixed inputs, targets, flags and binary hashes. Each individual manifest contains the exact standalone command.

Run the candidate with the parent selected flags, `OCA_SCHUR_NUMERIC_GUARD=1`, `--lam0 0.1`, `--dof9 --zero_k2 --mf-no-alpha`, and an explicit target/time cap. The current code is an isolated research build; the repository's production solver defaults and unrelated working-tree edits were preserved. The literature motivation and broader alternatives are in [TR model research](tr_model_research.md); the new claims in this report rest on the local experiments above.
