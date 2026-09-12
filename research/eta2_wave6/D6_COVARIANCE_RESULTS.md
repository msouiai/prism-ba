# D6 result: posterior variance confirms geometric starvation but is redundant

## Verdict

The exact gauge-quotient posterior covariance identifies Venice camera 34 in
all five high-ratio terminal states.  In each state its top-one posterior rank
captures about 99.99956% of the squared raw camera-step norm.  The diagnostic
therefore confirms that the late Venice failure is a genuine global posterior
uncertainty, rather than a low-count graph artifact.

It does not justify a native Hutchinson estimator or posterior-driven prior.
The inverse smallest eigenvalue of the local 8x8 Schur diagonal block also
ranks camera 34 first in every terminal state and captures exactly the same raw
energy.  The registered added-information gate fails in 0/5 states.

## Exact construction

For five archived terminal states and three archived successful-opening
rejection states, the analysis rebuilt the coherent FP64 scaled Schur operator,
removed inactive k2 coordinates, constructed the seven global Sim(3) modes by
finite differences of the solver's retraction, and inverted the operator on
their orthogonal complement.  The scored covariance was

`C = Q (Q^T A Q)^-1 Q^T`.

All eight quotient operators were positive definite.  Projector reconstruction
errors were `1.15e-15`--`1.67e-15`; Schur symmetry error was at most
`2.22e-16`; independently recomputed initial costs agreed with captured costs
to `2.17e-15` relative.  The gauge basis had rank seven in every state.

## Terminal states

The five terminal runs are nearly identical instances of the same failure:
raw-step/radius is 428.257--428.267, camera 34 carries
99.999556%--99.999562% of raw squared norm, and the quotient condition number
is about `3.565e8`.

| Score | Camera-34 rank | Top camera | Top-one raw energy | Median score ratio for camera 34 |
|---|---:|---:|---:|---:|
| Posterior maximum block eigenvalue | 1 in 5/5 | 34 | 99.99956% | 33,916x |
| Local inverse minimum block eigenvalue | 1 in 5/5 | 34 | 99.99956% | 68,223x |
| Inverse observation count | 9 in 5/5 | 41 | 0.0000016% | n/a |

Posterior score has a higher whole-camera Spearman correlation with raw energy
than the local score, 0.535 versus 0.350, but this does not improve the sparse
top-one decision that a production gate needs.

## Opening controls

At each successful-policy opening rejection, raw-step/radius is 1.5469 and
camera 6 is the raw-step leader with only 6.36% of squared norm.  Posterior and
local scores both still rank camera 34 first, but it carries just 0.385% of the
raw step and its posterior score is only 1.51x the camera median.  Posterior
variance is therefore an observability diagnostic, not an attribution of the
current rejection.  A separate high-ratio trigger could avoid acting here, but
would add no information to the already available raw concentration plus local
block spectrum.

## Consequence

The categorical-map cell is useful as a mathematical confirmation:

- graph resistance measures combinatorial support and misses camera 34;
- posterior covariance measures its geometric uncertainty correctly;
- the local Schur block already exposes the same exceptional direction at far
  lower cost.

Wave 3's problem with the local spectral floor was its broad threshold, which
touched 47% or more of cameras, not failure to rank camera 34.  A top-rank
local actuator would be sparse, but the tested camera cap already selected the
dominant camera and still failed natively.  D6 supplies no new actuator
mechanism that changes that result, so it stops before stochastic probing or a
prior-strength sweep.

Machine-readable ranks, spectra, projector checks, archive/member hashes and
provenance are in `d6-covariance-results.json`; the immutable decision rule is
in `D6_COVARIANCE_PROTOCOL.md`.
