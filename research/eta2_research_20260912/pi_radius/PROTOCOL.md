# Brief 6 registration: one PI radius policy

One global arm, frozen before measurements: `OCA_PI_RADIUS=1`, epsilon=0.3,
kI=0.3, kP=0.4. All frozen Eta2 flags, storage, forcing, point solves,
acceptance, backtracking and stopping remain as in champion.json. No learned
parameters, per-scene tuning, new candidate menu or objective change.

For an accepted proposal, e=max(1e-6,abs(1-rho)). On its first accepted
proposal initialize e_previous=e, so the derivative term is zero. Set
factor=clamp(exp(.3*log(.3/e)+.4*log(e_previous/e)),.25,2),
R_new=max(1e-14,R_old*factor), and retain e as accepted-step history.
Rejected steps retain the original radius rule and do not update history.
Nonfinite accepted-error inputs use the original rule and are logged.
Retain the original lambda/radius relation, numerical floor and the
accepted-interior lambda reduction; the latter is explicitly an existing
exception to a pure lambda*R^2 invariant. A rho above1.3 can shrink R by
design. This arm can prevent entry into a storm but cannot change the
response inside an otherwise identical sequence of zero-accept retries.

Verify the frozen source/header hashes and recover the source exactly by
reversing the patch. Test deterministic controller sequences and invariants;
run a tiny native fixture and N3 original-versus-derived-off compatibility.
Then use the shared frozen nine practical targets, N3 per arm, plus
Venice52 and Final3068 targets, N5, native cap60/outercap600. Alternate order.
Compare same-binary off against on, retain original compatibility rows,
all endpoint audits, score_init, hits/misses, rejection/alternation counts,
retry wall, PCG work, and both signs of time/cost change. Count all overhead.

Kill if storm-scene rejection counts do not improve with disjoint N>=3
ranges. No promotion without the standing >0.15% median cost improvement
or disjoint target-time ranges and no >20% practical median-time regression
or lost sampled target reliability. Inactive or ambiguous cells are not
wins. This tests the supplied gains; failure does not refute all PI policies.

The ODE analogy and prior art are in ../literature/MATH_AND_PRIOR_ART.md.
Accepted-step LM policies are already smooth in other solvers; the new
ingredient being tested is accepted-error history. No controller-stability
theorem is claimed for this nonlinear, inexact, rescued-step plant.
