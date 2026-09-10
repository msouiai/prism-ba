# Schur preconditioner results — 2026-09-10

The frozen eta2 Hcc-PCG champion remains the winner of this bounded gate.
A cheaper Schur-block construction is validated, but neither always-on use nor
an eight-iteration conditional upgrade improves full time to fixed targets.
This does not refute all Schur/visibility preconditioners, nor measure Config S.

Host: Codex 2237c6528e79, RTX 2000 Ada. No cross-host timing ratios.
The protocol was registered before capture; the conditional upgrade is explicitly
an exploratory follow-up after the always-on failure. Claude's suite, baseline
gap investigation, and independent eta2 validation were not duplicated.

## Fixed linear systems, N=3

Three exact captures from the unchanged eta2 trajectory: Muell outer12,
Ladybug598 outer8, Final1936 outer0. The Ladybug state turned out to be a cheap
native-eta solve; we did not substitute a more favorable/deeper state.
Every selected native forcing tolerance was0.5. Total times below include build,
PCG and true-residual verification, using CUDA-event intervals including host
submission gaps. One warm-up precedes three repeats with rotated arm order.

| Scene / outer | Preconditioner | Iterations | Total ms median [min,max] | Build ms median |
|---|---|---:|---:|---:|
| final-1936 | Hcc | 1 | 16.347 [16.274, 16.382] | 0.117 |
| final-1936 | Schur legacy | 1 | 61.534 [61.004, 61.772] | 45.420 |
| final-1936 | Schur Gram | 1 | 46.994 [46.959, 47.122] | 30.888 |
| ladybug-598 | Hcc | 2 | 1.854 [1.836, 1.857] | 0.104 |
| ladybug-598 | Schur legacy | 3 | 5.431 [5.283, 5.469] | 3.093 |
| ladybug-598 | Schur Gram | 3 | 4.312 [4.299, 4.327] | 1.984 |
| muell-gba146 | Hcc | 41 | 131.195 [130.967, 131.498] | 0.111 |
| muell-gba146 | Schur legacy | 3 | 30.803 [30.760, 30.811] | 18.376 |
| muell-gba146 | Schur Gram | 3 | 24.350 [24.326, 24.372] | 11.929 |

Gram construction cuts the legacy Schur setup by32.0–35.9%. On Muell it cuts
the full captured native-eta solve from131.195 to24.350ms (5.388x). But the
cheap controls lose: Hcc needs only one/two CG iterations and construction has
no opportunity to repay itself. Native-eta block fallback count is zero for
all arms. Normalized unfactored-block relative Frobenius differences are
3.09e-17 (Final), 2.03e-16 (Ladybug), and6.18e-17 (Muell).

At the stricter0.01 tolerance, all arms miss within128 iterations on Muell and
Ladybug; these are failures, not equal-quality speedups. Final hits in six
iterations with every preconditioner; Hcc remains fastest. All54 measured
fixed-system rows and their actual residuals are retained in evidence.

The kernel uses C_tau=R^T R and W C_tau^-1 W^T=Y^T Y, Y=R^-T W^T.
It removes the backward point solve and one row array while preserving the
camera-major layout and fixed warp reduction. Roundoff changes are measured;
bitwise identity is not claimed.

## Full fixed-target gates, N=3 per arm

Targets copied unchanged from the sustained eta2 study: Muell1,946,488.746262194;
Final1936 5,125,687.352261469. All runs share lambda0=.1, eta2,600 outer cap and
12 native seconds. Both arms use the same binary within each gate. Target
seconds include solver setup and iteration work; RESULT solve_seconds additionally
includes final solver bookkeeping. Input loading is outside this native clock.
All24 target runs hit; no cap censoring. Endpoints are at first target crossing,
not fully converged minima. Each cell below shows median [min,max].

