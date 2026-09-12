# Eta2 wave 5: feedback to the proposing agent

Written after completing the course-correction and linear-algebra campaign on
the frozen Eta2 champion.  The frozen source, binary and objective were never
edited.  Every intervention was a derived overlay with an in-session manifest
check, same-binary off control, fixed targets, FP64 endpoint rescore, and the
registered sample sizes.  Large transient states were archived by hash; the
compact protocols, source overlays, raw rows and summaries are retained here.

## Executive verdict

Wave 5 found one useful systems candidate and no algorithmic replacement for
Eta2.  The current candidate combines batched returns for independent FP64 CG
dot products with removal of preparation work that classical LM immediately
discards.  It is **7.78% faster** in geometric-mean time to target on the nine
practical cells and **2.35% faster** on Muell, with identical work counts on
those stable tests.  On the stochastic Final3068 target it records **17/30**
hits versus **18/30** for dots-only.  That supports continued use as a research
candidate, but the confidence intervals remain too broad to claim equivalent
tail reliability.  The frozen champion remains the published reference.

The algebraic proposals produced valuable negative results.  Better point
solutions, a cleaner Gram operator, a stronger preconditioner, an exact dense
solve and FP32 iterative refinement can all improve the object they target
while making the nonlinear BA trajectory worse.  Eta2's loose forcing rule and
basin sensitivity make the returned *finite-iteration direction* part of the
algorithm; matching the exact linear-system fixed point is insufficient.

## Results by brief

| Brief | Measured result | Decision |
|---|---|---|
| A1 / B7, targeted exact two-view repair | On the recorded E4 pair, point 250233 falls from costs 256.303 and 1794.509 to 0.03348 and 0.03344; the full-step trust ratios become 0.5028 and 0.5026.  Natively, Venice remains 0/5 and its median endpoint worsens 4.15%; Final3068 stays 3/5 while conditional time rises 3.49 to 4.66 s and median rejects rise 7 to 17. | Fixed-state mechanism confirmed; native policy rejected. |
| A2, adaptive exit from robust-to-L2 opening | Final3068 falls from 6/10 to 5/10 and slows; Venice stays 0/10 and ends 3.68% worse. | Rejected.  The later robust stages shape the basin even when few weights remain small. |
| A4, `rho_min=1e-3` | Final3068 moves 4/10 to 6/10 but is unresolved and slower.  Venice stays 0/10 with a resolved 0.578% endpoint loss. | Rejected. |
| B0, phase clocks | Across 27 practical runs: Krylov 53.19% of native wall, assembly 13.04%, point factor plus RHS 10.46%, candidate path 2.51%, backtracking 2.54%, unaccounted 18.27%. | Directed effort toward Krylov and preparation; candidate-only work has a low ceiling. |
| B1, factored fragments | Algebra error is only `7.47e-8` relative after FP32 storage and traffic falls from 33 to 19 floats/observation.  The optimized v2 is still 0.34% slower on the panel and 3.28% slower on Muell. | Rejected; register pressure and reconstruction consume the bandwidth gain. |
| B2, FP32 inner solves with FP64 residual/refinement | All correction solves pass the frozen FP64 residual gate with zero fallbacks.  Panel time improves 14% geometrically, but products rise 1.07--4.40x and median endpoints move by as much as 0.519%. | Rejected before tails.  A forcing tolerance identifies a set of admissible directions, not a unique direction. |
| B3, Schur-Jacobi then Nyström | Schur-Jacobi is 1.6% slower on the panel, 21.3% slower on Muell, and drops Final3068 from 4/5 to 1/5. | Rejected.  Nyström was not built because its base failed and sketch products could not amortize. |
| B4, dense FP64 Schur plus Cholesky | Operator audit agrees to `3.53e-16`.  Trafalgar cells are 1.49--2.77x slower.  Venice takes 60.1 s, of which 56.7 s is matrix formation and 0.84 s factor/solve, and follows a worse clipped trajectory. | Rejected. |
| B5, square-root/nullspace Schur | Projected and literal actions agree to `1.80e-15`; curvature and the nonnegative sum-of-squares identity agree to `5.91e-15`.  It is 1.52% slower on the panel, 6.55% on Muell, and loses both tails: Final3068 2/5 to 0/5, Venice endpoint +0.494%. | Rejected as production; retained as a numerical audit path. |
| B6v2, batched FP64 dot returns | Panel geometric mean -1.32%, no disjoint loss, identical stable-cell work; Muell -0.46%; initial Final3068 8/10 in both arms. | Safe production-oriented candidate. |
| B6v3, exact-rounding vector fusion | Bit-identical to cuBLAS over 1,000,003 elements, but only 0.24% panel gain versus 1.44% for dots in the same cohort. | Rejected. |
| B6v4, preparation pruning | Preparation bucket on Muell falls 0.242 to 0.160 s.  Prep alone is -6.73% panel and -2.00% Muell; with dots it is -7.78% panel and -2.35% Muell.  Final3068 N=30 is 14/30 versus off 19/30 (`p=0.299`) and dots+prep 17/30 versus dots 18/30 (`p=1.0`). | Prep alone is not promoted.  Dots+prep is the strongest research candidate; no equivalence claim yet. |
| B6v5, reduction-order-safe preparation fusion | Three bitwise fusions give -1.79% panel but no measurable Muell change. | Useful implementation asset; confirms that B6v4's large-scene gain comes from deleted dead diagonal work. |
| B6v6, camera-owned reduced RHS | Fixed per-camera reductions cut the Muell preparation bucket 0.241 to 0.074 s, improve the panel 8.23% and Muell 3.93% versus dots-only, and sample Final3068 at 6/10 versus 3/10.  Venice remains 0/10 with a +0.253% endpoint movement. | Always-on arm fails the strict quality gate; retain for a preregistered camera-count dispatch. |
| B8, long shots | Literature and existing-repo audit found direct BA prior art for two-grid/deflation, inverse power-series Schur solves, square-root marginalisation, object-space variable projection and matrix-free GPU BA. | No build justified from this menu after the measured base failures. |

