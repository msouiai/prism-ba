# Lambda hysteresis pilot, frozen before measurements

Priority experiment requested by user; previous coordinators/lock waiters
paused, active previous solver allowed to finish without timing interruption.
Resume previous processes after this experiment and checks finish.

Selection: among per-shift best scored checkpoints with reduction at least
0.95 of the best positive menu reduction, choose the shift nearest the last
successfully accepted menu shift in absolute log-lambda. No history on first
step. Keep history after a backtracking rescue. Apply before existing alpha
search; all original acceptance, backtracking and center updates remain.
No extra candidates: existing menu gate can mean some shifts are unscored.
This tests preference among observed candidates, not a complete-grid oracle.

Same frozen new binary for control and hysteresis; both use logging and
per-shift snapshot overhead. No production default change. Base flags match
Config A plus retry-cache, multi-RHS, diag-norm, 5 shifts and guarded8.
N=3, alternating control/hysteresis order. Venice52 and Ladybug1197 full600;
final3068 cap100 is a retry-stress/transient pilot, not a converged comparison.
No threshold tuning after outcomes. A logging-off timing pilot on Venice52
is separate to estimate measurement overhead, not pooled into main control.

Measure candidate top-two reduction gap, hypothetical preference changes in
control, realized switches, actual selected lambda motion, center motion,
retries/matvecs/scored work, endpoint cost and time to common fp64 targets.
N3 ranges and 0.15%-plus-disjoint cost gate; no tail or convergence claims.
