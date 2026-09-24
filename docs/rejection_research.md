# Why a multi-shift BA menu can reject more often

Research and bounded investigation, 2026-09-07. Broad novelty coordinators are
paused in `/workspace/prism-rejection/paused-processes.json`; the in-flight
Venice-1672 run was allowed to finish. Existing frozen binaries and results are
preserved. No production default is changed.

## What the literature actually guarantees

[Jegerlehner (1996)](https://arxiv.org/abs/hep-lat/9612014) derives simultaneous
Krylov solves for `(A + sigma I)x = b`. The shared operator and RHS are crucial;
the saving concerns matrix-vector products, not nonlinear acceptance or the
number of outer iterations.

[Lin, O'Malley and Vesselinov (2016), sections 4.1–4.2](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/2016WR019028)
reuse a Krylov basis across damping parameters and select the candidate with
the smallest nonlinear objective. This supports investigating our implementation
rather than dismissing multiple dampings. Their full-parameter regularization
is materially different from our camera-only shift at fixed point damping.
It also means that basis reuse plus best-candidate selection is prior art.

[Ceres' nonlinear solver documentation](https://ceres-solver.readthedocs.io/latest/nnls_solving.html)
formulates LM using a full-state regularized model and an actual/predicted
reduction ratio. Its Dogleg discussion explains how shrinking a trust region
can reuse directions without another linear solve. This motivates full-step
safeguards in PRISM, but does not establish convergence of our bounded fallback.

## The correct version of the user's intuition

At the **same state, point damping, camera scaling, and linear accuracy**, if
a multi-shift candidate set includes the standalone single-shift candidate,
then its best nonlinear cost cannot be worse. A rejection despite an improving
included candidate would be an implementation error.

Our independent full runs do not satisfy those premises. Selecting a different
candidate changes the next state, Jacobian, point damping, stopping criterion,
and lambda history. A better immediate decrease can lead to more later retries.
Moreover, the implementation does not always include the standalone candidate:

* The seed is lambda/100 for five shifts, versus lambda for a single shift.
  Their forcing-test stopping depths differ.
* The model-flatness gate scores only the lowest shift. It can reject without
  evaluating the center or other shifts. Similar model decreases do not prove
  identical nonlinear costs.
* After at least one scheduled checkpoint, an ordinary CG stop between
  checkpoints does not score the terminal iterate unless candidate pruning is
  enabled. Useful work can be computed and then discarded.
* Negative curvature in the least-damped seed truncates the entire sweep.
  Larger shifts can still have positive directional curvature. This requires
  a measured frequency before attributing a rejection storm to it.
* The shifted recurrence divides by zeta without a zero guard. The earlier
  2048-depth audit exposed NaNs; occurrence under production's 128-depth cap
  must be measured separately, not assumed.

## Why increasing camera lambda may never rescue the full step

Write the linearized Hessian as `[U W; W^T V]`, with gradient `[gc; gp]`,
and `Vtau = V + tau Dp`. With fixed tau, PRISM solves the congruently scaled
version of

```
(S(tau) + lambda Dc) dc = -(gc - W Vtau^-1 gp)
S(tau) = U - W Vtau^-1 W^T
dp = -Vtau^-1 (gp + W^T dc)
```

As lambda grows, `dc -> 0`, but **`dp -> -Vtau^-1 gp`, generally not zero**.
Five camera lambdas can therefore share the same harmful point relaxation.
A rejection ladder also changes tau; the eventually accepted attempt need not
have succeeded because its camera lambda increased.

Giving each candidate a different point tau changes both `S(tau)` and its RHS.
These are generally no longer scalar shifts of one matrix. Applying the current
multi-shift recurrence to them unchanged would be mathematically wrong.

## Other controller issues to distinguish

The default rho denominator uses a camera-space prediction. The optional
`OCA_RHO_PT` adds the eliminated point constant, but the subsequent alpha search
scales camera and point blocks independently. A generally correct trust-region
prediction for the selected full step is

`pred(d) = -g^T d - 0.5 ||J d||^2`.

A camera-only prediction updated using camera alpha does not represent every
such step. The cold-phase forced lambda decay and rejection-streak unwind also
mean this is not textbook Nielsen LM. These are plausible controller causes,
not yet isolated experimental findings.

The existing backtracking safeguard permanently switches off at the first
nominal convergence after a rescue, to prevent tiny steps from causing false
convergence. Rejections before and after that switch must be counted separately.
Removing the safeguard is intentional; it may also explain why late retry counts
remain high. Any rearming experiment must preserve a credible stopping check.

## Lightweight experiment

First screen: single and five shifts with the same existing backtracking on
Ladybug-49, Dubrovnik-88, Venice-52, Trafalgar-126 (400-outer cap, one logged
run each). Add Ladybug-1197 and Dubrovnik-173 as known retry cases; each has fewer
than 635,000 observations and takes seconds to tens of seconds in prior runs.
Logged runs diagnose causes; they are excluded from timing comparisons.

Candidate-coverage experiment: same newly built binary, three arms (single,
five, five+coverage), two cyclic-order repeats on Dubrovnik-173, Ladybug-1197,
Venice-52 and Trafalgar-126. Same 600-outer budget, 180-second per-run timeout,
full fp64 objective, no observation subsampling. This is exploratory evidence,
not a statistical or publication-grade consensus claim. Each arm keeps the
existing eight-probe backtracking safeguard.

`OCA_MENU_COVERAGE=1` makes three candidate-set changes, without changing the
lambda update or point damping:

1. Score the central iterate at its first shifted-residual forcing threshold.
2. Score computed terminal iterates between scheduled checkpoints.
3. Expand a model-flat shortcut if its scored candidate did not improve cost.

This tests candidate omission as a combined mechanism. Component ablation is
needed if it helps. Two repeats expose obvious instability cheaply; they cannot
establish tail robustness. Compare rejects, rescues, matvecs, all cost evaluations,
final cost, and time to 1%, 3%, 5% above the best observed endpoint per scene.
Do not reject a method merely because it exchanges a small cost increase for
substantial time savings. Do not call fewer rebuilds a win if extra scoring or
slower convergence consumes the saving.

## Second bounded experiment: rearm only after a disproved stop

The logged Ladybug-1197 run had 294 rejected attempts, 286 after fallback
shutdown; Dubrovnik-173 had 51, all after shutdown. Neither run had nonfinite
candidate costs or curvature-truncated rejected attempts. Thus the long-depth
recurrence failure from the earlier audit does not explain these particular
small-scene traces. A flat-menu gate fired on 282 of Ladybug's rejects; 211 did
not score the center. This is an association, not proof that the center would win.

`OCA_BACKTRACK_REARM=1` separately tests re-enabling backtracking when an
**original-policy accepted step during confirmation** decreases cost by more
than `max(1e-4, 10*ftol)`. The threshold separates meaningful renewed progress
from the flatness tolerance. Every later proposed stop still requires original
policy confirmation; rescued steps cannot themselves trigger rearming. This is
a heuristic safeguard, not a convergence theorem. Default behavior is unchanged.

Two repeats of multi versus multi+rearm on Ladybug-1197 and Dubrovnik-173 use
a second frozen binary, without candidate coverage. Compare within each cohort;
do not silently mix controls between executables. The entire timed investigation
is 24 coverage runs plus 8 rearm runs, not a new broad baseline sweep.

## Same-state evidence

At one saved Ladybug-1197 state (cost 366,888.81141), point tau=1e-7 and camera
center=1e-7 give shifts 1e-9 through 1e-5. With the model gate disabled, even the
best scored candidate costs about 1.856 billion. Raising the camera center to
1e-4 still fails. Holding the same tau but moving the center to 0.1 gives a
winning shift of 10 and cost 366,860.09634. Alternatively, raising tau to 1e-4
allows all three tested camera centers to accept, ending near 366,874.56.

This shows **both routes can rescue this state**. It would be incorrect to say
camera damping cannot help this particular state, or that every high-lambda
candidate is necessarily harmful. The point-step limit explains why success
is not guaranteed by camera damping alone; the measured fork establishes that
the currently explored camera range can also be far too low.

The diagnostic trace repeatedly returns the camera center to 1e-7 after a
contested accept at tau=1e-4, then pays another three-rejection ladder. The code
intentionally unwinds camera escalation because tau changed too. This discards
useful information about the **joint** damping state, not merely the last
lambda index. A promising next design would remember the successful lambda/tau
pair and expand the camera range at fixed tau before deciding to rebuild points.
A saved Krylov basis could support additional shifts without repeating its
matvecs (as in the cited recycling literature). That is a proposed follow-up,
not an implemented or novel result of this study.

## Reproduction

```sh
cmake -S gpu -B /workspace/prism-rejection/build -DCMAKE_BUILD_TYPE=Release
cmake --build /workspace/prism-rejection/build --target oca_cuda -j 4
python bench/rejection_experiment.py --study coverage \
  --binary /workspace/prism-rejection/coverage-frozen \
  --out /workspace/prism-rejection/coverage-pilot \
  --scenes dubrovnik-173 ladybug-1197 venice-52 trafalgar-126 \
  --reps 2 --max-iter 600 --timeout 180
python bench/rejection_experiment.py --study rearm \
  --binary /workspace/prism-rejection/rearm-frozen \
  --out /workspace/prism-rejection/rearm-pilot \
  --scenes ladybug-1197 dubrovnik-173 --reps 2 --max-iter 600 --timeout 180
python bench/check_rejection_math.py
python bench/summarize_rejection_study.py --output docs/rejection_results.md
```

Retained artifacts include both frozen binaries and CUDA sources, input/binary
hashes in manifests, raw stdout/stderr and CSVs, extra diagnostic JSONL, the saved
BAL state and six damping forks. New reruns should use a new output directory;
the harness retains completed/failed measurements rather than overwriting them.

## Corrected-coverage recheck

Review found duplicate scoring in the first coverage prototype when CG stopped
before its first scheduled checkpoint: the legacy early-stop branch had already
scored that iterate, and the new terminal branch scored it again. The central
forcing-test candidate could also duplicate a just-scored scheduled candidate.
The corrected code records which depth each shift was scored at, avoids the
latter duplicate, and marks the already-scored early terminal as complete.
It also records the actual CG depth in that branch when coverage is enabled.

The original 24 runs are retained as `coverage-pilot`; do not describe their
timings as measurements of the corrected implementation. A bounded recheck
(`coverage-v2-pilot`) runs only multi versus corrected coverage, one repeat per
arm on the same four scenes: eight additional timed runs. This raises the total
timed budget to 40. The recheck can catch gross regressions; one repeat cannot
resolve performance variance. No combined coverage+rearm performance claim is
made. A joint memory-safety smoke test is separate from the timed ablations.

Additional same-state probes show the standalone low-lambda solve and completed
low-lambda menu both reject; standalone lambda=10 accepts (cost 366,859.78045).
Thus there is no evidence from this snapshot that the multi-shift recurrence is
fundamentally inferior to single CG. The available damping range is the decisive
local difference. Small differences between accepted standalone/shifted costs
also reflect their different stopping depths and floating-point trajectories.
