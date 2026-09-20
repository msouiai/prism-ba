# Ten steps: identical-geometry damping comparisons

2026-09-08. **No new end-to-end winner. Single shift + point repair remains the incumbent on Dubrovnik173** (2.36 seconds in the preceding matched-binary target test). This round isolates local choices rather than timing complete solves. Paired multishift produces the greatest next-outer objective decrease on all four shared starting states, at higher computational cost. Three of four locally best single-shift damping choices lose their gain advantage by three outer iterations.

## Ten completed steps

1. Froze protocol and retained the existing winner ledger.
2. Captured actual accepted repaired directions from frozen paired + point repair on Dubrovnik173 and Venice52, using the unchanged v4 binary.
3. Constructed post-repair states for capture calls 1 and 4 in each scene, using CPU retraction.
4. Audited the retraction cost and rotation-to-BAL roundtrip; all arms share the exact same generated BAL file per state.
5. Screened six initial damping choices: hold, camera half, point half, both half, camera double, and point double, fixed single shift + point repair, one outer iteration each.
6. Repeated all 24 cases in reverse order.
7. Checked all initial objectives and actual first-attempt camera/point damping against the protocol.
8. Compared fixed five-shift and paired modes from the same starting states, one outer iteration each.
9. Compared hold versus each state's best median one-outer single-shift choice for three outer iterations, once each.
10. Saved provenance and published the local and end-to-end winner distinctions.

## Controlled scope

These are fresh solver restarts from shared post-repair geometry, **not full checkpoint continuations**. Krylov, convergence, and controller history are reset. Initial lambda and tau come from the captured repaired attempt; camera/point multipliers are applied before the first attempt. Tau/lambda floor coupling is disabled in these restart probes so that independent initial pairs can actually be tested. Existing retry and subsequent damping-update rules remain active: one outer iteration can include rejected attempts, and the starting pair is not held constant over all retries or later iterations.

The paired and five-shift checks use the same hold starting pair and the same point repair. Only the restart harness gained a custom input-data path and a CPU conversion helper. No solver algorithm, default, or live damping policy changed. Results are diagnostic and conditioned on four selected repair states; they are not a new representative benchmark or speedup claim.

## Single-shift choices: immediate and later quality

The values below are absolute objective decreases, so larger is better. First-outer values are two-repeat medians. Three-outer values are one diagnostic run per arm, after selection using the earlier data. The two columns are not matched-time comparisons.

| State | Best initial pair among six | One-outer gain: hold → selected | Three-outer gain: hold → selected | Three-outer quality winner |
|---|---|---:|---:|---|
| Dubrovnik173, repair 1 | Camera half | 2928.9 → 4755.2 | 9332.9 → 7930.3 | Hold |
| Dubrovnik173, repair 4 | Both half | 410.8 → 551.6 | 736.1 → 1595.0 | Both half |
| Venice52, repair 1 | Point double | 3003.7 → 3007.2 | 12442.7 → 9136.4 | Hold |
| Venice52, repair 4 | Point double | 1580.1 → 3562.7 | 10581.6 → 9163.8 | Hold |

Venice repair 1's initial advantage is just 0.12% in objective decrease; treat that as practically tied. There is no consensus direction: even within Dubrovnik, point-half is worse than hold at repair 1 but improves immediate gain at repair 4. Selecting a damping policy by the largest immediate decrease is not validated by these outcomes. The selected three-outer runs also consume different time and work; lower gain is not by itself proof of worse time-to-quality.

## Does multishift improve the local step?

Yes, in this screen. Paired has the largest one-outer objective decrease at every shared state. Menu checks have one repeat; single hold has two. Matrix-vector counts include the work of any retries within the outer iteration.

| State | Single hold gain / matvecs | Fixed five gain / matvecs | Paired gain / matvecs | Local quality winner |
|---|---:|---:|---:|---|
| Dubrovnik173, repair 1 | 2929 / 31 | 4894 / 36 | 5215 / 67 | Paired |
| Dubrovnik173, repair 4 | 411 / 41 | 770 / 76 | 858 / 117 | Paired |
| Venice52, repair 1 | 3004 / 20 | 3074 / 80 | 3324 / 91 | Paired |
| Venice52, repair 4 | 1580 / 60 | 9426 / 142 | 9925 / 193 | Paired |

Paired also scored 40, 46, 47, and 64 candidates respectively, versus single hold's 10, 11, 10, and 12. More options do find better immediate steps here, but the extra gain is purchased with more computation. Fixed five offers an interesting intermediate tradeoff in these four cases. None of these local gain ratios is a measured complete-BA speedup.

## Mathematical interpretation

At a fixed linearization and fixed damping scales, let A(tau)=V+tau Dp. Then

S(tau)=Hcc-W A(tau)^(-1) W^T,

and dS/dtau=W A^(-1) Dp A^(-1) W^T is positive semidefinite when Dp is positive semidefinite and A is invertible. However the reduced right-hand side also changes:

b'(tau)=bc-W A(tau)^(-1) bp,

db'/dtau=W A^(-1) Dp A^(-1) bp.

Thus increased point damping changes both the reduced operator and its right-hand side. Positive-semidefinite ordering of the operator alone does not order nonlinear objective gains. Changing tau generally does not add a scalar identity shift: ordinary multishift reuse for camera lambda cannot automatically share the entire sweep across arbitrary point-damping choices. This explains a structural source of the paired controller's extra work, without proving which choice will win in a given scene.

The existing split rule evaluates isolated components of the already accepted repaired direction at the previous state. Those ratios are not direct estimates of the next state's best damping pair, especially after retried or shortened steps. The current experiments show that even explicitly selecting the best next-outer gain does not reliably maximize gain over the following three outer iterations. This argues for evaluating a prospective controller over a short trajectory and accounting for work, rather than promoting a one-step winner directly.

## Validation, cost, and artifacts

Two capture solves plus 64 one-/three-outer restart solves consumed **14.403 native solver seconds**; process startup, file conversion, and CPU auditing are additional. All 66 endpoint audits and monotonicity checks passed, maximum relative endpoint discrepancy 9.70e-15. All 64 restart initial objectives agreed with their CPU reference within 2.00e-15 relative, and all 64 initial lambda/tau pairs matched the prescribed values. BAL rotation and retraction roundtrip errors are saved in `restarts.json` and passed the predeclared tolerances. Restart history is intentionally reset despite the shared geometry.

Artifacts: `/workspace/prism-state-damping/` contains protocol, ten-step plan, captures, generated data, frozen run plans, per-run manifests/logs/CSV/JSONL/states/results, selection, summaries, provenance, and completion. Helpers are `bench/prepare_damping_restarts.py` and the extended `bench/backtrack_investigation.py`. The eleven older jobs remain paused. Nothing was pushed, and no Caspar or large-scene test was run.

## Current winners and next step

End-to-end incumbent on Dubrovnik173: **single + point repair**. Earlier Ladybug1197/Trafalgar126 winner: **frozen paired**. Local one-outer quality winner in this round: **paired on all four states**, with greater work. No universal winner or online selection rule has been established.

The next useful experiment is a small equal-work comparison of single, fixed-five, and paired over several outer iterations from these shared states. Fixed-five deserves attention because it often gets much of paired's immediate gain at lower work, but it must earn a time-to-quality win before promotion. Avoid another blanket damping-relaxation rule based solely on immediate cost decrease.
