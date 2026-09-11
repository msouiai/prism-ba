# Eta2 opening phase hybrid — registered before candidate measurements

Own the Eta2-side prototype; Claude owns the reverse handover and rescue ladder.
Original frozen Eta2 source/flags remain unchanged. No deep-reject feature,
stopping-policy change, robust kernel, or point-polishing addition in this study.

A shared sweep uses five camera shifts lambda*[.01,.1,1,10,100] with the
point damping fixed at the CENTRAL lambda, so K=E S(tau) E and b'=E b(tau)
are the same across shifts. This is not five joint-damping LM solves. Use
ordinary shared-zeta CG, no arbitrary PCG within the recurrence. The point
floor/equilibration are rebuilt normally at the next coupled-damping attempt.

Compare four arms, same frozen Eta2 flags and binary: PCG champion; shared
sweep but score the central candidate only (control for changed linear solver
and phase overhead); shared sweep with all five candidates; and that menu with
winning-shift feedback to the radius controller's next-lambda anchor. Center
scores first; ties keep center. All candidates undergo existing radius clipping
and true-cost scoring; the selected step then passes the unchanged full-GN
rho>.1 check. A model-invalid winner may still cause a rejected attempt; this
prototype does not change the ordering of the champion acceptance pipeline. Backtracking and point safeguards remain.
No fake menu is made by scalar-rescaling the PCG solution.

Measure normalized maximum pairwise CAMERA distance in Eta2's equilibrated
coordinates, before and after radius clipping, from the five-by-five Gram
matrix. A collapse is post-clipping diameter <=1e-3; require two consecutive
accepted, non-rescued, residual-qualified collapsed menus before handover.
This threshold/normalization is provisional pending Claude's exact SHIFTDIAG
metadata; do not silently substitute its interpretation. Handover also occurs
after eight accepted outers as a bounded-opening safety limit (report separately
from genuine collapse). No re-entry after handover in this first prototype.
PCG restarts from zero; no shared Krylov vectors or preconditioner state are
transferred across operators. Failed/nonfinite shared solves fall back to
ordinary PCG at the unchanged central lambda and point damping.

Same 128-iteration maximum and dynamic Eta2 forcing. The first prototype audits
all five true residuals once at sweep exit; charge those five matvecs. Candidates
at an iteration cap remain approximate as in Eta2; only residual-qualified
menus can count toward collapse. Report true residuals and all sweep, Gram,
extra model/cost, and fallback overhead. The shared-versus-five-PCG work claim
does not establish a benefit versus the ONE-PCG champion.

Correctness gate: shared solutions vs independent NumPy solves on several
frozen SPD/near-singular synthetic Schur systems, finite-precision residual
checks, singular/indefinite/zero-RHS behavior; explicit materialized BA Schur
systems; off-mode comparison; no increases in accepted objective. Preserve
true-cost selection and original numeric-recovery semantics on PCG fallback.

Small panel: Ladybug49, Dubrovnik88, Venice52, N=3 rotating arms, 600-outers /
12-native-second cap. Primary fixed targets: 1.01 times the original champion
reference endpoints already published in champion_point_followup (same target
within each scene across every arm), reflecting the user's speed-first priority.
No Caspar comparison. Regardless of small-screen outcome, test the best menu
variant against Eta2 on Final3068 and Final4585 at N=10 each (both bimodal), with
fixed targets from original-champion N=3 calibration, 1.01*median endpoint,
600-outers / 15 seconds; retain all misses, spreads, and stopping reasons.
This is a short target-speed experiment, not a reproduction of Claude's
converged-basin-rate hypothesis or significance test. Choose the menu variant
by more hits first, then geometric-mean target time on fully hit small scenes;
keep both variants' original results. No parameter tuning after outcomes and
no general promotion from one scene. Report limited opening-only scope.
