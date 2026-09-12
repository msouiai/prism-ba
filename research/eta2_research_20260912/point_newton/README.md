# Conditional point-Newton witness test

This module implements the committed [Brief 8 protocol](../PROTOCOL_08.md),
registration `ddf798c`. It keeps each saved camera step fixed and changes only
the conditional Euclidean point block. It is a CPU model-fidelity diagnostic,
not a native solver rollout or a new champion.

**Completed: 54/54 valid rows; killed by the Ladybug proposal failure.**
See [FINDINGS.md](FINDINGS.md) for all results and the two-observation
perspective-horizon mechanism.

For each observation, write `u=-Yxy/Yz` and `pixel=f(1+k1||u||²)u`.
The exact residual-weighted point Hessian follows the chain rule:

```
Hdist = 2 f k1 [r u^T + u r^T + (r^T u) I]
HY = Du^T Hdist Du + (r^T G)_0 Hu + (r^T G)_1 Hv
N_point = sum_observations R^T HY R.
```

Residuals in this contraction are held at the original witness state.
The camera/point cross block remains GN. Thus this tests the requested
points-only Hessian hybrid, not a complete conditional Hessian recomputed
at the nonlinear proposed camera state.

`core.py` assembles the same conditional RHS, GN block, and diagonal/trace
damping as the immutable Euclidean controls. It uses `V+N+lambda Dp` only
when the Dp-whitened block passes the exact registered SPD threshold;
otherwise it uses the unchanged damped GN block. A point rejected by that
test also contributes no N term to hybrid prediction. Raw undamped negative
eigenvalues and actual damped fallback are reported separately.

Prediction and scoring are deliberately distinct:

```
pred_GN = -g^T d - 1/2 ||Jd||²
pred_hybrid = pred_GN - 1/2 sum_points dp^T N_active dp.
```

The existing immutable chart scorer evaluates every original observation,
SIMPLE_RADIAL, unshared intrinsics and k2=0, using the Euclidean point
retraction. No robust loss, dropping, point clipping or damping retuning is
introduced. Its numerical arguments are unchanged except for the supplied
conditional point solver; the temporary Python function substitution is
restored on exit and never modifies the source file or another process.

Reproduce with one CPU/BLAS thread:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python3 research/eta2_research_20260912/point_newton/verify.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python3 research/eta2_research_20260912/point_newton/run_witnesses.py
```

Existing rows require `--resume`; source/protocol/control hashes must match.
The run manifest pins every witness, saved camera direction, original BAL
file, and retained Euclidean comparison. N=3 repetitions per fixed state are
deterministic numerical repeats, not basin/hit-rate samples. CPU timings
include assembly, SPD decisions, point solves and scoring; they are not GPU
overhead estimates or a same-host isolated speed comparison with old rows.

`verification.json` records analytic-Hessian finite differences, zero-residual
GN equivalence, exact fallback recovery, and finite damped treatment of an
undamped indefinite block. `camera_prediction_kill.json` documents the
separate algebraic kill for prediction-only changes to the nine already
recorded raw Final3068 proposals: their true cost rises, so changing rho's
denominator cannot satisfy the mandatory descent condition.

Final results and the registered kill assessment are in `FINDINGS.md`.
No broad novelty claim follows from a partial
Newton model or an analytic Hessian implementation.
