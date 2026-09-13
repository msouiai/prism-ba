# D14 protocol: one-reduction Chronopoulos--Gear PCG

Registered 2026-09-13 before implementing or timing the D14 fixed-system
harness.

## Hypothesis

The wave-5 optimized Eta2 path already batches each independent pair of FP64
dot products, but standard Hcc-PCG still has two host-visible scalar
dependencies per iteration: `(p,Ap)` before the step and `(r,M^-1 r)` after
it.  The preconditioned Chronopoulos--Gear recurrence is mathematically
equivalent in exact arithmetic and combines the residual/preconditioned-
residual and `A M^-1 r` products into one reduction phase.  It adds the
recurrence `s=A p = w + beta s_old`.

On a single GPU there is a real cost: filling and draining the recurrence uses
one additional Schur product per linear solve.  The method can only win on
deep, launch/synchronization-bound solves.  This fixed-system screen measures
that crossover before any nonlinear trajectory is changed.

## Registered implementations

Both arms use the same FP32 fragments, FP64 Schur contractions, Hcc block
preconditioner, zero initial guess, `eta=0.5`, and 128-update cap.

1. `standard`: frozen preconditioned CG algebra, with the two independent dot
   pairs returned in two batched device-to-host copies per update, matching the
   wave-5 B6v2 synchronization structure.
2. `cgcg`: Algorithm 2 of Ghysels and Vanroose's presentation of
   Chronopoulos--Gear PCG.  A batch contains `||r||^2`, `(r,u)`, `(Au,u)` and
   the norms/cross-products needed for the existing curvature test.  It uses
   one host-visible reduction phase per update and one extra Schur product per
   solve.  No residual replacement is enabled.

Every reported hit is verified with an explicit FP64 `b-Ax` product.  Report
true residual, updates, total products including verification, reduction
phases, wall time, solution difference, and recurrence-denominator failures.
The implementation must pass a dense random-SPD unit test against direct
Cholesky before captured BA timings.

## Fixed-system cohort and decision

Use the four checksum-pinned captures already used by D13: Muell outers 11 and
12, Ladybug598 outer 8, and Final1936 outer 0.  Run three warmups then ten
arm-alternated timed repetitions per cell.  The shallow cells measure pipeline
fill/drain cost; the two Muell cells measure the only plausible crossover.

Advance to a native, depth-gated arm only if all of the following hold:

- true residual is at most `0.5 ||b||` whenever a hit is reported;
- no denominator/curvature failure occurs where standard PCG succeeds;
- median products differ by exactly the registered one-product overhead unless
  finite-precision convergence depth itself differs;
- `cgcg` is at least 1.05x faster on one Muell capture and is not slower on the
  other Muell capture with disjoint ranges.

Otherwise stop at the fixed screen.  A fixed win would earn a separate native
protocol based on the previous solve's observed depth; no scene-name or
post-hoc per-scene dispatch is allowed.

## Prior-art and claim boundary

Chronopoulos and Gear introduced s-step CG in 1989.  Ghysels and Vanroose
presented the one-reduction preconditioned recurrence and a communication-
hiding extension in 2014.  Extra recurrences can amplify roundoff; the residual
gap and replacement literature therefore motivates the explicit audit, but
D13b already rejects periodic replacement as a global Eta2 policy.  D14 can be
a systems optimization only; neither the recurrence nor synchronization
reduction is novel.
