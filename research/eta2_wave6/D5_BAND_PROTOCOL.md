# D5 protocol: structural gate for a banded camera preconditioner

Registered before computing any band-locality statistic.

## Question

The categorical map proposes banded camera preconditioners for ordered image
sequences.  Wave 5 already showed that replacing Eta2's unreduced camera-block
preconditioner by Schur-Jacobi can improve a frozen linear solve while harming
the finite-iteration nonlinear trajectory.  D5 therefore does not build
another native preconditioner on faith.  It first asks whether a narrow band is
a mathematically credible approximation to the reduced camera operator.

## Graph screen

Use these fixed BAL inputs:

- sequence-family hypotheses: `ladybug-539`, `ladybug-1197`, `venice-52`, and
  `venice-951`;
- controls: `final-3068` (unordered photo collection) and `muell-gba146`
  (production scan).

Build the binary camera-point incidence matrix `B`.  Measure the camera graph
in two fixed weightings:

1. raw covisibility, `B B^T` off the diagonal;
2. track-normalized hypergraph clique expansion,
   `B diag(1/max(m_j-1,1)) B^T` off the diagonal.

For natural BAL camera order and deterministic reverse Cuthill-McKee (RCM)
order, report the fraction of upper-triangle edge mass within camera
half-bandwidths `{1,2,4,8,16,32,64,128}`, plus the minimum half-bandwidths
containing 50%, 80%, 90%, and 95% of mass.  Report track-span and graph-fill
statistics as diagnostics.  RCM is the sole registered reordering; no
scene-specific choice is allowed.

## Numerical screen

Losslessly restore the existing Venice52 outer-39 curvature capture to
`/dev/shm`.  Form its coherent FP64, diagonally scaled Schur matrix

`A = E (Hcc - W V_tau^-1 W^T) E + lambda I`

from the stored FP64 cross blocks and point factors.  Verify the dense action
against the independently saved matrix-free product before using it.  For
natural and RCM order, measure off-diagonal Frobenius energy retained by each
registered band.  Where the exact band truncation is SPD without an adaptive
shift, report the generalized condition number of `(A, M_band)` and compare it
with Eta2's `Hcc` block preconditioner and Schur-Jacobi.  A shifted band is
reported diagnostically but cannot pass the gate because tuning the shift
would introduce another damping policy.

## Native-build gate

A native banded implementation is justified only if all of the following hold:

1. at least two of the four sequence-family scenes retain at least 80% of the
   normalized graph mass inside RCM half-bandwidth 16;
2. the Venice numerical matrix retains at least 80% of off-diagonal Frobenius
   energy at the same or narrower band;
3. that unshifted band is SPD and improves the generalized condition number by
   at least 3x over the frozen `Hcc` block preconditioner.

If any gate fails, stop D5 before a GPU build.  This is a necessary-condition
screen, not evidence that graph weight equals numerical Schur energy or that a
passing preconditioner would preserve Eta2's nonlinear trajectory.

## Reproducibility

Record SHA256 values for every input, the capture archive and its restored
members, this protocol, and the analysis program.  The source capture is read
only; its restored copy is deleted after the compact numerical results are
written.
