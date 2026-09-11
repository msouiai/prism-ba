# Champion combinations: registered before new candidate runs

Base: frozen Eta2 source in `research/eta2_champion`, parent research commit
`a48c554`. Keep the original source and defaults unchanged. This is a targeted
follow-up to the specialized low-parallax result, not a reversal of the failed
general-promotion gate.

Native arms retain every champion flag, especially its point safeguard and
camera-radius acceptance. Add (a) one observed-pixel point GN polish, (b) that
polish only on tracks whose maximum ray angle from their first view is <=5
degrees, (c) joint virtual-ray correction, (d) dynamic EW forcing with the final
cap raised from .5 to .8, and combinations of each point method with (d).
Polishing uses the existing champion research kernel's regularization 1e-6,
and whole-track alpha=1,1/2,1/4 cost selection. The selective gate is evaluated
at the proposed state, with its full overhead charged. Virtual rays use parent
geometric image velocity, parent radial-distortion pixel metric, proposed
cameras, and the same effective diagonal point damping as the native solve.

Point methods are additional candidates after the incumbent rescue/safeguard
pipeline. Preserve the incumbent step in a separate existing scratch buffer.
Only replace it with a strictly lower true objective, positive full GN
prediction, and rho > .1. The existing camera-radius test still applies.
Recompute the model on the actual altered displacement; no stale prediction
or unconditional point commit. Charge candidate construction, all extra cost
and model evaluations, and failed probes. These native overlays are explicitly
different from the earlier six-DOF CPU path-replacement experiment.

Correctness: frozen-source hash verification; new flags disabled vs original
binary; tiny native kernel vs independent NumPy calculations for point polish
and virtual rays, including radial distortion, moving cameras, degeneracy and
zero steps; retained original point safeguard. Check all accepted cost traces
are finite and nonincreasing. Fresh low-parallax seeds 510--515 and fresh
depth/joint controls 510--512 are reserved for this follow-up.

Native panel: full Ladybug49, Dubrovnik88, Venice52, rotated arm order, N=3,
600-outers / 12 solver seconds per run. Fix each target at 1.001 times the
median endpoint of three original-champion calibration runs, before running
any candidate. This measures convergence to the champion's attained quality,
not optimality or Caspar superiority. Record misses separately, never turn
their time cap into a target-hit time. Extend a winning addition to Ladybug598
and Muell with the same frozen-target procedure and N=3, 25-second cap. An
extension needs >=1.10x geometric mean speed on the small panel, all targets
hit, and no scene slower by >20%. Otherwise keep Eta2 as champion and report
specialized findings without claiming general promotion.

For fresh CPU geometric holdouts, preserve the previous six-DOF solver and
the 1.01*reference-endpoint target, independently calibrated from truth. Compare
XYZ, virtual-ray, and observed polish at N=3, 3s/160 attempts. These are mechanism
checks and are reported separately from native GPU timing.
