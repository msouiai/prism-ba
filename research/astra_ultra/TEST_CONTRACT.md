# Shared test contract, registered before adviser candidate outcomes

All methods preserve observations, original pixel L2 cost, fixed intrinsics,
camera0 pose and point0 z gauge. They use the same baseline LM initialization
and lambda/rho rules unless an explicitly registered comparator changes one.
Count every setup, extra solve, relinearization, feature, rejected trial and
verification. Time to an identical fixed target is primary; never compare each
method's own stopping point. Report misses and continuous global geometry error.
One BLAS/OpenMP thread, serial timed work; do not alter production Eta2.

Prepare new synthetic view-diverse inputs independently of proposed algorithms:
eight cameras on an orbit looking toward [0,0,-5.5],120 points, five random
observations/point, pixel noise sigma0.2. Orbit half-angle0.55rad for depth and
joint-error families;0.025rad for low-parallax controls. Camera height varies
with orbit angle. Generating intrinsics f500, k1=k2=0, fixed in every solve.
Initial depth error is applied along rays from the first camera center with
log-depth sigma0.45 (depth/low-parallax), or Cartesian sigma0.15 (joint).
Initial rotation sigma0.025rad for depth/low-parallax,0.12rad for joint;
camera-center perturbation sigma0.02. Gauge entries equal generating truth.
Invalid initial observed depths cause a recorded generation failure, not silent
seed replacement. Screening seeds500..503 in each family, before any candidate
outcomes. If an idea passes its own gate, validation seeds510..515 are untouched
until registration of that follow-up. No data-dependent scene selection.

Reference construction: bounded ordinary LM from generating truth,400 attempts
or3seconds maximum. Freeze its feasible endpoint and cost independently of
candidate arms. Primary target1.01*Fref and secondary1.001*Fref; neither is called
an optimum. This avoids arbitrary looseness from large initialization cost.
Reference geometry is recorded and reference generation is outside all solve
timings. Candidate initial states and observations never use that endpoint or
truth as a feature. Initial-state ordinary LM remains the runtime comparator.

Also retain unchanged packed24-camera/300-point Ladybug49, Dubrovnik88 and
Venice52 development probes and their existing references. Primary BAL target
Fref+1e-3*(F0-Fref), deeper diagnostic tau1e-5. These are not new independent
scene families. Fresh native or larger tests require a successful bounded gate.

Screen N=1 first for algebra/obvious failure, then N=3 rotated order for promising
fixed comparisons. Typical gate>=1.10x paired median time benefit, no additional
target misses, and no new severe geometry deterioration. Report smaller effects
without automatic dismissal or promotion. Each track must register its own
candidate arms, exact safeguards, iteration/time cap and stop rule before runs.
Raw traces, reference/input hashes and endpoints remain reviewable.
