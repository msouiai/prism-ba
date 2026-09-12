# A2 adaptive robust exit and A4 acceptance threshold

Registered before the fresh N=10 cohorts.

## A2

Retain wave 4's fixed Cauchy scales and at most two accepted steps per scale.
Before a robust stage takes its first step, compute the fraction of original
observations whose current Cauchy IRLS weight is below 0.5.  Exit directly to
plain L2 when that fraction is below **0.1%**.  The threshold is fixed from the
wave-4 detector's pre-registered locality scale, not selected from wave-5
outcomes.  Recheck after each accepted robust step.  All counting, transfers,
and handover work is charged.  Target stopping remains disabled until L2.

Fresh Final3068: same-derived-binary off versus adaptive opening, N=10,
alternating order, target 1744796.9841897595.  Also run Venice52 N=10 as the
opposite-tail control.  Proceed to the nine practical cells at N=3 only if the
Final3068 hit count is no worse than off and at least one tail improves.
Promotion requires the reliability signal to survive and practical geometric
mean time <=1.02x off.  The historical Eta2-to-MFREE portfolio row (9/10,
median 3.84 s, mean 6.59 s, p90 18.1 s, cross-machine wall caveat) is an
external reference and is never silently treated as a same-host arm.

## A4

Use the already validated wave-4 acceptance overlay with `rho_min=1e-3` and a
same-derived-binary off arm.  Run fresh N=10 cohorts on Final3068 and Venice52,
alternating order.  Do not pool these rows with wave 4's N=5 screen.  Retain
the existing nine-cell N=3 result (geometric-mean ratio 0.9923 with every range
overlapping) as its separate panel cohort.  Adoption requires no tail hit-rate
loss and no resolved endpoint regression.

