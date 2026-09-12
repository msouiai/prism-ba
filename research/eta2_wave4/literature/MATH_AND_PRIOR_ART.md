# Wave 4 mathematical and primary-source audit

In progress. Entries distinguish facts derived here, primary-source support,
and literature still to be read. No novelty priority claim is made.

## Acceptance aside: established method, controlled ablation

[Ceres' solver documentation](https://ceres-solver.readthedocs.io/latest/nnls_solving.html#_CPPv4N5ceres6Solver7Options21min_relative_decreaseE)
specifies default minimum relative decrease 1e-3. Its nonmonotone section allows
temporary increases and returns the lowest-cost visited state. That supports
the proposed comparison; it does not mean changing Eta2's threshold reproduces
Ceres' complete controller. Our max-window prototype retains Eta2's current-cost
rho for radius/lambda updates and is not advertised as Ceres' implementation or
as an implementation of the complete Toint convergence theorem.

## Corrections derived directly from the scored model

1. SIMPLE_RADIAL has q=-Y_xy/Y_z and pixel=f(1+k1*||q||^2)q. With k1 nonzero
   the numerator/denominator powers reach degree three; the residual is
   rational, not generally linear-fractional. Fixed-depth projection at s=0
   still has a cubic distortion term. It is not an affine residual or a
   convex translation/point least-squares problem unless distortion is removed
   from that model. We retain distortion and withdraw that convexity premise.
2. For a joint step, first-order Y omits both the second-order rotation term
   and the rotation-times-point-step term. Updated focal/distortion parameters
   also couple with geometry. The rational-geometry attribution is a surrogate;
   comparison to the true retraction is mandatory.
3. BAL/Snavely uses signed camera depths. A valid relative denominator bound is
   |delta Z| <= kappa*|Z|. Its one-sided counterpart is
   sign(Z_old)*Z_new >= epsilon*|Z_old|, when preserving the existing sign is
   intended. Blindly requiring Z>=epsilon*Z_old changes the meaning for the
   usual negative-depth observations. Sign preservation is not a full guarantee
   against a small positive distance to a projection pole.
4. Cost-matching scalar weights do not make object-space IRLS tangent or a
   majorizer of pixel L2. Counterexample: one undistorted observation on the
   optical axis, residual r=x/z, perpendicular residual e=x. At (x0,z0),
   w=1/z0^2 gives Q=x^2/(2z0^2)=F at that state, but Q_z=0 while
   F_z=-x0^2/z0^3. Thus fixed points of that IRLS are not automatically pixel-L2
   stationary points. True-cost acceptance and a final original-L2 solve can
   still make it a legitimate opening experiment.
5. Joint translation/point object-space minimization has an all-zero collapse:
   scaling every translation and point toward zero scales its frozen-weight
   objective toward zero while perspective pixels stay unchanged. Known-fixed
   geometry PnP has no such variable scene scale. A BA opening must explicitly
   constrain scale and translation gauge and audit this collapse, rather than
   transfer a PnP convergence statement to unrestricted joint BA.
6. Active affine constraints require equality feasibility, multiplier signs and
   complementarity in the QP. A finite rank-one penalty alone is not an exact
   active-set solve. Neither a sparse active set nor a sparse detector is
   guaranteed merely because one recorded cost gap concentrated in one point.
7. Large ||J_point|| is sensitivity, not increased statistical weight of that
   observation in the plain-L2 objective. It does not prove its optimal
   residual tends to zero. A frozen-anchor 1-DOF point no longer stays exactly
   on an observation ray when the observing camera also moves. O4 must score
   the updated camera and record any approximation or hard-constraint bias.

## Primary sources inspected so far

- [Triggs et al., Bundle Adjustment — A Modern Synthesis](https://www.cs.jhu.edu/~misha/ReadingSeminar/Papers/Triggs00.pdf):
  full 75-page manuscript read, including appendices. Section 4.3, footnote 8,
  explicitly warns that freezing projective-depth weights optimizes the wrong
  gradient. Section 7 also cautions about slow weakly coupled alternations.
- [Lu, Hager and Mjolsness, TPAMI 2000](https://computableplant.ics.uci.edu/papers/2000/LuHagerMjolsness.pdf):
  full 13-page author copy and convergence appendix read. Its problem has known
  3D geometry and camera internal calibration. Global convergence here is
  convergence of an iteration to a fixed point, not a globally optimal BA
  reconstruction. The paper distinguishes scalar depth reweighting from an
  exact anisotropic relation that loses the closed-form rotation update.
- [Rydell, Torres and Larsson, CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/html/Rydell_Revisiting_Sampson_Approximations_for_Geometric_Estimation_Problems_CVPR_2024_paper.html):
  verified author/title and pages 4990–4998. Sampson constraint approximations
  are relevant prior art, not evidence that our particular denominator detector
  or full distorted BA polytope is already proved useful.
- [Yang et al., GNC for Robust Spatial Perception](https://arxiv.org/abs/1909.08605):
  main text and supplement read before the robust-to-L2 prototype. GNC usually
  continues toward a robust target; our Cauchy-to-L2 schedule reverses that
  direction. Its guarantees do not transfer to Eta2's nonconvex inner solve.

- [Kahl and Hartley, TPAMI 2008, Multiple-View Geometry Under the L-infinity Norm](https://www.maths.lth.se/matematiklth/vision/publdb/reports/pdf/kahl-hartley-pami-07.pdf):
  full 15-page published author copy read, including cheirality proofs and
  experiments. DOI 10.1109/TPAMI.2007.70824; 30(9), 1603–1617. Section 6.1
  gives the known-rotation/calibration quasiconvex structure-and-translation
  problem, with fixed first-camera translation and one point depth for scale.
  It solves fixed-error SOCP feasibility problems by bisection; this is not
  joint convexity in the unknown error bound, nor a proof for distorted pixel
  L2. Their experiments already use the solution as an initializer for L2 BA.
- [Fusiello and Crosilla, Revisiting Procrustean Bundle Adjustment, ISPRS Annals 2016](https://isprs-annals.copernicus.org/articles/III-3/35/2016/):
  all seven pages read. DOI 10.5194/isprs-annals-III-3-35-2016, pages 35–41.
  Very close O1 prior art: object-space BA, alternating SVD rotations,
  translations and ray-depth variables, with robust reweighting. Depth scales
  are normalized to prevent collapse. Their robust weights operate per track;
  they do not use our cost-matching pixel/object scalar weight or joint
  translation/point QP. Object-space BA, rotation SVD and IRLS themselves are
  therefore not new. Their 2015 predecessor and Commandeur's earlier STIMIDIO
  formulation further restrict any priority claim. A measured GPU constrained
  opening could still be an implementation/empirical contribution.
- [Transtrum and Qiu, Model Reduction by Manifold Boundaries, PRL 2014](https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.113.098701):
  full six-page publisher manuscript read. Sloppy Fisher-information spectra,
  manifold-boundary reduction and refitting do not establish that a high
  perspective Jacobian norm makes an observation an exact zero-residual
  constraint. The failed O4 frozen-ray replay is reported separately.

O2 primary-source audit is assigned to the second agent at the user's explicit
request for parallel O2 work. All other priority/proof assertions remain
provisional until the corresponding source audit is recorded.
