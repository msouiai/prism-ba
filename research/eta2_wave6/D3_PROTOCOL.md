# D3 protocol: paired full-convergence fragment precision on Final3068

Registered after D2d passed its mechanistic gate and before generating any D3
input or running either arm.

## Arms and paired inputs

Both arms use the deterministic B6v7-derived path, frozen Eta2 flags, full plain
L2 SIMPLE_RADIAL objective, unshared intrinsics, and k2 fixed to zero.

- control: stored Jacobian fragments in FP32;
- variant: stored Jacobian fragments in FP64.

For pair `i`, PCG64 seed `640000+i` generates one field-scaled perturbation at
`epsilon=1e-10` using the fixed D1 transform.  Both arms consume the exact same
BAL bytes, and arm order reverses on odd pairs.  These seeds were not used in
D2--D2d.  Inputs live in `/dev/shm`, their hash and initial FP64 residual-space
distance are retained, and they are deleted after both endpoint states have
been independently rescored in FP64.

The registered target is `1744796.9841897595`, the cap is 45 native seconds,
and the outer cap is 600.  The solver's existing target stop records first
crossing time.  Misses remain in every denominator.

## Sequential decision

The primary outcome is paired target hit.  Only discordant pairs update a Wald
SPRT:

- `q0 = 0.50`: FP64 is no more likely to own a discordance;
- `q1 = 0.70`: FP64 has a useful conditional reliability advantage;
- `alpha = 0.05`, `beta = 0.10`;
- at most 60 total pairs.

The upper boundary is evidence for the registered benefit; the lower boundary
is evidence against a 70% conditional benefit, not proof that FP64 is harmful.
Concordant hits and misses are reported and count toward the 60-pair cap.

Secondary metrics are target time on double-hit pairs, native wall over all
pairs, endpoint cost on double misses, outers, rejects, and Schur products.  A
production-oriented precision candidate requires the upper SPRT boundary and a
median FP64/control target-time ratio no larger than 1.25 on double hits.  If
the reliability boundary passes but the time gate fails, a compact
FP32-high-plus-low-residual representation is permitted as a new experiment.
If the reliability boundary fails or remains unresolved at the cap, no compact
precision format is built from this mechanism.

This cohort measures deterministic robustness to a controlled infinitesimal
input shell.  It is not automatically an estimate of deployment run-to-run
probability and cannot replace the frozen champion's external ledger.
