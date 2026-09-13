# D12 protocol: randomized Nyström correction of the Hcc preconditioner

Registered 2026-09-13 before implementing or running D12.

## Question and mathematical object

The frozen Eta2 solve uses the camera block matrix

\[
H=EUE+\lambda I
\]

as its block-Jacobi preconditioner for

\[
A=E(U-WV_\tau^{-1}W^T)E+\lambda I.
\]

Writing `H = L L^T` gives the normalized system

\[
L^{-1}AL^{-T}=I-G,\qquad
G=L^{-1}EWV_\tau^{-1}W^TEL^{-T}\succeq0.
\]

The slow modes of the Hcc-preconditioned camera solve are the near-unit
eigenmodes of `G`.  D12 applies a Gaussian Nyström sketch directly to `G`,
not to `A`: `Y=G Omega` and

\[
\widehat G=Y(\Omega^TY)^\dagger Y^T=Q\Theta Q^T.
\]

Because `0 <= Ghat <= G < I` in exact arithmetic, the low-rank inverse

\[
(I-\widehat G)^{-1}
=I+Q\,\mathrm{diag}(\theta/(1-\theta))Q^T
\]

is SPD and corrects precisely the point-mediated modes missing from Hcc.  In
the original camera coordinates the preconditioner is

\[
L^{-T}(I-\widehat G)^{-1}L^{-1}.
\]

This is a BA-specific sign adaptation of randomized Nyström preconditioning;
the published regularized-PSD formula cannot be copied directly because the
hard directions of `I-G` correspond to the *largest* eigenvalues of `G`.

## Scope and controls

Use the checksum-pinned frozen Eta2 matrix-free kernels and the already
captured systems, without changing the operator, RHS, damping, scaling,
forcing tolerance, or true-residual verification:

- Muell-gba146 outer 12: hard control, frozen Hcc 41 iterations / 42 products;
- Ladybug598 outer 8: shallow control, 2 iterations / 3 products;
- Final1936 outer 0: shallow control, 1 iteration / 2 products.

First reproduce the frozen Hcc solve with rank zero.  A result is invalid if
the iteration count differs or the final true relative residual differs by
more than `1e-10`.

Protocol amendment after the rank-4 smoke result and before the registered
multi-rank sweep: add a rank-zero restart-at-8 arm.  Rank 4 from the origin
needed 47 iterations, while the provisional rank-4 delayed arm needed only 13
total iterations.  A plain recurrence restart can itself change finite-CG
convergence, so this control is required to attribute any delayed gain.  The
provisional row is diagnostic only until this control is run; no rank or
native decision was made from it.

## Registered arms

Gaussian sketches use deterministic seeds `2026091300 + rep`, with ranks
`k in {4, 8, 16}` and N=3 seeds per rank.  The stable construction discards
eigenvalues of `Omega^T Y` below `1e-12` of its largest eigenvalue and rejects
any retained `theta` outside `[0, 1)` by more than `1e-10`; it may clamp only
roundoff-sized excess.  Report effective rank, theta range and the residual
of the Nyström factorization.

Two timings are reported:

1. **oracle/start**: build the sketch at iteration zero, then solve;
2. **dispatch/8**: run ordinary Hcc PCG for eight iterations; if unresolved,
   form the sketch, restart the recurrence from the current iterate and
   residual, and finish with the Nyström preconditioner.  A solve that reaches
   eta before eight iterations incurs no sketch or restart.

The dispatch arm is the run-everywhere rule.  Its first eight products, every
sketch product, host eigensystem, transfers, low-rank applications and final
verification are charged.  Rank 32 is excluded before results: dispatch needs
at least `8 + 32 + 2 = 42` Schur products, equal to Muell's entire frozen count
before any setup or remaining iteration, so it cannot satisfy the speed gate.

Following the preregistered restart-only amendment, a Nyström attribution also
requires the selected delayed rank to reduce either post-restart solve products
or total wall versus rank-zero restart-at-8.  If it reaches the same iteration
with extra sketch products, it is strictly dominated even when both beat the
uninterrupted frozen solve.

Eta2 has `tau=lambda`; therefore `G` changes whenever lambda changes.  D12
does not claim sketch reuse across retries or outers.  Any later native arm
must rebuild after a changed lambda.  This directly tests and corrects the
shift-reuse premise in the categorical brief.

## Decision gates

Advance beyond fixed systems only if one preregistered rank satisfies all:

- dispatch/8 reaches the identical true residual on all three Muell seeds;
- median charged Muell time is at least 10% below frozen Hcc and its full
  range is below the frozen range;
- median total Schur products, including the sketch, fall by at least 20%;
- Ladybug and Final skip bit-for-algorithm before the trigger, with no extra
  Schur product;
- no non-SPD or numerical-repair event occurs.

Choose the smallest passing rank unless a larger passing rank is at least 10%
faster.  If no rank passes, stop without a native nonlinear arm.  A favorable
oracle arm alone is mechanism evidence, because it lacks a deployable trigger.

If fixed gates pass, run N=3 on Muell and the nine registered practical target
cells, then N=5 on Final3068 and Venice52 only if speed and quality survive.
Changing a finite-eta direction can change the nonlinear basin; product count
alone is never a promotion result.

## Prior-art boundary

- Frangella, Tropp and Udell, *Randomized Nyström Preconditioning*, SIMAX
  44(2), 2023: <https://doi.org/10.1137/21M1466244>.
- Das, Katyan and Kumar, *A Deflation Based Fast and Robust Preconditioner for
  Bundle Adjustment*, WACV 2021: direct BA deflation prior art.
- The earlier Eta2 Schur-Jacobi arm was rejected natively.  D12 uses Hcc as
  its base and sketches the normalized point coupling, so it is not a layer
  on that rejected arm.

Randomized low-rank preconditioning and BA deflation are established.  The
potential contribution is the `I-G` sign adaptation, fully charged matrix-free
GPU break-even result, and its interaction with loose inexact LM.
