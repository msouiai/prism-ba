# D20 protocol: quotient projection of one sloppy camera mode

Registered 2026-09-13 after D19 closed and before scoring a D20 nonlinear
proposal.  This changes the finished direction, not the operator or PCG path.

## Mathematical rule

Use D18's immutable geometric-starvation gate: `||z_raw||/R > 100`, one camera
carries more than 99% of raw squared norm, and that camera also has the
smallest active local scaled-Schur eigenvalue.  Let `q_0` be the normalized
weakest eigenvector of that camera's 8x8 block.  Apply the orthogonal quotient
projection

`z_i <- z_i - q_0 (q_0^T z_i)`

to that camera's eight active coordinates exactly once on the attempt.  Leave
every other coordinate unchanged, recompute the full camera norm, and apply
Eta2's ordinary global radius clip if still needed.  Back-substitute points
from the actual projected/clipped camera direction and evaluate the full model
and full plain-L2 objective on that joint step.

This is the active manifold-boundary limit for one locally unobservable
combination.  Unlike D19, it cannot change healthy cameras before the ordinary
clip.  Unlike D16, it retains the selected camera's seven observable
directions.  There is no dose, rank, cap or threshold sweep.

## Fixed-state gate

Use all five checksum-pinned Venice terminal states.  Recompute and audit the
weak eigenvector against the archived direct-Gram block.  Three deterministic
CPU scoring repetitions must agree.  D20 earns a native arm only if:

- camera 34 is the sole selected camera in 5/5;
- the removed rank-one component contains at least 99% of total raw-step
  energy in 5/5;
- post-projection raw/radius is at most 10 in 5/5;
- all other camera coordinates are exactly unchanged before global clipping;
- true decrease improves by more than 0.15% and rho does not decrease in 5/5;
- independent full-objective and model audits pass.

## Native gate if earned

Derive from the deterministic B6v7 source first; feature-disabled compatibility
must match endpoint SHA256, accepted costs and controller decisions exactly.
Run Venice52 N=5 at target 243740.27.  Advance only with at least 3/5 hits.
Then run Final3068 N=5 and the nine practical cells N=3.  Promotion requires no
Final hit-rate loss, no endpoint regression above 0.15%, and no disjoint time
loss on five or more practical cells.  Report trigger counts, selected camera,
removed energy, norm ratio, products and all wall.

No native threshold tuning follows a failed gate.  The scored objective stays
plain-L2 SIMPLE_RADIAL, unshared intrinsics, `k2=0`; the frozen Eta2 champion
remains the winner until every gate passes.
