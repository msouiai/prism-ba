# Exact bridge-only evaluation

For a camera and point owned by one cluster, transform both centers/positions
by `(s,Q,t)` and camera orientation by `R'=R Q^T`. Its camera coordinates
become `q'=s q`. For positive finite scale, central projection, radial
distortion and signed depth are preserved. Fixed intrinsics are essential to
this first comparison. No metric priors are present.

For fixed cluster ownership, partition the unchanged original objective:

```
F(T) = F_internal(initial) + F_cross_cluster(T).
```

Thus `J_collective=0` on every internal residual, and coarse GN curvature/RHS
can be accumulated entirely from cross-cluster observations. Nonlinear trial
costs also require only those observations plus the constant internal term.
The implementation keeps each landmark unique and moves the entire camera/point
cluster. It verifies the full objective and valid depths before returning the
coarse state; a failed verification returns the immutable parent.

This does not apply to a linear finite update in the collective tangent basis.
That path preserves internal projections only to first order, so evaluating its
trial cost on cross-cluster observations alone would mis-score the candidate.
The matched linear comparator continues to evaluate all observations.

The implementation also rejects nonfinite or extreme incremental scales,
records numerical failures, and retains an ordinary-BA fallback. The eight-step
schedule, coarse damping and line search otherwise match the original T4 arm.
Roundoff-sized differences in the zero internal Jacobians may lead to minute
endpoint differences; the equivalence tests measure these explicitly.

This is an exploitation of known submap invariance, not a claim that local
frames or separator-only global motion are new. See the prior-art discussion
in [T4_MATH.md](../geometry_agenda/T4_MATH.md), especially
[Ni, Steedly and Dellaert, sections 3.1–3.4](https://dellaert.github.io/files/Ni07iccv.pdf).
The empirical question here is whether the reduced coarse cost repays partition
setup and improves total time to the same objective on BAL-derived problems.

The new samples retain every camera and every observation of selected points.
They do not preserve every original graph edge: point sampling still changes
coupling and may remove rare bridge tracks. Three sampling seeds probe that
sensitivity but do not certify full-BAL transfer.
