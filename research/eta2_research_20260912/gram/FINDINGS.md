# Brief 4: consistent Gram energy — reproduced, with a necessary qualification

The seeded two-observation stress experiment reproduces the proposed mechanism. In 3,000 independently drawn local systems, FP32 cross blocks combined with FP64 camera/point normals give a negative minimum Schur eigenvalue in **3,000/3,000**, minimum −4.34e−6. Evaluating one consistent Jacobian through the damped residual-energy identity gives **0/3,000** negative values, both for FP64 Jacobians and consistently rounded FP32 Jacobians with FP64 arithmetic. The corresponding consistent product dot products were positive in this cohort too.

This is a deliberately ill-conditioned algebraic cohort, not the frequency of failures on BAL. The seed, actual Jacobian construction, diagonal scaling, depth scales, damping range and every row are retained in `check_energy.py` and `energy_results.json`. No supplied numerical count was treated as measured before this reproduction.

There is a crucial limit to the proposed one-line change. For an approximate point solve, with `e=s-(Jp^T Jp+lambda Dp)u`, the actual product satisfies

```
v^T Ap = ||Jc v-Jp u||^2 + lambda*u^T Dp*u + lambda*||v||^2 + u^T e.
```

The deliberately perturbed point solves produce discrepancies as large as 6.71e−4 between the actual product and the nonnegative terms alone. Adding `u^T e` restores the identity to maximum normalized error 4.72e−18. Therefore replacing only a CG denominator can conceal a mismatched product; it is not a consistent solver fix. The native formulation must also retain its nonnegative intrinsic-regularization term, omitted from this synthetic no-intrinsics system.

Brief 0 already implements the coherent FP64 reference operator and validates camera products, symmetry and reduced residuals. Independent full-normal checks exposed a separate point-completion accuracy issue; the supplementary CPU completion on Venice reaches full scaled residual below 1e−10 while preserving the original nonlinear conclusions. See `../analysis/FINDINGS.md` and `../coarse/refined/`. Accurate linear algebra does not make every unclipped direction useful.

The frozen nine practical target cells encountered no numerical repairs before their targets. This mechanism cannot explain a speed improvement there through avoided floor repairs. A production consistency experiment would have to establish a tail benefit or separately measure a bandwidth improvement. The prior FP32-fragment experiments included endpoint regressions, so the synthetic PSD result does not reverse those empirical results.

Current status: **numerical mechanism reproduced; no new deployed solver or speed win.** This useful completed-square identity is closely related to square-root marginalization. It does not support a first-PSD-BA or backward-stability-by-one-line claim; the prior-art boundary is in `../literature/MATH_AND_PRIOR_ART.md`.
