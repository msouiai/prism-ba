# T4 registration: collective corrections

Start with three clusters of four cameras and 60 points each. Each point is
observed by all four local cameras. Adjacent clusters share 4 (weak) or 16
(strong) bridge points per side, each observed by two remote cameras; each
landmark remains one variable. Include zero-bridge/disconnected cases.
Observations receive 0.15 px noise. Initial cluster similarities use bounded
rotations (0.15 radians per component), translations (0.4 world units) and
log-scale (0.2), with small internal pose/point perturbations. Seeds 0–9
development, 100–109 held out, three rotated-order timing repeats.

Arms: ordinary LM; up to eight opening linear coarse steps in a 14-dimensional
collective tangent basis, then ordinary LM; and the same coarse problem using
exact finite Sim(3) transforms, then ordinary LM. Cluster0 is fixed; full BA
retains the original camera0/point0.z gauge. All observations participate in
the objective. Known generating partitions first, automatic partitions only
after a successful controlled gate. Coarse initial lambda=1e-3 with diagonal
GN scaling, exact valid-cost line search at 1, 0.5, 0.25; halve on success, x4
on failure. Disconnected zero-information coarse systems skip, not fabricate
motion from damping. Fine LM is unchanged from T2.

Equal total cap 2 seconds (including every setup, coarse step and fine step),
max80 fine attempts; targets frozen as F(truth)+1e-4*(F0-Ftruth). Also record
bridge residual, undamped coarse eigenvalues in a fixed state-unit metric and
one globally aligned geometry error. Disconnected rows diagnose unobservability
and never count as successful relative-geometry recovery from a low cost.

Gate: nonlinear coarse >1.10x speed versus both fine-only and same-basis linear
coarse, no extra target misses or point-NRMSE>0.15 cases, both observable bridge
settings. If that passes, validate a geometry-weighted automatic partition and
larger synthetic scale, then small real scenes. CPU reference cannot replace
Eta2 without matching free variables, gauge and hardware.
