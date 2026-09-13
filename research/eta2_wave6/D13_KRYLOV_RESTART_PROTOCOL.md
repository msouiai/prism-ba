# D13 protocol: align the inner Krylov process with Eta2's forcing metric

Registered 2026-09-13 after D12 exposed the restart signal and before any
restart-depth or native experiment.

## Hypothesis

Hcc-PCG minimizes the `A`-energy norm of the linear error.  Eta2 terminates the
inner solve when the explicitly recomputed Euclidean residual satisfies
`||b-Ax||_2 <= eta ||b||_2`, usually with `eta` as loose as 0.5.  These are
different objectives.  The Euclidean residual of CG need not be monotone, so
preserving a long conjugate recurrence can spend products improving a norm the
forcing rule does not inspect.

D12 supplied two pre-registered witnesses with the unchanged operator and
Hcc preconditioner:

- Muell outer 12: uninterrupted 41 iterations / 42 products / 130.35 ms;
  exact-residual restart at 8 gives 13 / 15 / 46.51 ms.
- Muell outer 11: uninterrupted misses at 128 iterations with true residual
  1.098; exact-residual restart at 8 hits in 52 iterations / 54 products with
  true residual 0.4763.

The intervention changes no matrix, RHS, preconditioner, damping, or forcing
threshold.  At the restart it computes `r=b-Ax` explicitly, sets
`p=M^-1 r`, and begins a fresh valid PCG recurrence from the current iterate.

## Stage 1: fixed-system selection

Development systems are Muell outers 11 and 12.  Shallow controls are
Ladybug598 outer 8 and Final1936 outer 0.  Compare one exact-residual restart
at depth `d in {4, 8, 16, 32}`.  Also record a periodic-8 diagnostic, restarting
at every multiple of 8, but it cannot be selected unless it beats one-shot 8
on both hard systems after charging every residual product.  N=3 timing repeats;
fixed arithmetic is deterministic.

Rank the one-shot depths lexicographically:

1. number of hard systems reaching the unchanged `eta=0.5` gate;
2. total products summed over both hard systems, counting residual replacement;
3. median summed wall time.

Choose the smallest depth within 2% of the best product sum.  A shallow solve
that finishes before `d` must be bit-identical and pay zero extra products.

Before native integration, run a residual-minimizing control on the same fixed
systems.  Right-preconditioned GMRES(m) minimizes the exact Euclidean residual
that Eta2 tests; use `m=8` and Hcc right preconditioning.  Every Arnoldi dot,
orthogonalization, preconditioner application and product is charged.  This is
a mechanism control, not eligible for native promotion in D13 unless it beats
the selected restart on both hard systems and does not allocate more than 16
camera vectors.  An implementation failing an explicit residual/Arnoldi
identity check is invalid.

## Stage 2: native rule

Add opt-in `OCA_PCG_RESTART_DEPTH=d` to a copy of the checksum-pinned frozen
Eta2 source.  It is legal only in the champion's single-shift, explicit Hcc-PCG,
unshared 9-DOF camera path.  Zero/unset is byte-path compatible.  Recompute the
true residual once, restart once, and log outer, retry, depth, residual before
and after.  Do not change checkpoint scoring or the 128-depth cap.

Run N=3 paired/alternated trials on:

- the nine registered practical time-to-target cells;
- Muell at `1946488.746262194`;
- Final1936 at `5125687.352261469`.

Advance to N=5 Final3068 (`1744796.9841897595`) and Venice52 (`243740.27`)
only if the practical geometric-mean time ratio is <=1.02, no cell loses more
than 10% with disjoint ranges, and Muell is at least 1.10x faster.  On the
tails, reject if hit rate drops or successful-run median target time rises by
more than 20%.  Cost differences below 0.15% remain unresolved.

If the frozen scientific arm passes, transplant the identical restart into
the wave-5 optimized systems candidate and re-run only the promotion cells.
The original champion and optimized binary remain unchanged.

## Prior art and claim boundary

CG, restarted CG, residual replacement, GMRES and MINRES are established.
Netlib's iterative-method templates explicitly distinguish CG's energy-error
minimization from minimum-residual methods.  Recent work on restarted CG's
asymptotic directions does not supply a BA policy or a speed prediction.

No novelty claim attaches to restarting at 8.  A possible contribution is the
measured mismatch between inexact-LM forcing and PCG's polynomial objective,
plus a sparse trigger that improves end-to-end GPU BA convergence rather than
only one linear solve.
