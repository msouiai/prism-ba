# Wave 5 mathematical and prior-art audit

Primary sources checked before implementation:

- Hartley and Sturm, *Triangulation*, CVIU 68(2), 1997,
  https://perception.inrialpes.fr/Publications/1997/HS97/HartleySturm-cviu97.pdf.
  Their degree-six construction globally minimizes the sum of squared
  corrections in two pinhole image planes subject to the epipolar constraint.
  It does not establish global optimality for SIMPLE_RADIAL distorted-pixel L2.
- Lindstrom, *Triangulation Made Easy*, CVPR 2010,
  https://www.osti.gov/servlets/purl/983384.  The method is a fast near-optimal
  epipolar correction; the paper's exact two-iteration statement has geometric
  conditions and must not be generalized to every camera pair.
- Jeong et al., *Pushing the Envelope of Modern Methods for Bundle Adjustment*,
  CVPR 2010 / TPAMI 2012,
  https://www.microsoft.com/en-us/research/wp-content/uploads/2010/06/Jeong-CVPR10.pdf.
  Embedded point iterations optimize point blocks inside BA.  A1 differs in
  sparse rational-model triggering, an in-attempt candidate, and a two-view
  global pinhole initializer followed by original-objective polish; those are
  the boundaries to measure, not grounds for a broad novelty claim.
- Agarwal et al., *Bundle Adjustment in the Large*, ECCV 2010,
  https://grail.cs.washington.edu/projects/bal/bal.pdf.  Schur-Jacobi is an
  established BA preconditioner.  Activating it in Eta2 is engineering and an
  attribution control, not algorithmic novelty.
- Frangella, Tropp and Udell, *Randomized Nystrom Preconditioning*, SIAM J.
  Matrix Analysis and Applications 44(2), 2023,
  https://tropp.caltech.edu/papers/FTU23-Randomized-Nystrom-SIMAX.pdf.  Their
  method targets regularized PSD systems.  A sketch of the unshifted operator
  can be reused algebraically across scalar shifts, but coupled point damping
  changes Eta2's Schur operator; reuse is valid only while tau is frozen.
- Demmel et al., *Square Root Bundle Adjustment for Large-Scale
  Reconstruction*, CVPR 2021,
  https://www.usenko.net/pdf/demmel2021rootba.pdf.  Landmark QR/nullspace
  marginalization is established and supplies the robustness boundary for B5.
- Katyan, Das and Kumar, *Two-Grid Preconditioned Solver for Bundle
  Adjustment*, WACV 2020,
  https://openaccess.thecvf.com/content_WACV_2020/papers/Katyan_Two-Grid_Preconditioned_Solver_for_Bundle_Adjustment_WACV_2020_paper.pdf,
  and Das, Katyan and Kumar, *A Deflation Based Fast and Robust Preconditioner
  for Bundle Adjustment*, WACV 2021,
  https://openaccess.thecvf.com/content/WACV2021/papers/Das_A_Deflation_Based_Fast_and_Robust_Preconditioner_for_Bundle_Adjustment_WACV_2021_paper.pdf.
  Two-level and deflation preconditioners have direct BA prior art.  A future
  Eta2 result could concern a particular matrix-free GPU construction and its
  interaction with an inexact forcing rule; it cannot claim the first coarse
  or deflated BA solve.
- Weber et al., *Power Bundle Adjustment for Large-Scale 3D Reconstruction*,
  CVPR 2023,
  https://openaccess.thecvf.com/content/CVPR2023/html/Weber_Power_Bundle_Adjustment_for_Large-Scale_3D_Reconstruction_CVPR_2023_paper.html.
  Inverse power-series solution of the Schur complement is established BA
  prior art.  Prism's earlier PoBA-style polynomial control was quality-neutral
  and did not repay its extra products, so wave 5 does not reopen it.
- *Power Variable Projection for Initialization-Free Large-Scale Bundle
  Adjustment*, ECCV 2024,
  https://www.ecva.net/papers/eccv_2024/papers_ECCV/papers/02034.pdf.
  PoVar combines object-space error, variable projection and a power expansion.
  This narrows any broad novelty claim for wave 4's object-space opening; only
  its precise constrained-opening construction and measured basin effect could
  remain distinct.
- Safari, *Matrix-Free Shared Intrinsics Bundle Adjustment*, CVPR 2025,
  https://openaccess.thecvf.com/content/CVPR2025/html/Safari_Matrix-Free_Shared_Intrinsics_Bundle_Adjustment_CVPR_2025_paper.html.
  Matrix-free products and single-precision stability are active BA topics.
  Its shared-intrinsics problem differs from Eta2's unshared-intrinsics BAL
  objective, but it prevents a broad “first matrix-free GPU BA” claim.

## Boundaries established by wave 5

The wave-5 systems winner is an implementation result: batch independent FP64
dot returns and remove a diagonal calculation whose value is dead in the
classical-LM path.  Neither operation is algorithmically novel by itself.
Their value is the measured end-to-end result and the complete arithmetic and
tail audit.

Two negative findings have a more interesting methodological boundary.  First,
a backward-stable square-root/Gram operator can choose a different BA basin
even when its frozen-system action agrees to FP64 roundoff.  Second, standard
mixed-precision iterative-refinement guarantees preserve an accurately solved
linear-system fixed point, but Eta2 stops at a loose forcing tolerance; many
directions pass that gate, and the low-precision trajectory need not preserve
the nonlinear algorithm.  These are empirical claims about inexact nonlinear
least squares, not claims that square-root BA or iterative refinement are new.

The OpenCV project's official `correctMatches` implementation was used only as
an independent transcription aid for the Hartley-Sturm polynomial.  Numerical
tests compare the transcription against the epipolar constraint and direct
cost sampling before it is used in the replay.
