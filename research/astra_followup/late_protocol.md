# Track A1: late collective correction oracle

Registered from Astra's initial protocol before this experiment's outcomes.
This tests the surviving late-correction hypothesis, not another unconditional
opening. Existing packed24-camera/300-point Ladybug49, Dubrovnik88, Venice52
inputs are read unchanged. The previously bounded reference Fref is reused.
Targets: Fref+tau*(F0-Fref), tau=1e-3 and1e-5; neither is called an optimum.

Generate ordinary-LM trajectories with the reference's actual lambda updates,
capturing immutable states immediately after accepted steps k=2,4,8. Save
the next lambda, current cost, accepted/rejected counts and prefix elapsed
time. Do not reset lambda on resumption. A no-coarse resumption must exactly
reproduce the baseline endpoint and remaining fine-step count before results
are interpreted. Run cap200 attempts/3 seconds per baseline or resumed tail.

At each available parent, compare continued ordinary LM with one/two exact
nonlinear bridge-only coarse steps and one/two matched linear coarse steps.
Rebuild the same automatic confidence partition; charge partition, coarse
steps and final full-objective verification. Original coarse diagonal damping
and line-search are shared by nonlinear/linear controls; no claim is made
that this is inherited P'DP. After a correction, invalidate the Jacobian and
resume the saved fine lambda/controller. Preserve full state/gauge/depth tests.

N=3, rotated arm order. Total time = measured ordinary prefix + intervention
and resumed tail. Also report paired tail time and actual fine iterations saved.
Continued ordinary LM is the alternate use of this computation budget; do not
compare immediate coarse decrease with an idle baseline. No timing overlap.

This is a hindsight upper screen: choosing the best insertion time separately
per scene is not a deployable controller. Require at least1.10x complete-run
time-to-target benefit on more than one real family, no new misses, and actual
fine-work savings before fitting a trigger or scaling. If even the local
oracle fails, close the current late-correction schedule without retuning.
Future triggers would compare current coarse/fine quadratic decrements under
one physical metric and charge feature computation; they are conditional.
