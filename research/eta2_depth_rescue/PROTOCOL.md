# Eta2 one-shot depth rescue — registration, 2026-09-11

Frozen parent: research/eta2-external-coverage at 9f4fc8754376b9b8f005def91845c8d3d84ed465.
Original Eta2 source, 44 headers, manifest, and binary remain unchanged.
This registration precedes building or measuring the candidate.

## Mathematical hypothesis and limits

For the current accepted state, eliminate points from the damped normal
equations: A_lambda x = b_lambda, with
A_lambda = U_lambda - W V_lambda^-1 W^T in equilibrated camera coordinates.
After j PCG iterations, x_j minimizes the SPD quadratic over its Krylov
space. In the SPD case its model error is (x_j-x_*)^T A_lambda (x_j-x_*)/2.
A loose Euclidean residual test does not bound that error independently of
the smallest eigenvalue. Tightening the residual can reveal directions
missed by shallow solves. It cannot repair a wrong nonlinear model or a
damping floor, and it need not reduce the step norm. No novelty claim follows
from this standard observation; the experiment tests a conditional policy.

Increasing only the iteration cap is insufficient: the existing Eta2
forcing test often stops after one or two iterations. Probes use residual
ratio <= min(original_eta, 1e-3), cap 512, same fresh Hcc block PCG,
original floating-point representation and true-cost acceptance. Score only
the terminal deep iterate. Negative curvature rejects the probe; it cannot
escalate damping and secretly consume several deep solves. Original radius,
point safeguard and full-model rho > .1 acceptance remain required.

## Arms

- original: existing frozen binary, exact champion flags.
- off: research binary, both new flags absent; compatibility control.
- stop: OCA_DEPTH_STOP=1. After the existing backtracking stop confirmation
  has completed and the original solver would actually terminate, schedule
  one deep solve from its current accepted state. Restore the camera damping
  center recorded at the start of the current flat-decrease streak, clamped
  to the unchanged numerical floor. This differs from the existing reject
  streak center. Rebuild the coupled point system at that damping; never
  reuse factors for a different tau. Keep the radius unchanged. Disable
  backtracking for the probe. On failure, stop at the original endpoint;
  on acceptance, resume the ordinary controller. At most one stop probe per
  run, even if backtracking later rearms. Log the original stopping endpoint
  and native time, giving a within-run counterfactual miss/hit witness.
- declip: OCA_DEPTH_DECLIP=1. Following the first accepted ordinary step
  with raw camera norm / attempted radius > 10 and rho in [.25,.75],
  schedule one deep solve at the next accepted state, using its current
  damping center and radius expanded by exactly 4. Preserve the true-cost,
  full-model and radius-feasibility gates. On rejection, restore controller
  scalars, invalidate factors and resume the original attempt at unchanged
  state. On acceptance, use the ordinary radius/damping update for this
  expanded radius. At most one de-clipping probe per run. This is a next-state
  intervention, not a rescore of the preceding step. No scene-name inputs.
- both: enable both flags, only in the no-regression screen initially.

The numerical safeguard is retained. Stop-center reset changes camera and
coupled point damping, so any win of that arm is not attributed to depth
alone without another matched ablation. The clipping trigger's historical
coverage is 10/10 frozen Venice runs, first zero-based outer 38; the quoted
3757/97 late example belonged to a separate tighter-forcing experiment.

## Evaluation

Serialize builds, native solves and CPU endpoint audits with
/tmp/prism_gpu.lock on host 2237c6528e79, RTX 2000 Ada. No cross-host speed
ratios. Same input bytes, zero k2, fixed observation L2, FP64 independent
endpoint audit. Scrub unrelated environment flags. Record every return
code, exported state, native target crossing, final cost, outers, rejects,
Schur products, depth/true-residual/trigger diagnostics, and cap hits.

Use 600 outers and 60 native seconds for all primary arms. A probe must fit
the original caps; caps are never extended on its behalf. The original
target check precedes either trigger. Failed deep steps do not alter the
accepted state. Count their products and time, never hide rejected work.
Native target hit requires the existing conservative 1e-8 margin; independent
endpoint must also meet the fixed target. Crossing times are conditional
on hits; report observed N-hit/N, never convert misses to fast solves.

1. Compatibility: original vs off, N=3 on Dubrovnik88. Compare objective
   traces/endpoints and triggers (zero), then apply the screen tolerance.
2. Final3068: original vs stop, N=10 each, alternate order by repeat,
   fixed target 1744796.9841897595. Failure criterion: any misses remain,
   or conditional median crossing time exceeds original by >20%.
   Log per-candidate original stop costs to distinguish an actual rescued
   stop from a fresh favorable stochastic trajectory. If fewer than two
   above-target stop witnesses occur, report coverage as insufficient;
   do not claim historical misses were rescued.
3. Venice52: original vs declip, N=10 each, alternate order, fixed target
   243740.27. Failure criterion: still 0/10 hits. Also report wall and
   endpoint changes; a hit alone does not establish a speed improvement.
4. No-regression: Dubrovnik88 and Ladybug1197, original/off/stop/declip/both,
   N=3 each, no target early-exit (ordinary endpoint and native solve time),
   rotating order. A scene/arm fails if paired endpoint is >.5% worse or
   paired native wall is >20% worse. Report medians and ranges too.

Do not tune the trigger, residual tolerance, expansion factor or depth
against these outcomes. If a mechanism fails its gate, keep the frozen
champion. Additional diagnostic variants require an explicit dated
amendment and cannot replace primary misses. New solver and harness stay
on a research branch; no automatic promotion.
