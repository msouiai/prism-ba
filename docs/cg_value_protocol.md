# CG marginal model-value pilot

Registered before measurements, 2026-09-10. Incumbent: initial lambda 0.1,
sustained eta multiplier 2 capped at 0.5. No production changes.

For a fixed SPD reduced system A and fixed SPD preconditioner M, PCG gives
delta_j = alpha_j (r_j^T M^-1 r_j)/2. In exact arithmetic this is the decrease
in q(x)=x^T A x/2-b^T x at that step. Accumulated G is model decrease; it is
not a bound on the remaining error and is not the final undamped BA gain.
Radius clipping, eliminated-point contributions, nonlinear curvature and
floating-point loss of conjugacy limit how well it predicts actual progress.

Use existing alpha and r^T z: no additional GPU kernels, reductions or buffers
in performance runs. Host steady-clock timestamps measure assembly/factor/PCG
setup and CG work. The previous attempt's post-CG scoring/acceptance duration
estimates the next scoring cost (zero before the first attempt). These host
times use the solver's existing synchronization; no new CUDA synchronization.

At depth j, compare the last three steps' summed model gain / elapsed time
against theta*G/(setup + CG elapsed + previous post-CG elapsed). Two consecutive
qualifying windows are required, hence earliest stop at depth 4. Candidate rate
uses theta=1; candidate conservative uses theta=0.1. A work-count control uses
last-three mean gain <= G/j, ignoring setup and nonuniform iteration cost.
This is a backward-looking estimate of marginal value, not a reliable forecast
of later spectral progress. Parameters are frozen, not fit to transfer scenes.

Extra termination requires estimated residual <=0.5*||b||, still above the
champion stopping tolerance. Existing true-residual verification checks this
0.5 bound on extra stops; original forcing can always stop earlier. The
original radius, true BA cost, predicted full-model reduction and acceptance
checks remain. Disable extra stops on retries, after a previous rejected or
rho<0.25 attempt, and permanently after numeric repair. First attempt eligible.

This is established quadratic-decrease truncation adapted to this BA engine,
not an RL policy or a novelty claim. See Nash, *A survey of truncated-Newton
methods*, https://doi.org/10.1016/S0377-0427(00)00426-X, and Hestenes/Stiefel,
*Methods of conjugate gradients for solving linear systems* (1952),
https://nvlpubs.nist.gov/nistpubs/jres/049/jresv49n6p409_A1b.pdf.

## Verification and experiment

CPU tests: marginal-rate decisions, setup amortization, residual guard,
passive mode, acceptance/retry/repair fallback; independent dense SPD PCG
checks the accumulated-gain identity. GPU N3 parent/new-off/passive smoke
must preserve work and audited costs within 1e-7. Separate N3 passive GPU
identity runs evaluate b^T x-x^T A x/2 explicitly (relative discrepancy <=1e-6);
their added matvecs/timing are excluded from performance comparisons.

Development: Ladybug598, Dubrovnik356, Venice89, existing fixed targets and
4s caps; champion, passive, rate, conservative, work-only x N3 =45 runs.
Choose rate or conservative by mean log median target time relative to champion;
miss penalty 4*cap. Freeze selected arm before transfer. No high-damping stress
selection. Same binary for all performance arms; initial lambda 0.1.

Frozen transfer: Trafalgar126 and Final1936 at existing primary and tighter
(primary/1.01) targets, Muell146 at existing primary target. N3 champion,
passive, selected and work-only =60 runs. Tighter Muell remains excluded
prospectively because all previous arms missed its12s cap. These are familiar
research scenes, not pristine population holdouts. Target costs in frozen JSON.

Extend to Final13682 primary27591576.557625167 and tighter27318392.631312046,
N3 four arms (24 runs,20s caps), only if every selected/champion transfer run
hits, geometric speedup >=1.05, and no setting slows >10%. Otherwise retain
champion and skip largest. No fresh Caspar claim without fresh measurements.

600 native-second ceiling,600 outers, local /tmp/prism_gpu.lock serialization.
Every endpoint gets an independent CPU FP64 original-observation audit <1e-7.
Target hit requires actual TARGET event within cap and audited cost <=target;
no interpolated crossings. Report N3 medians/min-max, outers/rejects/matvecs,
intervention counts, misses and all controls. Freeze binary/code/protocol/input
hashes. Store bulky evidence in /tmp/prism-cg-value, durable compact package
under /workspace. No new large-scene run if the registered gate fails.