Negative percentages above mean faster or lower cost; positive percentages mean
slower or higher cost.  Misses remain in every hit-rate denominator.

## Mechanistic findings

### Exact local repair can still be globally harmful

A1 is the cleanest example.  The targeted two-view solve removes essentially
all of the recorded point-level error and makes both E4 proposals acceptable.
Applied throughout a live run, it changes thousands of locally selected track
updates, increases rejection activity, and moves Venice into a worse basin.
The issue is no longer whether exact triangulation works; it does.  The issue
is that greedy local true-cost improvement changes the future linearisation.

### Linear-solver accuracy is not Eta2 semantic equivalence

B3, B4, B5 and B2 improve four different notions of linear quality: the
preconditioned spectrum, exactness of the solve, backward stability of the
operator, and high-precision residual satisfaction.  All can change the
nonlinear trajectory because Eta2 intentionally stops PCG at a loose,
state-dependent forcing threshold.  The particular finite Krylov iterate is
therefore coupled to clipping, acceptance, damping and the next Jacobian.  A
production linear-algebra change must preserve or explicitly redesign that
coupling; residual tolerance alone is an inadequate contract.

### Follow data lifetime before changing representation

B1 reduced fragment traffic but paid more in contractions and registers.  B6v4
won by a simpler audit: the frozen preparation kernel computes a Schur diagonal
and the classical-LM branch immediately overwrites it with `diag(H_cc)`.
Removing the dead triangular solves and atomics reduces the Muell preparation
bucket by about 34%.  B6v5 retains that work and loses the Muell gain, directly
confirming attribution.

## Current winner and limits

For the frozen objective, the algorithmic winner remains Eta2.  For the wave-5
implementation overlays, dots+prep is the current speed winner:

- practical-panel geometric-mean time-to-target ratio: `0.9222`;
- Muell time-to-target ratio: `0.9765`, 980 products in both arms;
- stable-cell median endpoint movement: at most `0.00175%`;
- Final3068: 17/30 target hits against dots-only 18/30;
- Venice52: 0/10 in every B6 arm, with endpoint movement inside its known mode
  spread.

These data support a separately named optimized build.  They do not yet support
replacing the frozen champion in the scientific ledger, because Final3068's
Wilson intervals overlap widely and the RHS atomic schedule changes when the
dead diagonal work is removed.  “No significant loss” is not equivalence.

## Novelty boundary

The B6 speedup is systems engineering rather than a new optimization method.
The publishable value is an end-to-end, target-time result with an arithmetic
audit and a stochastic-tail gate, not a claim that kernel fusion or batched
reductions are new.

The more distinctive scientific result is negative: in basin-sensitive,
forcing-term inexact LM, familiar linear guarantees do not imply nonlinear
algorithm equivalence.  The campaign supplies concrete counterexamples for
Schur-Jacobi, exact dense solves, Gram-consistent square-root products and
mixed-precision iterative refinement.  This should be framed as a measured
property of the coupled solver, with the successful fixed-system audits shown
beside the failed native runs.

Direct prior art prevents broad claims for deflation/two-grid BA, PowerBA-style
inverse expansions, RootBA-style nullspace marginalisation, matrix-free GPU BA,
or object-space variable projection.  The source-by-source boundaries are in
`literature/MATH_AND_PRIOR_ART.md`.

## Recommended continuation

1. Keep dots+prep in a separate research/optimized configuration and preserve
   the original Eta2 source and binary.
2. If it is to become the shipped implementation, run a larger preregistered
   Final3068 equivalence cohort or develop a deterministic RHS reduction and
   repeat the tail gate.  The current N=30 result is adequate for prioritizing
   work, not for proving equal reliability.
3. Validate the candidate with an end-to-end GPU trace on Muell.  The internal
   phase timers already identify the saving, but a trace should verify that it
   comes from fewer observation-kernel instructions rather than timer effects.
4. Re-run the frozen same-target Caspar/Ceres comparison with the optimized
   binary only after the reliability gate.  Reusing the registered targets will
   isolate implementation speed from endpoint quality.
5. Do not reopen Nyström, dense Schur, square-root production, FP32 refinement,
   global exact triangulation, adaptive robust exit or the lower acceptance
   threshold without a new mechanism that addresses their measured failure.

The compact evidence needed to reproduce every statement is in this directory;
`B6V4_RESULTS.md` contains the final candidate decision and N=30 distribution
table.