| Gate | Scene | Arm | Target seconds | Final cost | Outers | Rejects | Products |
|---|---|---|---:|---:|---:|---:|---:|
| targets | muell-gba146 | hcc | 4.228473 [4.225464,4.235115] | 1946467.186 [1946467.153,1946467.209] | 16 | 0 | 980 [980,980] |
| targets | muell-gba146 | gram | 5.076967 [5.062383,5.097330] | 1944598.471 [1944570.729,1944604.206] | 17 | 1 | 1149 [1148,1157] |
| targets | final-1936 | hcc | 0.508047 [0.502255,0.509198] | 5098339.730 [5098339.730,5098339.730] | 4 | 0 | 16 [16,16] |
| targets | final-1936 | gram | 0.669763 [0.663133,0.680178] | 5098232.064 [5098232.064,5098232.064] | 4 | 0 | 21 [21,21] |
| targets-upgrade | muell-gba146 | hcc | 4.231964 [4.229803,4.237080] | 1946467.157 [1946467.131,1946467.168] | 16 | 0 | 980 [980,980] |
| targets-upgrade | muell-gba146 | upgrade | 4.384501 [4.351819,4.405148] | 1945886.952 [1945877.168,1945910.268] | 18 | 0 | 961 [955,962] |
| targets-upgrade | final-1936 | hcc | 0.502661 [0.501333,0.508152] | 5098339.730 [5098339.730,5098339.730] | 4 | 0 | 16 [16,16] |
| targets-upgrade | final-1936 | upgrade | 0.505008 [0.504192,0.522443] | 5098339.730 [5098339.730,5098339.730] | 4 | 0 | 16 [16,16] |

Always-on Gram is20.1% slower on Muell and31.8% slower on Final1936. Muell
requires17 accepted outers and one rejection instead of16/zero, and more Schur
products overall despite the isolated favorable system. The changed inexact
steps lead to a different nonlinear trajectory; setup savings alone do not
control that trajectory.

The conditional upgrade preserves Hcc for solves completed within eight steps.
For unfinished solves it retains x, explicitly recomputes b-Ax, builds Schur
blocks, and restarts p=M^-1 r with the same operator and remaining iteration
budget. It is mathematically a restarted PCG solve, not an uncorrected change
of M inside the old conjugacy recurrence. The extra residual product is charged.

This reduces Muell's product count980->961 but needs18 rather than16 accepted
outers. Target time is3.60% slower; Final is0.47% slower with overlapping ranges
and identical iteration/product counts. This is not a major practical regression,
but it misses the registered1.10x improvement criterion. No replacement champion.

Both integrated versions pass zero-error CUDA memcheck; the conditional check
uses Ladybug598 and actually exercises upgrades. Off-mode objective parity
against the original measured frozen binary passes within1e-8 relative (raw
costs in summaries). Capture and experiment manifests hash inputs and matrices.
No default or original implementation file was modified.

## Interpretation and next decision

The shared architectural question has an executable negative compatibility
answer, not a five-shift timing result; see ARCHITECTURE.md. Coupled point damping
changes the reduced matrix and RHS, and the existing PCG does not support the
ordinary shared shifted recurrence. Do not claim eta2's Caspar wins demonstrate
multi-shift economy, or that this absent comparison proves the menu is expensive.

The useful deliverable is the cheaper Schur build plus a reproducible fixed-state
benchmark. It can be reviewed independently of whether Schur is selected. A
future preconditioner experiment should estimate saved operator work versus
construction AND preserve nonlinear progress. This gate does not justify more
parameter sweeps or use of Claude's GPU; his same-host R/S/eta2 target comparison
has higher priority. Schur Jacobi, the Gram identity, and PCG restarting are not
claimed as new mathematics.

Raw fixed matrices remain in /workspace/prism-schur-eta2 (about904MiB), with
per-file SHA256 manifests and regenerating capture code. Git includes compact
logs, manifests and exact first-version patches, not large matrices or binaries.
The measured v1 solver source and executable also remain in the targets folder.
Current build_solver.py reproduces both modes; solver-v1.patch preserves the
exact source/header delta for the first measurement (copy gram.cuh to headers).
The fixed benchmark later gained a dimensions check only; evidence includes
the exact translation unit used for the measurements.
