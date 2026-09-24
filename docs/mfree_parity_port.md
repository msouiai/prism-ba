# MFREE rig-path parity port (branch `mfree-parity`, 2026-09-21)

Prism's rig / fisheye path (`gpu/oca_rigfisheye.cuh`, `gpu/oca_core.h`, the
`oca::SolveRigFisheye` adapter at the tail of `gpu/oca_cuda.cu`) had forked from
MFREE before the 2026-09-18 local-BA parity work. The fork lacked constant
parameter blocks (frame / sensor / calibration / point), the soft-L1 loss the
COLMAP mapper uses for local BA, the Ceres gauge rules (gauge_scale_frame), the
pinhole-family model masks, and the shared-helper optimisations. On Fuchsberg
that fork produced a 1.83 % extent error map versus 0.7 % for MFREE.

This branch replaces those three pieces with `mfree_release/solver` @ 0a6cb5a,
verbatim, plus `gpu/oca_rig_support.cuh` (helpers that MFREE keeps in its
shared section, copied so that prism's BAL/dof9 kernels stay untouched), the
generated atan2 / pinhole Jacobian headers and their generators, and
`test_rigfisheye.cc`. Codex's uncommitted theta-cap-in-constant-memory work is
preserved as commit 9df47234 (superseded: MFREE's atan2 residual is the default
and `OCA_RF_THETA_MAX_DEG` is honoured through `SolveRigFisheye`).

## BAL regression gate

`cuobjdump -sass` of the CLI before and after: 179 kernels present in both
binaries, 179 byte-identical (offsets stripped); 7 old rig kernels removed, 16
new rig kernels added. The BAL/dof9 machine code is unchanged.

Endpoints (`bal_gate.sh`, README champion flags, 3 repeats):
`parity_bal_gate_base.txt` vs `parity_bal_gate_port.txt`. ladybug-49 and
final-1936 identical to the printed digits; trafalgar-126 / dubrovnik-88 within
the baseline's own repeat scatter (atomic reductions); ladybug-1197 is
non-deterministic in the baseline itself (105-137 iterations, 5.2e5-5.5e5).

## Rig gate

`test_rigfisheye`: synthetic rig PASS, constant blocks A/B/C PASS, pinhole
SIMPLE_RADIAL PASS (RTX 2000 Ada).
