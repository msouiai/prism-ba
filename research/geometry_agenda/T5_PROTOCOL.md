# T5 registration: observability-aware continuation

Three known clusters, 12 cameras/180 points, four bridge points per side.
Four mandatory cases: correct bridges, all corrupted bridges, half corrupted,
and disconnected. Use the T4 generator and bounded independent corruption
of +/-80 px per coordinate. Development seeds0–9, held-out100–109, N=3 with
rotated arm order. This is a small controlled robust-BA experiment, not native
Eta2 or a Caspar comparison.

Fix the final Cauchy objective to `0.5*sum(log1p(||r||^2))`, sigma=1 px.
Continuation stages use `0.5*sigma^2*sum(log1p(||r||^2/sigma^2))`, sigma32,8,2,1.
Weights are frozen within each GN solve, and acceptance uses the exact current
stage objective, not its quadratic surrogate. Larger-scale stages may increase
the final objective; log it explicitly. No observations are removed.

Arms: fixed sigma1; ordinary continuation (four attempts per stage); residual
schedule; information schedule. Residual schedule delays a scheduled reduction
while the 95th percentile residual norm exceeds twice the next sigma.
Information schedule delays if any of the three weakest nonzero modes of the
current undamped 14-D collective information matrix loses >75% of its Rayleigh
information at the proposed scale. Use a fixed initial fine-space metric M,
remove cluster0 gauge, and compare the same directions at the same state;
never add LM damping to the observability measurement. A zero-information
subspace is declared unobservable and cannot justify retaining any bridge.

Min4, max12 attempts per nonfinal stage; at attempt24 force sigma1 for every
continuation arm. Run a common total60 attempts / 2-second cap, including
feature/eigensolve overhead. Final-stage LM uses the same algorithm/starting
lambda continuation rule for all arms. Every final state has therefore spent
at least36 attempts on the prescribed final objective unless time-censored.
Target=Ffinal(truth)+1e-3*(Ffinal(initial)-Ffinal(truth)); freeze before timing.
Time-to-target is counted only after reaching final sigma and includes all
previous work; also report final cost, geometry, stage delays and false-inlier
retention (corrupted observation residual norm<1 px). Disconnected geometry
cannot be counted as recovered. No correspondence labels enter the scheduler.

Gate: information schedule 1.10x faster than both ordinary and residual
schedules with no extra misses, geometry failures or false-inlier retention,
across correct and mixed-bridge cases; all-corrupt/disconnected cases must
remain explicit counterexamples. Otherwise no new adaptive controller.
