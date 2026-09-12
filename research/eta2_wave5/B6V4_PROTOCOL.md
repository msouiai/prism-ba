# B6v4 preparation pruning and fusion protocol

Registered before building or running the B6v4 derived binary.  B0 attributes
10.46% of the frozen Eta2 panel wall to point-factor and reduced-RHS
preparation.  Inspection of the champion's CD=9 classical-LM path finds four
avoidable device passes:

1. `MFPointFactorTau` writes the damped 3x3 point factors and the immediately
   following `MFVinvApply` reloads them to solve `V_tau^-1 b_p`.
2. `MFRhsDiagFused` computes both the RHS correction and the diagonal of the
   Schur complement, after which classical LM zeros the computed diagonal and
   uses `diag(H_cc)` for equilibration.
3. `MFDiagHcc` writes `diag(H_cc)` and `MFMakeEquil` immediately reloads it.
4. The reduced RHS is copied, updated by cuBLAS AXPY, and later scaled by a
   separate kernel.

The active preparation arm performs the same mathematical operations while:

- forming the damped point factor and solving its first RHS in one
  point-owned kernel;
- computing only the RHS correction in the observation kernel, omitting the
  Schur-diagonal work that classical LM discards;
- constructing the equilibration directly from the stored `H_cc` diagonal;
- evaluating `(b_c - correction) * E` in one coordinate-owned kernel.

The arm is `OCA_W5_PREP_FUSE=1`.  It is legal only for the frozen champion's
CD=9, unshared-intrinsics, single-shift, PCG, classical-LM, diagonal-equilibrated,
tau-split configuration, with no selective point floor, block scaling, or
alternative RHS/diagonal path.  Unsupported combinations fail loudly.  Flag
off must reproduce the frozen binary within the 0.15% trajectory gate.

The non-atomic point-factor, equilibration, and RHS-finalisation transforms
receive a standalone bitwise audit against their separated forms.  Removing
the discarded diagonal changes when observation threads reach the existing
RHS atomics, so the native result is expected to remain in the champion's
ordinary reduction-order stochastic class rather than be bit-identical.

The native comparison has four fresh, interleaved arms:

- `off`: derived binary, both changes disabled;
- `prep`: preparation arm only;
- `dots`: B6v2 device-result dot batching only;
- `dots-prep`: both changes.

Run N=3 compatibility against the frozen binary, then N=3 on all nine
practical cells.  Continue with N=3 Muell/profile and fresh N=10
Final3068/Venice tails only if `prep` improves the panel against `off` and/or
`dots-prep` improves it against `dots`, without changing median work counts.

Promotion requires a geometric-mean target-time gain, no disjoint timing loss
on a majority of cells, no stable endpoint movement above 0.15%, and no tail
hit-rate loss.  A result that merely shifts work into a different profile
bucket, changes the nonlinear trajectory materially, or fails to add to the
dots-only winner is rejected.
