# O5: one robust-to-L2 opening, registered before building or scoring

The frozen champion and original observations remain untouched. The sole arm
uses Cauchy cost `0.5*a2*log1p(||r||^2/a2)` for an opening, then plain L2.
At setup `a2_base=max(4*median_initial(||r||^2),1e-12)`. Four stages use
`a2/a2_base = 1,4,16,64`, two accepted steps each, followed by L2. We count the
setup pass, median, all stages and handover in native time. No observations are
dropped. This is reverse robust continuation, not GNC toward a robust target
and not a globally convergent estimator.

Each surrogate stage has an 18-attempt cap, including retries. A stage cap or
stop request skips remaining robust stages to L2 at the current state, without
rollback. Controller lambda, radius, numeric floor and cumulative work persist.
On any objective transition, rebuild assembly/factors/RHS and reset the
objective-dependent forcing/flatness/confirmation history. Target stopping is
enabled only in L2. Full original L2 is logged separately throughout; the scored
CSV omits intermediate robust-stage rows so they cannot become target hits.

Consistency requirement: assembly/RHS/Schur fragments and the full-step GN
prediction use the same current Cauchy IRLS weight; candidate cost and per-track
keep/move rescue use the same actual Cauchy cost. In L2, all original formulas
are retained. A model-only weighting modification is not this experiment.

First: finite-difference robust gradient and weighted prediction checks, native
off-vs-frozen compatibility N=3, Cauchy-stage and final-L2 score checks, and a
memory-error smoke. Then fresh off vs O5 at N=5 on both registered tails.
Promote to the nine-cell N=3 panel only with an observed tail hit-count gain
and no loss on the other tail. If neither tail improves, stop O5. A small
N=5 hit-count difference is a screening signal, not an established reliability
advantage. No selection of per-scene scales or schedules after observing scores.
