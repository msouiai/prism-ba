# Brief 11: native soft-mode kick feasibility proposal

Status: source and math audit only. No native implementation, build or data
has been run for this brief. Await the parent's precise registration before
implementation/grid. Frozen Eta2 remains the baseline. This proposal is a
single intervention at a confirmed FTOL stop, not acceleration across outers,
Krylov reuse, controller-state restoration or a candidate menu.

## Hook and trigger

Track a local `ftol_reason_this_outer` only at the original function-tolerance
and persistent OCA_FTOL assignments to `converged`. Clear it when existing
meaningful-progress rearming cancels convergence. After the original
backtrack stop-confirmation block, and immediately before the final
`if(converged){ ++k; break; }`, queue one pending kick only when the FTOL
reason survives. Existing target checks stay ahead of this trigger; a run
already hitting its registered target pays no kick work.

A precise semantic choice for registration: "confirmed" means the FTOL
stop survives the champion's existing confirmation policy. If there have
been no backtrack rescues, that policy requires no extra confirmation solve.
If the intended protocol requires `backtrack_confirm==true` unconditionally,
register that explicitly; it is a narrower trigger. Do not conflate the
max-consecutive-failures or budget/outer-cap stop with an FTOL event.

Queueing preserves the accepted state and current controller values, cancels
that one stop and lets the ordinary outer index advance. It does not compute
a mode from the just-used pre-accept assembly. At the next outer, require
`need_assembly=true` and let ordinary assembly, point factors, E, reduced RHS
and operator construction finish. The pending hook belongs immediately before
`sweep_attempt`/`sweep_restart` (frozen source around line 10829), after the
`KvS` and full-cost/retraction helpers exist, and **before** the residual-norm
forcing code overwrites `prev_bnorm` (around line 10844).

The hook calls `pcg->Prepare` only for this event to obtain its actual factor.
After an admitted kick, set assembly/factor/point-observation caches dirty and
continue at the same next-outer index. Thus the kick consumes wall/work but is
not falsely counted as a solved LM outer. The following ordinary LM attempt
assembles at the perturbed state. Preserve current lambda, attr_R,
numeric_floor, prev_bnorm, last_rel and backtrack-confirmation/history state.
Reset only stop bookkeeping (`converged`, FTOL/failure streak, `prev_cost`
set to the perturbed cost), which is necessary to allow continuation after
the cancelled stop. Any reset must appear explicitly in the trace. PCG build
bookkeeping is not a substitute for a forcing-history update.

If the event is numerically unusable or the one score fails its bound, honor
the pending stop immediately. No fallback direction, depth or amplitude grid.
If the ordinary budget expires before the pending event, stop normally.

## The actual generalized coarse problem

Reuse the existing K=8 deterministic geometry and one-pass coarse assembly
kernels read-only from `coarse/native/geometry.h` and `coarse.cuh`, but do not
activate the coarse preconditioner. Prefer a small local adapter that calls
the public geometry/kernels directly: the existing `Native::Prepare` includes
unrelated activation gates and a Cholesky-success policy. Do not change those
files or spoof accepted-step history to bypass their gates.

Let Z be the assembled rank-aware rigid/scale camera basis in equilibrated
coordinates, and Ac=Z^T A_lambda Z the native compact-operator matrix, with
coupled point factors and intrinsic solve prior as in the current attempt.
Use the **actual** lower triangular blocks in `pcg->B` to form

```
M_i = L_i L_i^T
B = Z^T M Z = sum_i (L_i^T Z_i)^T (L_i^T Z_i).
```

This accounts for Cholesky safeguards. Reconstructing M as E U E+lambda I
would not necessarily reproduce that factor. B has small size (<=56), and
its SPD, symmetry and finite checks are mandatory. This is a generalized
Ritz diagnostic of A_lambda in the PCG metric, not exact lowest eigenmodes
of the complete problem.

Build the seven known global similarity camera tangents directly in the
code's convention, with global centroid cbar:

```
rotation:    dtheta_i = -R_i omega, dt_i = R_i (omega x cbar)
translation:dtheta_i = 0,          dt_i = -R_i v
scale:      dtheta_i = 0,          dt_i = -R_i (C_i-cbar)
intrinsics: zero; then divide camera components by E_i.
```

These follow the existing independently tested geometry convention. Call the
result G. Verify G is represented by Z to a registered relative tolerance;
Z is locally Euclidean orthonormal, so coefficients are Cg=Z^T G. With
B=Lb Lb^T, the whitened gauge coefficients are `Yg=Lb^T Cg`. Remove their
rank-aware span (up to seven) by SVD/QR. For an orthonormal complement N,
solve the small symmetric eigenproblem

```
T = N^T Lb^-1 Ac Lb^-T N,
z = Z Lb^-T N v_min_positive.
```

