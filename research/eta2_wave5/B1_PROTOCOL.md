# B1 factored-Jacobian fragment protocol

Registered before building or running the active arm.

## Hypothesis

B0 assigns 53.19% of practical-panel native wall to Krylov and another 10.46%
to point-factor plus reduced-RHS preparation.  The frozen champion stores each
camera--point cross block as 27 FP32 values per observation.  Those values are
read on every Schur product and candidate back-substitution.  The same block
can be reconstructed from the projection derivative `dr/dY` (6 values), the
rotation lever arm `R*X` (3), and the two active intrinsic columns (4): 13 FP32
values.  Camera-major ordering should make the additional 3x3 camera rotation
read cache-resident.  The expected gain is lower fragment bandwidth without a
new nonlinear policy or a different forcing rule.

## Frozen arm

The only active flag is:

```
OCA_W5_FACTORED_J=1
```

The implementation is restricted to the frozen Eta2 layout: CD=9,
SIMPLE_RADIAL with k2 fixed, unshared intrinsics, L2, one shift, compact
camera-major fragments, diagonal equilibration, explicit camera-block PCG,
and the fused reduced-RHS/Schur-diagonal preparation.  It retains the existing
six-value FP32 point-Jacobian rows used by point QR.  This isolates compression
of the 27-value cross block: stored fragment traffic and capacity fall from
33 to 19 floats per observation, while each Krylov cross-block stream falls
from 27 to 13 floats plus a cacheable camera rotation.

The active kernels contract the two Jacobian rows directly; they do not form a
temporary 9x3 block.  Assembly, point factors, damping, forcing, scoring,
acceptance, stopping, and controller state are otherwise unchanged.  The
disabled derived binary must match the frozen binary within 0.15% before the
active arm is eligible.

## Diagnostics and run order

1. Run an initial-state algebra audit on Ladybug49.  Reconstruct every 9x3
   block and compare it with the champion's direct FP64-product-then-FP32-store
   definition.  Report relative Frobenius error and maximum absolute error.
2. Run N=3 disabled-derived versus frozen-binary compatibility on the calm
   Ladybug539 1.01 target.
3. Run N=3 paired active/off trials over the nine registered practical target
   cells, alternating arm order and reversing cell order on odd repetitions.
4. If the panel has no quality failure, run N=3 on registered Muell and N=5 on
   Final3068 and Venice52.  Profile at least one Krylov-heavy practical cell
   and Muell with the existing phase timers.

Primary metrics are time to the identical registered target, hit rate,
endpoint cost, products, outers, rejects, native wall, and phase time.  Report
crossings in both directions and ranges.

## Decision rule

Promote only if the geometric-mean panel target time improves, at least one
Krylov-heavy cell has disjoint faster ranges, and no tail hit rate or endpoint
fails materially.  Kill if the reconstructed operator misses a registered
target that the control reaches, if endpoint cost moves by more than 0.15% on
a stable cell without a compensating tail benefit, or if reconstruction ALU
and camera-state traffic erase the fragment-bandwidth saving.  A microkernel
gain without end-to-end target-time gain is recorded as a systems negative.

No parameter is selected per scene.  B2 mixed-precision refinement and B5
square-root products are separate experiments and are not enabled here.
