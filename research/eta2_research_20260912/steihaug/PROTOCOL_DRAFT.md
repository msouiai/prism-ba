# Brief 3: boundary-truncated PCG, protocol draft

Written before any STCG GPU run, 2026-09-12. This is a correctness-ready
prototype protocol; the parent campaign must freeze the benchmark manifest
before running a comparison grid. No result or promotion is implied.

## One candidate

Frozen Eta2 flags and CLI, plus `OCA_STEIHAUG=1` everywhere. No tuning knobs,
model-progress stop, second candidate, Krylov recycling, or objective change.
The source and all 44 headers must match the champion manifest. Its storage
remains compact FP32 fragments with principal arithmetic in FP64.
Both derived-binary arms enable `OCA_STCG_ATTEMPTS=<run>/attempts.json`.
This common host-clock trace records an entire attempt with a scope timer,
including numerical-repair `continue` paths, and writes its buffered rows at
solver exit. It adds no CUDA synchronization, candidate norm, or matvec.
Record both time spent entering retries and time spent on attempts not
accepted; these are different fractions. Original-binary compatibility rows
cannot provide this new trace and are not speed-comparison rows.

PCG retains the champion's adaptive residual forcing and camera-block
preconditioner. At each attempt, let its actual factored preconditioner be
`M=L L^T`, including the factor's numerical fallback. Define the trust region
by `||z||_M = ||L^T z||_2 <= R`. Compute `x^T M x`, `x^T M p`, and `p^T M p`
directly from this factor, not from an orthogonality-dependent recurrence.
On the first PCG iterate whose full update crosses the radius, solve the
scalar boundary equation and stop at `x+tau*p`. Point back-substitution then
uses those cameras. This includes all metric kernels and synchronizations.

The first ordinary solve is unbounded until the usual forcing/cap stop;
initialize `R` to its finite positive M-norm, otherwise 1. This preserves the
ordinary first camera direction before nonlinear checks. If a finite
curvature-cutoff event occurs before this bootstrap, initialize the radius
to `sqrt(r^T M^-1 r)` at the initial iterate (fallback 1), then take the
positive boundary root. A non-finite curvature or invalid boundary equation
retains the current finite iterate for ordinary nonlinear evaluation;
it is logged as an invalid arithmetic event, not negative curvature.

At a finite curvature cutoff `pAp <= 1e-14 pp`, take a boundary proposal and
skip the champion's persistent damping-floor repair. This is an experiment
in responding to the *computed* operator; it does not assert the underlying
damped Gram system has a saddle. A rejected proposal still shrinks the
radius and raises the attempt's damping through the ordinary controller.

All proposed/rescued camera norms and radius acceptance use the same M from
that attempt. Keep Eta2's `rho > .1`, full objective prediction, point rescue,
backtracking, `R/4` / `2R` update, and lambda/radius update, including the
accepted-interior lambda reduction. The retained radius is a dimensionless
scalar in the **new attempt's metric** when M is rebuilt. This defines a
variable-metric TR policy; it does not transport a physical ellipsoid or
prove the previous stale-metric concern is solved. Both the norm change and
curvature response are part of this arm and cannot be attributed separately.

## Correctness gate before performance

1. Verify frozen source/header hashes; reverse all exact source substitutions
   and recover the frozen source byte-for-byte. Disabled code executes the
   original arithmetic branches and allocates no STCG device buffers.
2. Test the shared host boundary routine on SPD interior/boundary cases,
   an indefinite matrix, non-identity M, roundoff-size boundary errors, and
   large dynamic ranges. Compare interior PCG with a dense solution and
   boundary solutions with the M-norm equation and decreasing quadratic.
3. Build the native derived source; then, only with the GPU coordinator's
   go-ahead, run a tiny BAL fixture under compute-sanitizer, check all
   accepted steps satisfy their logged M-radius, and run a same-binary
   disabled-arm compatibility gate. Compiler changes can perturb trajectories;
   source parity is not a binary-identity claim.

## Subsequent registered grid

Parent supplies the frozen nine scene/target cells and time budgets. Run N>=3
per arm/cell; Venice52 and Final3068 hit-rate rows require N>=5 (prefer the
campaign's N=10). Use the existing full-objective targets, same score_init,
and count missed targets explicitly. Record native time to target, full final
cost, accepted/rejected attempts, retry wall, PCG work, boundary/cutoff event
acceptances, all metric overhead, and lambda/radius trajectories. Both signs
of change must appear. No tail or hit-rate inference from witness samples.

Kill if curvature-boundary attempts are accepted less often than the frozen
floor-rule restarts and time to target does not improve. Independently, do
not promote absent the standing >0.15% median cost criterion or disjoint
observed time-to-target ranges; apply the campaign's no-regression rules.
Practical-target traces with zero curvature events test boundary truncation
and metric effects only, not removal of the persistent floor.

## Contribution boundary

Steihaug-Toint PCG and variable-metric trust regions are established methods.
This is an ablation of their fit to the frozen GPU BA architecture, not a
claim to have invented a trust-region solver. The optional model-decrease
stopping rule is omitted because the prior ledger already tested it.
