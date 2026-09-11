# T7: spectral pruning does not beat a simple menu

The exact filter derivation is correct; the proposed inexpensive pruning
controller fails the registered nonlinear-quality gate. No new filter shapes
or native GPU integration are justified by this screen.

For D=lambda*M and fixed SPD M, whitening makes the scalar response
`f(k,lambda,h)=(1-(lambda/(h+lambda))**(k+1))/h`, with value
`(k+1)/lambda` at zero. Tests cover general SPD metrics, null modes, recursion
indexing, and a gauge-fixed BA system. Maximum BA recursion/closed-form error
was 1.06e-14. The camera Schur change from jointly changing point/camera
damping had a 0.334 non-scalar fraction in the explicit counterexample.

The online estimate uses twelve RHS-seeded Lanczos steps, with charged
operator assembly and reorthogonalization. On forty development parents,
thresholds .01/.03/.10 retained on average 18.43/15.20/7.45 of twenty candidates,
but preserved the registered true-cost quality only on 38/38/22 parents.
The frozen threshold is therefore zero. On forty held-out parents those
thresholds passed 39/38/24 times; none salvages the development decision.
Even the .01 proxy merged steps whose exact RHS-weighted relative distance
was 0.187 on held-out states. Approximate spectral similarity is not a
certificate of similar nonlinear cost.

N=3 complete solves on ten held-out seeds in each of two families give:

| Menu | Speed vs full, depth | Speed vs full, rotation | Pooled median |
|---|---:|---:|---:|
| Full: five dampings x four depths | 1.00x | 1.00x | 1.00x |
| Five dampings, depth zero | 2.80x | 1.87x | 2.78x |
| One damping, four depths | 3.23x | 3.81x | 3.80x |
| Spectral rule, frozen at no pruning | 0.85x | 0.85x | 0.85x |

All four arms reach all sixty targets. At target crossing, all arms share
three of twenty seed-level geometric failures (point NRMSE > .15); this is
not a geometry-certified convergence claim. The spectral feature consumes
14.4% of its runtime. The simple four-candidate menu is 1.36x faster than
the simple five-candidate menu in this reference, so beating the wasteful
twenty-candidate menu alone would not establish a useful new controller.

## Scope and implementation audit

These are six-DOF, fixed-intrinsics CPU experiments with coupled full-system
damping. They are not a matched ablation of the legacy native five-shift
menu. Eta2's `classical_lm` route requires one shift and uses tau=lambda.
The legacy menu holds point factors fixed while varying camera shifts
within an attempt: shared shifts can be valid there. A change of effective
point damping between attempts invalidates those numerical factors and
the corresponding reduced operator. The coupled full-system grid here
refactors for each lambda and reuses factors only for successive RHSs at
the same parent, metric and lambda.

The [OCA paper](https://arxiv.org/html/2411.06343), section 3.2, already derives
the recursion from an approximate optimal-control construction; its imaging
example is orthographic cryo-ET. [PowerBA](https://arxiv.org/pdf/2204.12834),
section 4, expands the inverse of a fixed damped Schur system. Increasing
its truncation order improves that linear solve, whereas the simplified
OCA recursion here changes the filter toward the undamped inverse. A
geometric-series identity alone is not a novelty claim.

Reproduce with `check_spectral.py`, `t7_snapshots.py --split development`,
then `--split held_out`, and `run_t7.py` for the same two splits. The frozen
rule, independent NPZ parents, all candidate outcomes, exact-spectrum audits,
work counters and convergence traces are retained alongside this report.
