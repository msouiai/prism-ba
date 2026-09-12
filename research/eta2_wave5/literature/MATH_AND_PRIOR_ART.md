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

The OpenCV project's official `correctMatches` implementation was used only as
an independent transcription aid for the Hartley-Sturm polynomial.  Numerical
tests compare the transcription against the epipolar constraint and direct
cost sampling before it is used in the replay.

