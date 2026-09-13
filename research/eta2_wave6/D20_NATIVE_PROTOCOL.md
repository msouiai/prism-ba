# D20 native protocol: sloppy-mode quotient projection

Registered 2026-09-13 after the fixed-state gate passed and before building or
scoring a feature-enabled native trajectory.  It refines, without changing,
the native gate in `D20_SLOPPY_QUOTIENT_PROTOCOL.md`.

## Frozen implementation

Derive from the checksum-pinned deterministic B6v7 source.  On every attempt:

1. compute the ordinary raw scaled camera direction;
2. if `||z_raw||/R > 100` and one camera carries more than 99% of the active
   eight-coordinate squared norm, form all local scaled 8x8 Schur blocks;
3. activate only if that same camera has the smallest local minimum eigenvalue
   (ties go to the lowest camera index);
4. remove its component along that block's weakest unit eigenvector once;
5. recompute the norm, then run the existing global clip, point
   back-substitution, full-model prediction and full plain-L2 scoring.

Coordinate 8 (`k2`) is untouched.  There is no dose, threshold, rank, dwell or
scene-specific parameter.  The diagnostic prototype may copy the direction and
local blocks to the host and eigensolve there; all of that wall time counts.

Feature-disabled compatibility must match the deterministic parent on the
registered Ladybug539 1.01 cell in endpoint SHA256, accepted-cost hash,
normalised controller-decision hash, hit, outers, rejects, products and cost.

## Fresh paired Venice gate

- Source: `/workspace/bal/venice-52.txt`, checksum pinned in the registration.
- Target: 243740.27; cap: 60 native seconds.
- Five common-input pairs use deterministic `epsilon=1e-12` state
  perturbations with seeds 660048--660052.
- Both arms use the derived binary; only the D20 feature flag differs.
- Arm order alternates by pair.  State input, binary, flags, traces, endpoint
  audit and hashes are retained as scalar/hash evidence.
- Advance only if D20 reaches the target in at least 3/5 pairs.  Report both
  arms' hits, conditional target time, endpoint, attempts, rejects, products,
  activations, selected cameras, removed-energy fraction and norm ratios.

This is a hard gate.  Failure ends D20; no tuning follows.

## Conditional gates

Only after Venice reaches at least 3/5:

1. Final3068, five fresh paired `epsilon=1e-12` inputs, seeds 660053--660057,
   target 1744796.9841897595 and 60-second cap.  D20 must not lose hit rate.
2. The nine practical cells from the pinned B6v7 registration, N=3 paired.
   D20 must have no endpoint regression above 0.15% and no disjoint target-time
   loss on five or more cells.

The scored objective stays plain-L2 SIMPLE_RADIAL with unshared intrinsics and
`k2=0`.  Timing includes all diagnostics.  The frozen Eta2 scientific champion
and B6v7 systems candidate remain the winners until all gates pass.

