# Venice witness: coarse spectral pre-test

**K=8 removes low eigenvalues from the symmetrically preconditioned camera
operator at Venice capture 0. This supports testing a coarse preconditioner;
it establishes no solver speed improvement.**

The first-state selection, basis and 50-step procedure are in
[SPECTRAL_PROTOCOL.md](SPECTRAL_PROTOCOL.md). The original result is retained at
[spectra/venice-52-capture-0.json](spectra/venice-52-capture-0.json), including its
failed combined agreement check. Follow-up numerical diagnostics are separate:
[spectra/venice-52-capture-0-point-diagnosis.json](spectra/venice-52-capture-0-point-diagnosis.json).

## Camera spectrum

All 52 fixed k2 slots are removed: 416 active coordinates. The coarse space has
rank 54. We use the actual captured camera-block preconditioner M=LL^T and
diagonal equilibration E, with the coherent FP64 Jacobian reduced operator.
Whitening is L^-1 A L^-T, not a nonsymmetric M^-1 A eigenproblem. The deflated
matrix is restricted to the explicit complement of its 54 coarse zero modes.

| Quantity | Camera-block baseline | Deflated non-null operator |
|---|---:|---:|
| Dense minimum eigenvalue | 8.0341184e-7 | 2.3800014e-4 |
| Dense maximum eigenvalue | 0.99999882 | 0.99918974 |
| Dense condition number | 1,244,690 | 4,198 |
| Eigenvalues below 1e-4 | 4 | 0 |
| Eigenvalues below 0.01 | 7 | 2 |
| Minimum 50-step RHS-started Ritz value | 1.1180463e-4 | 2.3800014e-4 |
| Residual norm of that Ritz pair | 1.3669e-3 | 3.3240e-7 |

The condition number improves about 296-fold, but this is **not** a prediction
of a 296-fold iteration or runtime improvement. Damped global similarity modes
are retained in the baseline spectrum, and some tiny eigenvectors may have
little component in the actual RHS. The baseline 50-step Ritz minimum has not
resolved the true minimum; substituting it for the dense eigenvalue would be
incorrect. Full spectra and Ritz residuals are recorded, with Lanczos
orthogonality errors below 1.4e-15. Explicit deflated zeros are at roundoff and
are excluded by construction, rather than an advantageous numerical cutoff.
The previous missing-direction projection remains 85.62% after removal of the
global similarity component, so the geometric coverage is not only a gauge
observation.

## Operator agreement and retained failure

The score agrees with native metadata to 1.2e-16 relative. Reconstructed Hcc
differs from captured Hcc by 2.01e-9 relative; the latter is used for the block
preconditioner. The saved source camera direction has a reduced residual of
9.05e-11 under the independent Jacobian product. Four dense-versus-Jacobian
product discrepancies are at most 4.03e-12 relative. These directly support
the camera-operator spectral comparison.

The original combined gate nevertheless **failed**. Its point residual was
normalized by max(||gp||, ||Jp^T(Jc dc+Jp dp)||), which contains cancellation
between the camera-induced and point-induced terms. That normalization gave
1.59. We retain that outcome; it does not become a passed preregistered gate.
The follow-up stable conditional equation instead gives:

| Saved source full step, Venice 0 | Value |
|---|---:|
| Stable point residual norm | 4,406.59196 |
| Conditional point RHS norm | 1.46559214e9 |
| Relative to conditional RHS | 3.00670e-6 |
| Global normwise backward error | 4.55086e-7 |
| Dp-whitened point residual / full scaled gradient | 1.61595e-6 |
| Full scaled normal residual / full scaled gradient | 3.28081e-6 |

These independently reproduce the main point audit. They qualify the saved
**full step**, while the reduced camera operator still agrees. The source's
reduced-PCG certificate must not be called a full GN certificate. The coherent
CPU operator also must not silently replace the champion's mixed-storage
production operator in any ensuing A/B.

## Supplementary full-normal completion

At the parent's request, recompute only the points by CPU FP64 QR and triangular
solves, holding each saved source camera direction bit-for-bit unchanged. The
new files are separate [refined/](refined/) artifacts, each with metadata and
input/output hashes. The unmodified shared `analysis/audit_capture.py` scores
the original full objective; it does not choose a candidate or run an outer.

| Venice capture | Full scaled normal residual | True decrease | Prediction | rho |
|---|---:|---:|---:|---:|
| 0 | 7.16461e-11 | 35.509976864 | 36.632767531 | 0.969350 |
| 1 | 8.24660e-11 | -20.045782219 | 0.444422827 | -45.1052 |
| 2 | 6.00008e-11 | 1.299238047 | 1.640707284 | 0.791877 |

All three now meet the requested 1e-10 full scaled residual in this independent
FP64 evaluation. This is a measured arithmetic certificate, not an interval
bound. The nonlinear verdict survives: capture 0 has a useful missing solve;
capture 1 still overshoots despite linear accuracy; capture 2 improves less.
No registered source direction or result was replaced. These are fixed-state
supplements, not three independent optimizer repetitions or target hits.

For capture 0, the new points differ from the saved ones by only 4.80e-6 in
Euclidean vector norm. The resulting point residual relative to its conditional
RHS is 1.98e-16. This does not identify a defective native triangular solver:
the CPU/native Jacobian evaluation itself is sensitive on point 60378 (as the
main extended-precision audit records). Separating native RHS accumulation,
factorization, geometry and back-substitution would require exporting the
actual native intermediate arrays.

## Verification and next boundary

[test_spectrum.py](test_spectrum.py) compares QR point inversion with an
independent full normal system, Schur with full-system solutions, symmetric
whitening with generalized eigenvalues, explicit deflation with its non-null
spectrum, and full-dimensional Lanczos with exact eigenvalues. Errors are
below 7.2e-15. No GPU was used, no production source changed, and no coarse
solver was timed. The practical next implementation proposal is in
[NATIVE_ADDITIVE_DESIGN.md](NATIVE_ADDITIVE_DESIGN.md).
