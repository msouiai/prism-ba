# A1 targeted nonlinear point repair: replay gate

Registered before running `a1_replay.py`.

The two fixed E4 proposals (`hit/6`, `miss/6`) retain their recorded camera
steps and every recorded point step except point 250233.  At the proposed
cameras, that two-observation track is replaced by the best depth-sign-preserving
candidate from a fixed, scene-independent set:

1. the recorded point and the old point;
2. midpoint ray triangulation after numerical inversion of SIMPLE_RADIAL;
3. Hartley-Sturm optimal epipolar correction in the two undistorted pixel
   planes, followed by homogeneous DLT;
4. the bounded old-anchor-ray search already used by wave 4;
5. analytic original-distorted-pixel least-squares polish from every preceding
   candidate.

The Hartley-Sturm candidate is globally optimal only for its two undistorted
image-plane error.  It is a deterministic initializer here, not a claimed
global minimizer of the original distorted-pixel objective.  The selected
candidate is scored only on the original objective.  Depth signs in both
cameras must match the pre-attempt point.  A candidate must also stay at least
as far from every observing camera's projection horizon as the recorded GN
proposal, measured by absolute depth.  This margin was added before any native
run: the first numerical replay exposed an unconstrained LM iterate at
`1.8e-8` of the old depth with a huge stationarity residual.  That iterate is
an approach to the rational boundary, not acceptable evidence of a repaired
point.  The raw Hartley-Sturm candidates were already feasible under the new
margin in both trajectories.  The full quadratic prediction is
recomputed for the substituted point step; a true-cost improvement alone is
not enough.

Replay passes only if both proposals have finite candidates, at least 90% of
the recorded hit/miss point-cost gap disappears, both full predictions are
positive, and both rho values exceed 0.1.  Passing permits a targeted native
kernel and continued-trajectory test; it does not itself establish a basin or
speed result.

## Native detector registered after the replay and before native runs

The native arm uses the same linear-versus-linear-fractional discrepancy as
the O3 attribution pass, with a GPU-cheap scene scale.  For observation `i`,
let `r_lin = r + Jd` and let `r_rat` evaluate the SIMPLE_RADIAL projection at
the first-order camera-frame point `Y + dY` and linearly updated intrinsics.
Flag it when

```
||r_rat-r_lin||^2 / max(||r||^2, 2 F_current / nobs) > 0.5.
```

The mean-squared-residual floor replaces O3's exact median so the detector does
not introduce a sort, sample, host transfer, or extra controller state.  It is
more conservative on the heavy-tailed states of interest.  A point is eligible
only when it has exactly two observations and at least one is flagged.  The
fixed-state detector validation must flag point 250233 in both E4 directions
and touch at most 1% of points in every healthy capture before compilation.

For each eligible point, the native candidate is Lindstrom's two-step
epipolar correction after SIMPLE_RADIAL inversion, followed by the
inhomogeneous least-squares DLT normal equations at the proposed cameras.  On
both fixed E4 directions this produces the same coordinates as homogeneous
DLT to `6e-15` in world space and slightly lower roundoff-level scored cost.
It competes against the recorded GN point at
fixed proposed cameras on the original distorted-pixel track cost.  It can
replace the GN point only when that cost is finite and lower, all observing
depth signs match the old point, and every absolute observing depth is at
least the corresponding recorded-GN depth margin.  The existing full-step
model is then evaluated on the actual substituted joint step.  No periodic or
all-point retriangulation is enabled.
