# B4 direct reduced solve results

## Verdict

Reject FP64 dense Schur formation plus Cholesky as an Eta2 production dispatch
on this GPU.  The final implementation applies the same numerical operator as
the matrix-free path, but explicit formation dominates wall time and the exact
direction interacts poorly with the existing radius clipping on Venice.  The
frozen Eta2 champion remains the winner.

## Correctness trail

The first optimized prototype failed its audit because the MFREE CLI did not
construct the persistent edge CSR; consequently its dense matrix contained
only camera-diagonal Schur blocks.  A second audit also initially compared the
damped dense product against the undamped matrix-free product.  Both failures
are retained in the versioned evidence and excluded from solver conclusions.

A literal point-major reference formation then matched
`(E S E + lambda I)b` from the matrix-free operator to `1.10e-15` relative L2.
That isolated the topology fault.  After enabling the existing edge-CSR build
for selected MFREE problems, the optimized atomics-free formation matched to
`3.53e-16`.  Disabled-mode N=3 median endpoint cost matches the frozen binary
to the printed digit.  The final registered binary is the v5 registration;
earlier registrations document the correction trail.

## Practical panel

All 54 paired runs reached their identical targets.  Cells above the fixed
`n_c <= 1536` threshold are controls and remain numerically unchanged.  The
three selected Trafalgar138 cells are slower with disjoint ranges:

| Target | PCG median (s) | Direct median (s) | Ratio | PCG/direct outers |
|---|---:|---:|---:|---:|
| 1.005x | 0.3016 | 0.4504 | 1.49x | 13 / 9 |
| 1.01x  | 0.2302 | 0.4006 | 1.74x | 10 / 8 |
| 1.02x  | 0.1266 | 0.3503 | 2.77x | 8 / 7 |

The exact solve saves outers but not wall.  Across all nine cells, including
the six intentionally untouched controls, the geometric-mean target-time
ratio is `1.2656` (+26.6%).  Endpoint changes on selected cells range from
`-0.45%` to `+0.07%`; this does not compensate for the speed loss.

## Phase attribution

The preregistered profile was terminated after one complete paired row per
scene because the kill criterion was already exceeded.

On Trafalgar138 1.005, the direct run reaches the target in 0.4526 s versus
0.3202 s.  Across nine direct solves, explicit formation costs 0.3559 s and
FP64 factorisation plus triangular solves costs 0.0635 s.  Formation, rather
than cuSOLVER, is the bottleneck.

Venice52 makes the failure unambiguous.  The control stops after 126 outers in
1.299 s at 247,590.  The direct arm hits its 60-second cap after 345 accepted
outers at a worse 255,080.  Its 342 successful direct solves spend 56.715 s in
formation and only 0.843 s in Cholesky plus solves.  The raw exact direction
remains much larger than the radius in the tail, so radial clipping repeatedly
throws away its useful stiff components; exact linear algebra does not fix the
nonlinear policy.

This also bounds two possible follow-ups.  Faster FP32 Cholesky cannot rescue
the current design because factorisation is only 1.4% of the Venice wall.
Changing the camera-count threshold cannot repair a formation kernel that is
already slower at 468 variables and changes the selected trajectory.  B4 is
closed without N=5 tails.

Compact evidence: `b4-panel-results.json`, `b4-panel-summary.json`,
`b4-profile-results.json`, `b4-profile-partial-summary.json`, and
`b4v5-registration.json`.
