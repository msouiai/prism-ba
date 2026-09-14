# Point-owned fused Pass1 protocol

Registered 2026-09-14 before implementation or timing.

Behind `OCA_AUDIT_FUSED_PASS1=1`, one point-owned block traverses the existing
point CSR in stable order, accumulates `W^T v` in FP64, applies the existing 3x3
factor immediately, and writes `u`. It replaces memset + observation-owned
atomic Pass1 + `MFVinvApply` only for compact CD9 unshared single-RHS products.
All other modes retain the original path.

The fixed-system gate compares operator output with the complete deterministic
Pass1 path on an archived Final1936 capture and a synthetic invalid-factor /
long-track fixture. Report point-output error and full Schur-action error
separately. Require `||delta u|| <= 1e-12*(||u_ref||+1)` and
`||delta Av|| <= 1e-12*(||Av_ref||+||Hcc v||+||W u_ref||+1)`, an adjoint
symmetry defect below `1e-12` after the same term normalization, and exact
agreement on invalid-factor zeroing. Product time must improve at least 5% on
the captured system.
Only after passing may Ladybug49 and Final1936 native N=3 cells run. Any native
wall regression above 2% kills promotion; controller tuning is forbidden.
