# O2 mathematical audit and native integration contract

This is preparation, not a performance result. `PROTOCOL.md` fixes the proposed
intervention. Christy–Horaud1996 and the full Oliensis–Hartley ECCV2006 paper
have been read. The later TPAMI2007 version is identified bibliographically;
its full text has not been read and is not silently substituted for ECCV2006.

## Analytic observation model

Let `a=s`, `D=a*Yz+(1-a)*d0`, `q=(u,v)=-Yxy/D`, `r2=q'q`,
`h=1+k1*r2+k2*r2^2`. The scored SIMPLE_RADIAL convention fixes `k2=0`; retaining
the zero-masked algebra in the primitive matches the native nine-column layout.
Pixels are `f*h*q`, residual is pixel minus observation. The stage derivative is

```
J_qY = [ -1/D,      0, -a*u/D
             0, -1/D, -a*v/D ]
J_pixel_q = f * [h I + 2*(k1+2*k2*r2)*q*q']
J_pixel_Y = J_pixel_q * J_qY.
```

Native cameras retract by `R+ = Exp(omega) R`, `t+ = t+dt`, and points by
`X+ = X+dp`. With `Q=R*X`, the joint first-order camera-coordinate direction is
`dY=omega cross Q + dt + R*dp`. Rotation Jacobians use `Q`, not `Y=Q+t`, since
the native rotation does not rotate the existing translation. Camera intrinsics
have derivatives `h*q`, `f*r2*q`, and zero for the masked k2 column. Point
Jacobians are `J_pixel_Y*R`. Finite joint retraction includes the second-order
term `omega cross (R*dp)`; it must not be omitted from actual trial costs.

For each observation the GN prediction of a full direction is
`-r'*(Jc*dc+Jp*dp) - 0.5*||Jc*dc+Jp*dp||^2`. This includes camera–point cross
terms. Stage acceptance must use this stage prediction and stage actual cost,
while target reporting independently uses original L2.

## Corrections to tempting interpretations

* At the initial state, `Yz=d0`, so all stage costs equal original cost. Their
  gradients differ: sensitivity to current depth is multiplied by `s`. Cost
  equality is neither tangency nor a majorization guarantee.
* Even with fixed cameras and intrinsics, distorted `s=0` is not a linear
  least-squares problem. In one dimension take `q=x`, `f=k1=1`, observation10.
  At `x=0.5`, `F=0.5*(x+x^3-10)^2` has `F''=-25.0625`. Joint rotation/point
  optimization is nonlinear even with distortion removed.
* Keep signed depths. If `d0=-1` and current `Yz=1`, the denominator vanishes at
  `s=0.5`, although both endpoint projections are finite. A homotopy can create
  an intermediate pole. The protocol rejects nonfinite proposals and records a
  domain failure on entering an invalid stage; it does not clamp or drop data.
* At `s=0` each camera's optical-axis translation has exactly zero image
  derivative. Extra unobservable directions are expected and damping must
  handle them. There is no claim of a globally convex or fully ranked opening.
* Frozen per-observation depths are not a camera's single weak-perspective scale.
  Christy–Horaud's calibrated affine reconstruction and this sparse distorted
  BA schedule are different procedures. CIESTA's error and its convergence
  hypotheses do not automatically apply to this objective schedule.
* Switching to `s=1` restores the original model, not the original trajectory.
  Changes in geometry, intrinsics and basin accumulated during staging survive.

## Frozen-source coverage ledger

The pinned source is `eta2_champion/source/prism_eta2.cu`; line numbers below
are anchors in that file, not promises about the derived build.

| Path | Required treatment |
|---|---|
| `MFAssemble`, ~1233 | Stage residual **and** analytic camera/point Jacobian; update separately computed normalized-image radius used in `r2acc` regularization statistics. Compact fragment storage and assembly order unchanged. |
| `ComputeCost`, ~2871 | Stage cost wrapper over a shared analytic projection primitive; preserve a separately callable original-cost function for logging/targets/export. Cover the default block-reduction kernel and all enabled backtracking paths. |
| `ComputeBacktrackCost`, ~2910 | Must route to the same stage cost. An unimplemented bounded alternate kernel must be explicitly rejected for O2. |
| `full_step_model.cuh: MFDirectFullModel` | Replace observation directional residual model with the same stage primitive; retains joint camera–point cross terms and all actual selected masks. |
| `point_safeguard.cuh: PrismTrackObservation` | Both keep and move evaluated with the same stage and **original observation index**, despite point-major traversal. No inference from a thread index. |
| Schur products, factors, point back-substitution | Consume stage fragments, residual RHS and diagonals consistently. No isolated operator swap or extra camera damping. |
| `ScoreTail`, ~10200 | Trial retraction remains native. Its cost wrapper and later full-model/safeguard must all refer to the same stage. |
| `SolveMFreeShiftedCG` stage lifecycle | Capture immutable `d0` once, count every attempt, advance only under the registered rule, refresh numeric caches and objective-dependent histories, preserve current lambda/radius/floor and cumulative work. |
| FTOL/convergence, ~11980 | Evaluate within-stage costs/history only. A surrogate stop jumps to the full objective rather than terminating the run. |
| `TargetReached` calls, ~9718/11980 | Disabled for surrogate stages. Original-objective crossings logged separately in both directions. |
| `RunLog`, CSV, final `RESULT` | Export original L2 only; label stage/internal cost in separate O2 trace so a surrogate result cannot enter the benchmark ledger. |
| Replay/checkpoint import | Existing snapshots lack stage/depth/history fields. Explicitly reject O2 replay until a versioned serialization is implemented. Fresh-input grids do not need it. |
| Alternate algorithms/robust/shared/JIT/stride paths | O2 initially supports only the frozen unshared CD=9, k2=0 champion configuration. Unsupported paths require a fail-fast guard, not partial coverage. |

An implementation must retain a default-off, inverse-patch proof against all
modified source/header files. Static coverage is necessary but insufficient:
tiny native stage gradient, point normal-equation and prediction checks must
exercise the actual assembled fragments and masked/backtracked trial directions.

## Primary-source boundary

[Christy–Horaud, TPAMI1996](https://inria.hal.science/inria-00590057) was read in
full. Their method iterates calibrated weak-perspective or paraperspective
reconstruction, with depth-dependent correction of image measurements and a
Euclidean upgrade. Section6.2 discusses the size of neglected approximation
terms; it does not establish a convergence theorem for the present BA schedule.
This is prior art for affine-to-perspective reconstruction, not an equivalence
between their algorithm and O2. Archived public PDF provenance is in
`literature/sources.json`.

[Oliensis–Hartley, ECCV2006](https://link.springer.com/chapter/10.1007/11744085_17)
was read in full from the [publisher PDF](https://link.springer.com/content/pdf/10.1007/11744085_17.pdf).
Its SIESTA iteration alternates rank-four approximation with projective-depth
updates. The normalized algebraic error can decrease toward trivial solutions;
balancing can cycle. CIESTA instead regularizes optimized projective depths
toward one. Its conclusions require a regularization condition; stationary-point
and unique-limit results add spectral-gap and local-minimum assumptions. O2
neither optimizes those projective depths nor minimizes that regularized error,
so none of those theorems proves this schedule converges. The paper also allows
that a few simple iterations can be useful BA initializers despite problematic
asymptotic behavior. The [TPAMI2007 extension](https://doi.org/10.1109/TPAMI.2007.1132)
has been identified, but only its abstract was available in this audit.
