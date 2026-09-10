# BA gradient, model discrepancy and forcing pilot

Preregistered 2026-09-10 before new measurements. Best tested global baseline:
initial lambda0.1, sustained eta multiplier2, all guarded coupled-LM flags from
the previous confirmation. Keep this baseline in every comparison.

The reduced RHS `bc-W(V+lambda Dp)^-1 bp` changes with point damping at fixed
geometry. Instead measure `G=hypot(||bc||/||bc_initial||,||bp||/||bp_initial||)`.
The two initial block normalizers stay fixed. G is independent of damping at
fixed geometry, but is not invariant to arbitrary within-block reparameterization.
Its computation costs two FP64 norm reductions per fresh assembly, charged to
native solve time. It is a convergence signal, not the norm used to certify CG.

Seven arms: original reduced-RHS forcing; champion eta2; constant eta0.5;
safeguarded EW2 on reduced RHS; safeguarded EW2 on full normalized gradient;
gradient EW2 with model-discrepancy floor; that floor plus moderated lambda decay.
EW2: min(0.5,0.9*(G_new/G_old)^2), guarded below by0.9*eta_old^2 when that
guard exceeds0.1. Reuse forcing within a retried outer; do not advance history
without a new linearization. Original/champion retain exact prior behavior.
Model floor: eta >= min(0.5,sqrt(abs(1-rho_previous_accepted))). Joint rule:
on acceptance, lambda_next >= lambda_used*clip(sqrt(abs(1-rho)),0.1,1).
No changes to rejection escalation, true residual verification, nonlinear
acceptance, point repair or radius constraints. These discrepancy mappings are
heuristics to test, not theoretical error bounds or novelty claims.

Development: Ladybug598, Dubrovnik356, Venice89; initial lambdas0.1 and10,
unchanged fixed targets from the trajectory pilot, 4s caps, N3 per arm.
Choose among the three full-gradient arms solely by geometric median target
time versus champion; a miss is penalized at4*cap. Preserve all controls.
Report leave-family-out selection as a diagnostic; do not use it to retune.

Freeze winner then evaluate against champion and reduced safeguarded EW2 on
Trafalgar126, Final1936, Muell146, using the previous targets AND targets/1.01,
N3, lambda0.1. These scenes are excluded from this rule selection but familiar
from earlier research. No pristine-holdout or population certainty claim.
Proceed to Final13682, both target27591576.557625167 and anchor27318392.631312046,
N3 same three arms, if transfer geometric speedup >=1.05, every target hit,
and no setting >10% slower. Otherwise stop the extension and retain champion.
All targets frozen before measurement. No forced novel/winning conclusion.

600 native-second ceiling, 600 outer cap, native caps4/8/12/20s by scene,
serialized GPU, independent original-observation FP64 endpoint audit <1e-7.
Off/champion N3 must match frozen parent work/cost before the sweep. Meaningful
CPU checks cover damping invariance of full gradient at fixed geometry, EW2
safeguard/history, and accepted-only lambda control. Bulky outputs in
/tmp/prism-ba-accuracy; repository contains source and reports.

Prior art: [Eisenstat–Walker forcing](https://users.wpi.edu/~walker/Papers/forcing_terms%2CSISC_17%2C1996%2C16-32.pdf)
and [inexact Newton BA](https://www.microsoft.com/en-us/research/publication/bundle-adjustment-in-the-large/).
The root-finding convergence theorem does not automatically transfer to clipped,
Schur-reduced Gauss–Newton. Established forcing controls are essential ablations.