Register the rank cutoff and positive-eigenvalue threshold before data; a
natural inherited rank cutoff is 1e-10 relative after column normalization.
Record the complete small spectrum, gauge residual and generalized Ritz
residual. A negative native compact-operator Ritz value is not evidence of a
true BA saddle; retain its value in the trace and do not change the numerical
floor or silently relabel it physical curvature. If no qualifying positive
mode remains, skip the kick and honor the stop.

This removes the seven known similarity camera directions in the camera-PCG
metric. The damped homogeneous point response below need not equal the
physical point part of a global similarity. Do not claim a stronger full-joint
gauge projection or that all remaining modes are physically rigid.

## Full direction, sign and amplitude

Lift `dc=E z` and complete **homogeneous** points
`dp=-V_lambda^-1 W^T dc`; omit the point gradient term. Existing `KvS(z,Av)`
already computes dc in `w` and the positive inverse response in `uu` on this
frozen diagonal native path, so one charged product plus copy/negate suffices.
Copy the direction to owned scratch before any helper reuses those buffers.

Use the existing FP64 full directional model on the full observations:
`a=g^T d`, `b=||Jd||^2`. Choose the sign so a>=0. At exact/toleranced zero,
use a registered deterministic sign convention (e.g. largest-magnitude
camera coordinate positive), never score both signs.

Track the last accepted absolute full-objective gain when each LM attempt
accepts, using the saved pre-attempt cost before it is overwritten. At the
queued boundary, freeze

```
B_up = 0.1 max(last_accepted_absolute_gain, 1e-12 F_pre).
```

Choose the positive alpha satisfying `a alpha + b alpha^2/2 = B_up`:
`alpha=2 B_up/(a+sqrt(a^2+2 b B_up))` for b>0, with the exact linear case
alpha=B_up/a when b=0,a>0. If both vanish or any value is nonfinite, skip.
This is an undamped full-GN predicted **increase**, not a trust-ratio step.
No old-radius clipping, damping reset, point safeguarding or sign menu is
applied to the kick. Log its old-radius ratio for scale visibility.

Retract once and score the full unchanged objective. Admit only finite
`F_trial <= F_pre + 2 B_up`. The upper-bound wording also admits an unexpected
true decrease; if registration intends to require a strictly uphill move,
state that before data. This is intentionally one bounded temporary uphill
intervention, separate from ordinary LM's descent acceptance. Keep all
ordinary LM controller rules for subsequent attempts.

## State retention and accounting

Before adopting an admitted kick, allocate one owned DeviceState snapshot
and copy the pre-kick state into it, including intrinsics. Preserve its cost.
The extra snapshot is only needed after a kick passes its true-cost bound.
At every final exit (target, FTOL, cap, budget or other failure), before final
diagnostics/export, compare current cost with the pre-kick cost and return
the better state. If restoration occurs, copy state and cost back and record
an explicit final-state restoration event/CSV row with measured wall. This
is selection of the better available output, not restoration of an earlier
controller state followed by more optimization.

Original LM steps after the kick remain monotone, so comparing pre-kick
state with final current state suffices; a separate per-outer best-state
copy is unnecessary. This guarantee does not establish dominance over an
independently continued baseline run, but prevents returning only an
unrecovered uphill perturbation. Do not hide its raw trajectory or time.

Count the new assembly/factors, geometry/clustering, host/device transfers,
coarse matrix build, M-Gram, gauge/eigensolve, homogeneous Schur product,
full-model pass, full cost, snapshot/copy and final restoration. The existing
solve clock naturally includes all of these; add explicit phase counters and
wall fields. No GPU barriers beyond required host small-matrix transfers and
existing full-cost/model results are necessary. Mark probe attempts separately
from accepted/rejected LM attempts, without disguising work as zero-CG LM.

## Required checks before any score grid

1. Exact replacement-count and inverse-patch recovery of pinned source;
   disabled-path compatibility using the common trace overhead.
2. CPU dense generalized eigenproblem with nontrivial block L, known gauge
   span and rank deficiency; verify M-orthogonality and basis-convention
   similarity derivatives. Test that reconstructing unsafeguarded U can give
   a different M and that the implementation uses L.
3. Dense homogeneous point-response and full model/amplitude identities,
   sign determinism, zero slope/curvature edge cases, finite-bound rejection.
4. Native small BAL memcheck and event trace showing the mode is built after
   a fresh accepted-state assembly, never on stale normals; assert controller
   values before/after the kick and forcing-history preservation.
5. Injected admitted-unrecovered/rejected kick cases proving final state and
   cost agree with the retained snapshot. Verify target crossing uses the
   actual full objective and all elapsed probe work.

No data have been collected for these choices. The parent must freeze the
precise trigger, gauge/rank thresholds, sign ties, counts/targets and native
kill rule in PROTOCOL_11 before implementation tests/grid.
