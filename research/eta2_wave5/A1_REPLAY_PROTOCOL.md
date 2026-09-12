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
