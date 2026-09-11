# T5: limited recovery benefit, false-bridge counterexample

The information schedule reaches the target on 10/10 mixed-bridge held-out
scenes versus 9/10 for ordinary and residual-based continuation, N=3. On the
nine common hits it is 0.942x ordinary and 0.961x residual-schedule speed. All
three schedules have zero geometric failures on correct and mixed cases.
On correct bridges the information signal does not change the schedule and
only adds overhead (0.945x ordinary speed).

The all-corrupted counterexample fails the intended interpretation. The
information controller delays tightening for a median 10.5 attempts, takes
0.442x ordinary time-to-target speed, and retains a median 7.5 false inliers
versus 6.5. Median final robust cost is 125.07 versus 114.14. Both have geometric
failures on 9/10 cases: low robust cost cannot recover absent correct bridge
information. On disconnected cases, all final states fail relative geometry
despite objective target hits; the diagnostic correctly reports no information.

Every run reaches the prescribed final sigma=1 objective and receives at least
36 terminal attempts. No observations are removed. Timing includes spectral
monitoring, which consumes about 1.3–5.0% of total information-arm runtime.
The failed speed/false-inlier gate closes T5 without promotion. The extra mixed
recovery is retained as a qualified result; it is not hidden by common-hit
timing statistics. Individual failures and all trajectories are in `t5_*` JSON.

## Prior art and limitation

Adaptive graduated robust estimation is established. ASKER introduces a scale
per residual, treats return to unit scale as a constraint, and uses cooperative
and restoration filter steps. Our experiment uses a simpler common scale
schedule and asks whether undamped geometric-information loss adds value.
It does not implement ASKER or inherit its convergence result.
[Graduated Filter Method, sections 4–5](https://arxiv.org/html/2003.09080).

A recent triangulation-free BA preprint also anneals a robust kernel, with
per-observation depth variables, a structureless correspondence objective and
pose priors. Its fixed three-stage arctan schedule differs from both our
Cauchy loss and original shared-point pixel problem. Thus annealing itself is
not new, and the reported regimes are not interchangeable comparisons.
[Triangulation-Free BA, sections 3.3–3.5](https://arxiv.org/html/2608.21008).

Reproduce `check_robust.py`, `run_t5.py --split development`, then
`run_t5.py --split held_out`. `T5_PROTOCOL.md` predates the comparisons. The
remaining question is how to distinguish weak **correct** constraints from
coherent false ones without truth labels; eigenvalues alone cannot do that.
