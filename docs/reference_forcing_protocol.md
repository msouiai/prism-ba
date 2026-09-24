# Fixed-reference reduced-gradient forcing

Registered before new performance measurements, 2026-09-10. The incumbent is
the global lambda0.1 / sustained eta2 configuration. No production defaults change.

## Measurement

For geometry x, write b(x,lambda)=bc-W(V+lambda Dp)^-1bp. If the last accepted
step was computed at x_old with damping lambda_old and diagonal camera scaling
E_old, compare

```
q = ||E_old b(x_new,lambda_old)|| / ||E_old b(x_old,lambda_old)||.
eta = clip(1.8*q*q,1e-12,0.5).
```

Both sides use the same damping and camera metric. V,Dp,W and the gradients
are evaluated at their respective geometries. E_old and the denominator are
saved from the accepted attempt's pre-update linearization. Only accepted
attempts advance the anchor. Hold eta through retries; use eta0.5 without an
anchor. Permanently fall back to the champion after numeric repair. A second
candidate adds the EW-style floor0.9*eta_old^2 when that exceeds0.1.

Recompute the point factor and camera RHS at reference damping once per new
outer, then restore the actual point factor before CG. Reuse Rf,uu,corr,w and
cached R0f. One extra GPU vector stores E_old (8*9*ncam bytes). Explicitly
synchronize restoration for charged, reproducible probe timing. Full native
target time includes probes, restoration, control and anchor copies.
No change to lambda updates, nonlinear acceptance, radius or residual checks.
This tests a forcing signal, not a convergence theorem or a novelty claim.

## Verification and controls

Modes:0 disabled;1 passive probe with champion decisions;2 reference forcing;
3 reference forcing with safeguard. Baselines include sustained eta2 and the
previous pilot's safeguarded reduced-RHS EW2 (`OCA_BAC=3`).

N3 smoke: parent/new champion, passive probe, and passive verification that
recomputing the current RHS at current lambda/E matches its native norm to1e-7.
Costs must agree within1e-7 and work counts match. CPU tests cover fixed-state
lambda cancellation, consistent metric use, accepted-only anchors, retry
idempotence, and repair fallback. Verification/logging are off in performance
runs. Unsupported split damping, non-diagonal metric, replay and selected point
floors are rejected rather than silently approximated.

## Bounded experiment

Development: Ladybug598, Dubrovnik356, Venice89, lambda0.1, unchanged primary
targets and4s caps, five arms xN3=45 runs. Choose between modes2/3 solely by
mean log median target time versus champion on these three tasks. A failed
run receives4*cap in selection. Lambda10 Dubrovnik356 is a separate N3 stress
test of champion/passive/selected rule, excluded from selection (9 runs).

Freeze selected rule before transfer. N3 champion/passive/selected/reduced-EW2
on Trafalgar126 and Final1936 at the same primary AND tighter(target/1.01)
targets as the preceding pilot; Muell146 at its unchanged primary target.
Do not repeat the tighter Muell target: all three preceding arms missed it
in all repeats at12s, so it offers no time-to-target comparison under that cap.
This exclusion is declared before measuring this controller, not after a miss.
Transfer=60 runs. Initial lambda0.1 throughout. Targets are recorded in JSON.
These scenes are excluded from controller selection but familiar research data.

If every selected/champion transfer run hits, geometric median speedup>=1.05,
and no setting slows>10%, run Final13682 at primary27591576.557625167 and
tighter27318392.631312046, four arms xN3 at each target, cap20s (24 runs).
Otherwise skip the largest extension and retain the champion. Report passive
probe overhead independently from active trajectory changes and count the
extra point/RHS evaluations; CG matvec counts alone omit this probe work.

600 total native-second ceiling,600 outers, serialized GPU via flock. CPU FP64
original-observation endpoint audit <1e-7; hit requires an actual native target
event within the cap and audited cost <=target. No target interpolation.
Raw build/logs/outputs: /tmp/prism-reference-forcing. Freeze protocol, code,
binary and input hashes before execution. No new Caspar claim without fresh runs.
