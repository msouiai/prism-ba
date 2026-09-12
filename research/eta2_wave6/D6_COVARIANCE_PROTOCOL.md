# D6 protocol: posterior camera variance as a geometric-starvation gate

Registered before computing a posterior covariance at any supplied state.

## Question

Effective resistance detects count starvation but misses Venice camera 34,
whose late weak direction is a focal/optical-axis-translation ambiguity despite
2,959 observations.  The categorical map proposes the diagonal of the reduced
posterior covariance as the statistical definition of starvation.  D6 asks
whether that global quantity adds information beyond the already tested local
Schur-block spectrum before paying for Hutchinson probes or attaching a prior.

## Fixed states

Use the five archived `venice-terminal-0..4` states from the failed static
long-track-damping runs.  All have raw-step/radius near 428 and camera 34 carries
more than 99.99% of the squared raw-step norm.  Use the selected rejected
opening attempt from each of the three archived successful-opening runs as a
negative control: raw-step/radius is near 1.55, the top five cameras carry only
about 26.6%, and no starved camera explains the rejection.

No optimizer rollout is part of D6.

## Operator and quotient

At each state, independently rebuild the coherent FP64, active-8-coordinate
scaled Schur matrix from the original observations and captured state:

`A = E(Hcc + Q_intr - W V_tau^-1 W^T)E + lambda I`.

The inactive k2 coordinate is removed.  Build the seven global Sim(3) camera
modes by finite differences of the code's own left-SO(3) retraction, transform
them to Eta2's scaled coordinates, and form an orthonormal complement `Q`.
The gauge-quotient damped covariance is

`C = Q (Q^T A Q)^-1 Q^T`.

For each camera report the trace and largest eigenvalue of its 8x8 diagonal
block in `C`.  The preregistered starvation score is the largest block
eigenvalue, since the measured failure is one directional ambiguity.

Comparators are fixed before analysis:

1. inverse smallest eigenvalue of the camera's 8x8 diagonal Schur block;
2. inverse unique observation count.

Report ranks, top-one identity, the fraction of raw-step squared norm carried
by each score's top one and top three, and Spearman rank correlation between
each score and raw per-camera squared norm.  Do not tune a quantile or prior.

## Gate

A native stochastic-diagonal or prior experiment is justified only if:

1. posterior top one is camera 34 in at least four of five terminal states and
   captures at least 99% of raw-step squared norm in each such state;
2. the posterior gives camera 34 a strictly better rank than the local-block
   comparator in at least two terminal states, or identifies a different
   top-one camera that captures more raw-step energy; and
3. all projected operators are positive definite and all reconstruction and
   archive checks pass.

The opening controls are descriptive because their global ratio is below any
plausible emergency trigger.  If the posterior merely duplicates the local
block rank, stop: an exact inverse is then an expensive way to recover a score
already available from the Schur diagonal, and wave 3 already showed that a
broad threshold on that score is not a useful actuator.

## Reproducibility

Record the BAL, archive, member, protocol, and analysis hashes.  Extract states
only under `/dev/shm`, validate every retained member used, and delete restored
files after each state.  All matrix symmetry and factorisation errors are
reported.
