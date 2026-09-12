# First spectral pre-test: Venice52 terminal witness0

Registered by the parent task before computing spectra. One fixed native state:
`evidence/collect/venice-52-capture-0`, K=8 deterministic center clustering
from the completed projection module. No GPU or optimizer rollout.

Reconstruct the original-observation SIMPLE_RADIAL FP64 Jacobians, with native
left-rotation tangent, unshared intrinsics and fixed k2. Use captured E, point
Cdiag and lambda; reconstruct the same intrinsic solve prior. Point factors use
FP64 QR on Jacobian rows plus the native diagonal augmentation. Assemble the
small dense Schur matrix by sparse cross blocks and triangular point factors.
Build the block preconditioner from captured Hcc/E and lambda, including native
diagonal-floor/fallback semantics. Do not replace that M with Schur Jacobi.

Before interpreting spectra, check reconstructed score versus metadata,
camera-Hcc agreement, saved exact-direction camera residual and point equation,
and dense-versus-Jacobian-product agreement on four fixed vectors. The CPU
cross-implementation agreement tolerance is1e-7 relative; this does not relabel
the CPU result as a1e-10 certified native reference. Keep every discrepancy.

Remove all52 fixed k2 slots, leaving416 active coordinates. Whiten symmetrically
using M=LL^T, Atilde=L^-1 A L^-T. Transform the camera coarse basis by L^T.
Form the symmetric deflated matrix and its explicit complement to the coarse
space. Its54 expected zero directions must not enter the non-null condition
number. Record full dense eigenvalues as an independent reference.

Run50-step symmetric Lanczos with full reorthogonalization, starting from the
whitened native reduced RHS for the baseline and its properly deflated residual
for the deflated system. Report all Ritz values and residuals, projected-matrix
versus-tridiagonal discrepancy, and exact spectra. If a starting residual is
zero, report coarse exactness rather than substitute an advantageous seed.

No parameter sweep, solver implementation, timing win or endpoint claim. A
lifted non-null minimum is mechanistic evidence for this state, not proof that
an additive two-level preconditioner will improve Eta2's nonlinear trajectory.
