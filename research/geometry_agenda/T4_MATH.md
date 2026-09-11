# Why finite collective motion can help when linear coarse motion stalls

For a cluster similarity `(s,Q,u)`, update a point and camera center by the
same `X'=s Q X+u`, `C'=s Q C+u`, and set `R'=R Q^T`. Then
`R'(X'-C')=s R(X-C)`: an internal pinhole projection is exactly invariant.
The same holds for fixed central radial distortion, since normalized image
coordinates remain unchanged. It does not hold for metric priors that constrain
scale. Our first prototype has no such priors.

In the native chart `R+=Exp(dw)R`, `t+=dt`, `X+=dX`, the tangent of a cluster
increment `(omega,u,a)` at identity is

```
dw = -R omega
dt = a t - R u
dX = -[X]_cross omega + u + a X.
```

Both coarse arms use exactly this basis and `K=J B`. The linear arm applies
`Retr(B delta)`; the nonlinear arm applies the exact finite similarity. The
two have the same first derivative but different finite paths. Consequently,
internal observations contribute zero to the ideal collective Jacobian while
the linear path can incur higher-order internal reprojection error. The finite
path concentrates optimization on relative cluster alignment without paying
that artificial internal penalty. This is a model-path distinction, not a
more accurate solve of the same linear system.

The point ownership constraint is essential. A point is transformed once,
with exactly one cluster. Giving a bridge point to the wrong region turns
previously internal constraints into cross-cluster constraints for the proposed
motion. Even correct camera clusters can then make a poor coarse space.
The v1/v2 comparison tests this explanation; it does not duplicate landmarks
or remove difficult observations.

The covariance of the original image noise, damping and geometry must not be
confused. The eigenvalue diagnostic uses `K^T K` without LM damping and a
state-unit metric frozen from the initial fine-space basis. Entire cluster0
is fixed in the coarse problem. Disconnected clusters have no information
about their relative similarities and cannot be recovered by any damping rule.

## Position relative to existing methods

Multigrid BA restricts approximate gauge modes to aggregates, applies local QR
to construct a prolongation basis, and uses a Galerkin coarse linear operator.
It explicitly studies the setup/fill tradeoff. Our nonlinear trial differs
from applying a linear correction in such a basis; the matched linear arm
isolates that finite-path effect.
[Multigrid for BA, sections 3.1–3.6](https://arxiv.org/html/2007.01941).

Submap BA already parameterizes cameras and points relative to local base
frames, optimizes base/separator variables, and caches internal linearizations
during global alignment. This is close prior art for collective nonlinear
motion. Our reduced prototype has only cluster similarities, recomputes all
original residuals, and does not implement that paper's eliminated separator
system. Finite group transforms or local frames alone are not a novelty claim.
[Ni, Steedly and Dellaert, sections 3.1–3.4](https://dellaert.github.io/files/Ni07iccv.pdf).

Nonlinear domain decomposition and FAS-RASPEN also establish nonlinear coarse
corrections, applied multiplicatively with local solves. We use a restricted
BA optimization manifold, not the FAS coarse residual equation or its Newton
preconditioner, and inherit no convergence theorem from it.
[Dolean et al., equations 20–22](https://arxiv.org/html/1605.04419).

A possible contribution would need a defensible geometry-adaptive coarse
space and schedule that transfers to real BA and beats these simpler controls
in total time. The current synthetic evidence alone is insufficient.
