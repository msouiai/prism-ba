# Brief 7: fixed full-normal cubic model, specified before witness data

The registered [protocol](../PROTOCOL_07.md) uses the complete variable
`d=(camera increment, point increment)` and captured positive diagonal
`D=diag(E_saved^-2,Dp)`. The point diagonal retains the native positive trace
floor, divided by captured lambda to define Dp. D is held fixed within each
witness. The model is coherent FP64 GN plus the native intrinsic solve prior,
with gradient from the original objective. Intrinsic priors are excluded from
scored cost and undamped-GN acceptance prediction.

Whiten with `y=D^(1/2)d`, `Hhat=D^(-1/2)(J^T J+Qintr)D^(-1/2)` and
`ghat=D^(-1/2)g`. This family has fixed Hhat and ghat. Eta2's eliminated
camera Schur family does not: both point factors and the reduced RHS depend
on lambda. A tiny coherent example tests that obstruction before BAL data.

For each repetition build one fresh Krylov basis from `-ghat`, up to exactly
64 vectors, using two complete Gram-Schmidt projection passes against all
prior vectors. Happy breakdown is declared only if the remaining norm is at
most 1e-14 times the input product norm; record actual dimension and products.
Keep operator products to form `T=Q^T Hhat Q`; record its antisymmetry before
roundoff symmetrization and the complete Q orthogonality error. No vectors are
reused outside the single matched diagnostic pair. The common setup is charged
in full to either hypothetical standalone arm, and actual shared wall is also
reported.

Use the single global rule `sigma=lambda_saved/max(||d_Eta2_saved||_D,1e-30)`.
The projected cubic model is

```
q(y)=ghat^T Q y + .5 y^T T y + sigma ||y||^3/3.
```

Solve `(T+lambda I)y=-Q^T ghat`, `lambda=sigma ||y||` by a bracketed scalar
root to relative residual <=1e-8. Eigenvalues are not clipped or floored; the
root is sought above max(0,-lambda_min(T)). A root requiring an unresolved
hard case fails visibly rather than changing the model. No trial shift is
nonlinearly scored. The matched LM control solves the same projected system
at captured lambda. Neither direction is clipped to the old camera radius,
and neither has points silently replaced by an eliminated solve. Report the
full D norm and camera E norm/old radius for both.

Both proposals are accepted only if the original full objective decreases,
the undamped GN prediction is positive and rho>.1. ARC's own cubic and
regularized quadratic model values are reported separately. Rejection keeps
the original state. Recompute a fresh full-normal stationarity residual for
each result, including its chosen damping; a small projected root residual
is not a full-space accuracy certificate. Count the 64 basis products plus
one fresh verification product per arm, all orthogonalization, scalar work,
assembly and full scoring. No Schur-product equivalence or GPU speed claim.

This is a fixed witness screen, not an ARC rollout: sigma is not updated and
there are no retries. The captured Eta2 and existing coherent rows are context,
never matched timing controls. The gate is accepted decrease >1.2 times the
matched LM control at >=2/3 states, with no >.15% accepted full-cost regression
on the third. Zero versus zero is not a win. Invalid rows stay in the ledger.
