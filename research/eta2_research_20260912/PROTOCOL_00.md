# Brief 0 registration: witness-state solve/model decomposition

Registered before building or running the diagnostic. This is a fixed-state mechanism experiment, not a time-to-target or hit-rate claim. The frozen champion has source SHA256 `22c18359a526526ae0a5b5109187878ab1cef33b453f6bbddc2aa92597a607d8` and binary SHA256 `1e3d2cf22a8a43075114e0ca2024923dad330461e35d0074938d0412cd77ecc0`.

## Witness selection and baseline control

- Capture the first three fresh above-target terminal-FTOL states on Venice52 and the first three on Final3068, at their fixed targets 243740.27 and 1744796.9841897595. Cap collection at 20 consecutive runs per scene. Retain selection outcomes for every run, including target hits, and do not call the witness-selection fraction a reliability estimate. Frozen flags, lambda0=0.1, 600 outers, 60 native seconds. Do not disable backtracking, alter the stopping rule, restore controller state, or change the trajectory before capture.
- Save the exact state and outgoing lambda, radius, numerical floor, previous reduced-RHS norm, and counters at the terminal decision. The diagnostic computes one hypothetical next attempt without committing it. This preserves the actual forcing history; old endpoint-only dumps do not contain that history.
- Also capture the first proposal at zero-based outer 1 on Ladybug1197 in three fresh runs. Report whether the historical fling exists under the current champion rather than assuming it. Use the first capture for the requested seventh-state comparison; retain the other two as repeat controls. The older MFREE fling is contextual evidence, not a matched Eta2 baseline.
- Verify source/headers and flags, validate the existing original binary hash, and run N=3 original versus diagnostic-disabled compatibility on Dubrovnik88 before using new instrumentation. Exact trajectory matching is not assumed under recompilation; report observed endpoint/work differences. No timing claim from instrumented runs.

## Directions and validity

At each captured state, with the same lambda, point damping, camera scaling and radius, compute:

1. Eta2's inexact mixed-storage direction, clipped in scaled camera coordinates and followed by native point back-substitution. Preserve its raw camera direction separately.
2. A consistent FP64 Jacobian-based reference: all products/RHS from the same FP64 camera and point Jacobian rows, point QR with the same diagonal damping, camera intrinsic regularizer, and fresh camera-block preconditioner. PCG true relative residual <=1e-10, no camera clipping.
3. The same reference camera direction clipped to the saved radius, then FP64 point back-substitution for those clipped cameras.

Use a 20,000-PCG-iteration / 180-second reference cap per witness. Recompute true residual, retain recursive/true discrepancies, and restart only within this same fixed solve if residual drift requires it; there is no cross-attempt or cross-iteration Krylov reuse. A capped solve failing the true residual threshold is labelled approximate, never exact. Also retain point-equation residuals and finite arithmetic checks. The product is Jc^T(Jc E v - Jp u) plus intrinsic/camera regularization; no inconsistent U/W subtraction is used as the reference.

Run three reference repetitions per retained primary witness; report all numerical variation. Performance of this deliberately expensive diagnostic is not solver performance.

## Decomposition

Score full original-observation FP64 cost, GN prediction, true decrease and rho for every direction. Define D(d)=F(Retract(x,d))-F(x)+pred(d). Compute Dcamera with only cameras moved, Dpoint with only points moved, and Dcross=Dfull-Dcamera-Dpoint; this is an additive decomposition of model error, not three raw costs. Bin the signed and absolute point error by track length 2 / 3–5 / >5 (retain 0–1 separately), and by initial maximum viewing-ray parallax <1deg / 1–5deg / >5deg. Report positive/negative error, top-200 absolute-error concentration and signed contribution, flings relative to the camera-center scene radius, and cheirality flips. Verify CPU and native cost/prediction agreement.

For the coarse pre-test, form deterministic geometric camera clusters K=8,32,128 (K capped at ncam). Build rigid translation/rotation/scale modes by finite differences of the actual world-to-camera retraction; intrinsics remain zero. Report rank after removal of dependent modes. Project the CAMERA difference exact-minus-Eta2 into the scaled CG metric ||dc||_E=||E^-1 dc||2, with an explicit orthogonal projection; also report exact-clipped-minus-Eta2 to avoid attributing clipping to unresolved linear modes. Gauge modes are retained in the diagnostic but labelled, not counted as guaranteed useful decrease. Lanczos uses 50 steps on a symmetric block-preconditioned reference, with true product checks, only for coarse fractions passing the gate.

## Decision rules and scope

- Reference rho>0.5 and Eta2 rho<0.1 motivates solve-side work, but inspect the equally clipped reference to distinguish solve error from the radius restriction.
- Both rho<0.1 and dominant thin-track point model error motivates charts, then point residual-Hessian correction. Dominant camera error motivates the camera model/controller branch.
- If both directions have adequate rho but tiny useful progress, or the exact/clipped comparison exposes a radius bind, classify separately rather than force the proposed binary decision. High accuracy at high damping can coexist with stagnation.
- Stop Brief 1's rigid-cluster solver route if every K at every valid witness captures <25% of the missing camera direction. A large fraction is necessary screening evidence, not proof of a speed win. Full-grid configurations must be separately registered before running.
- Failed linear certification, nonfinite retractions, and mixed/error-dominated cases remain visible. No negative-curvature event alone is called a nonlinear saddle. No practical-target improvement is inferred from this diagnostic.
