# SHIFTDIAG: coordinate and normalization definition

Computed inside SolveMFreeShiftedCG at every fired checkpoint, BEFORE any
candidate scoring, on the multi-shift CG iterates xs[l], l=0..4:

- SPACE: the equilibrated camera-block CG space (dimension n_c), i.e. the
  x_scaled vectors of the zeta-recurrence PRIOR to MFScaleVec un-equilibration
  and prior to the shared-intrinsics broadcast. Camera block only; the point
  block never enters.
- SHIFTS: sigma_l = lam_cam * 10^(l - grid_down), grid_down=2, L=5, where
  lam_cam is the CURRENT outer iteration's damping (dynamic, not a fixed grid).
- METRIC: maxrel = max over the 10 unordered pairs (a,b) of
      || xs[a] - xs[b] ||_2 / max( ||xs[a]||_2 , ||xs[b]||_2 )
  (cublasDnrm2 on device, fp64).
- LINE FORMAT: [sd] it=<outer k> ck=<cg_it+1> maxrel=<%.3e> nrej=<n_reject so far>
- Phase boundary claim: maxrel ~6e-4 grind vs ~0.95 opening/storm was measured
  on ladybug-49 / dubrovnik-88 / final-3068, library config
  (--tau_pt 3e-3 --func-tol 1e-6 --max-consec-fail 3, env
  OCA_RHO_LAMBDA=1 OCA_GRID_DOWN=2 OCA_RHO_SHIFT=1 OCA_ALPHA_RHO=1).
- CAVEAT for cross-solver comparison: our equilibration is symmetric Jacobi on
  the reduced camera system; a post-clipping equilibrated-camera diameter in
  Eta2 coordinates is a DIFFERENT functional and thresholds do not transfer;
  compare phase-boundary LOCATION (outer index), not raw maxrel values.

Source: oca_cuda.cu (sha256 below), OCA_SHIFTDIAG block in the checkpoint loop.
The independent-CG-vs-Nystrom-PCG iteration study (shared 800-1218 vs summed
1629-1900) is spectral_study.py + spectral_study.json: dense S assembled at the
BAL start by FD Jacobians (9-DOF Snavely, k2=0, tau_pt=3e-3 Marquardt on
diag(V), symmetric-Jacobi equilibrated), CG tol 1e-4 on rel residual.
