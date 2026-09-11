# T1 pinhole mechanism screen

Register before evaluating synthetic candidate outcomes. This follows the real
capture audit and isolates perspective/pose model error from radial distortion.

- Six fixed-intrinsics pinhole cameras and 80 points, four observations per
  point, Gaussian pixel noise sigma 0.25. First camera pose and point0 z fix
  the seven similarity gauge freedoms. No projections may have z >= -1e-8;
  the threshold is explicit in the fixed synthetic world units, never a
  denominator replacement in the projection formula.
- Two families: point-depth perturbation (log-depth sigma 0.7 plus pose noise)
  and rotation perturbation (sigma 0.2 radians plus small position noise).
  Development seeds 0..9, held-out seeds 100..109 per family.
- Initial candidate grid lambda = 1e-6, 1e-4, 1e-2, 0.1, 1, 10. Every candidate
  starts from the same immutable parent. These are different damped systems,
  not an assumed scalar-shift Schur family. Exact reduced Cholesky solves make
  linear numerical error independently checkable.
- Test whether prospective fractional-depth statistics improve held-out
  failure prediction over damping, step norm and numerical residual. Require
  +0.05 pooled AUC without a sign reversal on either family before enabling a
  depth controller. Include rotation-dominated counterexamples.
- If that gate passes, compare a temporary quadratic depth-step penalty with
  scalar LM, stronger point-only damping, and global step shortening. Include
  an anchored inverse-depth coordinate control under the same pixel objective.
  Tune only on development seeds. Use original-objective target
  `F_ref + 1e-4*(F0-F_ref)` with F_ref equal to the true-state cost (a reference,
  not an optimum), 80 attempts and 2 seconds per run. Report camera/point error
  in the common fixed gauge and valid-depth counts. All extra construction and
  trial evaluation time is charged. The general promotion bar remains 1.10x
  with no added geometric failures; CPU gates alone cannot promote over GPU Eta2.

Use a dense augmented least-squares reference on tiny instances to validate
the Schur solution, including the depth penalty's cross block. Fixed-matrix
Cholesky factors can serve new RHS vectors; changing lambda or penalty forces
a new factorization. Dependency: isolated SciPy 1.16.2, NumPy 2.1.2.
