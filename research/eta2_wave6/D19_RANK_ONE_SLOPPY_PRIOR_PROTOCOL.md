# D19 protocol: rank-one sloppy-mode camera prior

Registered 2026-09-13 after D18 closed and before building or scoring D19.
This is a different actuator, not a relaxation of D18's failed 95% gate.

## Hypothesis

D18 regularises every eigenvalue of camera 34's scaled Schur block below the
scene reference.  It fixes all five terminal Venice directions, but its
best-balanced dose retains only 94.475% of the ungated camera norm.  Information
geometry and manifold-boundary reduction prescribe a narrower change: suppress
only the single sloppiest local combination, leaving the camera's seven other
active combinations and all other cameras in the original model.

Use D18's immutable gate unchanged: raw/radius above 100, one camera above 99%
of raw squared norm, and that camera also has the scene's smallest active local
Schur eigenvalue.  Let `(mu_0,q_0)` be that camera's smallest eigenpair and
`mu_ref` the median largest active eigenvalue of other cameras.  Add exactly

`Delta_1 = max(0, mu_ref - mu_0) q_0 q_0^T`

to the scaled operator and its camera preconditioner.  Resolve at the same
lambda, tau, radius and Eta2 forcing tolerance.  This has no dose, rank or
threshold sweep.

## Fixed-state gate

Reuse the five checksum-pinned corrected D18 Venice systems.  Compare control
and rank-one prior, each for three deterministic linear repetitions, and score
the clipped/recompleted full joint step on the plain-L2 objective.  Baseline
direction and cost audits must pass.

D19 earns native rollout only if all conditions hold:

- camera 34 is the sole selected camera in 5/5 states;
- raw/radius is at most 10 in at least 4/5;
- ungated raw-direction norm is at least 95% of control in every state;
- true decrease improves by more than 0.15% in at least 4/5;
- rho never decreases.

If it fails, stop without trying rank 2, another scale, or a weaker/stronger
prior.  If it passes, register a same-binary-off Venice N=5 native gate before
building that arm, followed by Final3068 N=5 and the practical panel only if
Venice reaches at least 3/5.  The frozen Eta2 champion remains the winner until
all native gates pass.
