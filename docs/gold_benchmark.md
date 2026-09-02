# Gold benchmark: Prism vs Caspar, one RTX 4090, identical objective

2026-09-02. Caspar's six BAL datasets (arXiv:2605.30583 Fig. 3), both solvers
measured on the same RTX 4090, identical SIMPLE_RADIAL fixed-pp objective
(Prism: `--dof9 --zero_k2`; Caspar: standalone driver against the vendored
generated solver, validated to reproduce the COLMAP-driven behaviour to 5
digits, COLMAP-default config). N=3 per arm, medians. See fig3_gold.png.

| dataset | Caspar (wall) | best Prism | vs Caspar | Prism->CaspF | Casp->Prism |
|---|---|---|---|---|---|
| dubrovnik-356 | 1.213e6 (0.9s) | sched 7.38e5 | -39.2% | 0.30s (3.1x) | never |
| ladybug-1723 | 4.482e5 (1.3s) | block 4.61e5 | +3.0% | never | 0.13s |
| trafalgar-257 | 1.184e5 (0.9s) | sched 1.157e5 | -2.2% | 0.57s (1.6x) | never |
| venice-1778 | 2.058e6 (10.6s) | sched 2.011e6 | -2.3% | 7.55s (1.4x) | never |
| final-4585 | 1.211e7 (5.8s) | sched 6.900e6 | -43.0% | 15.75s (0.4x) | never |
| final-13682 | 2.406e7 (54.9s) | block 2.377e7 | -1.2% | 125.4s (0.4x) | never |

Verdict: quality 5/6 (two by ~40%); crossings won on small/mid sets, lost
~2.5x on the two Finals. Caspar reaches a Prism final on 1 of 6.


## Iteration-cost diagnosis (overnight 2026-09-02)

Cross-GPU per-unit profiling (RTX 2000 Ada vs RTX 4090, identical configs):
no hardware pathology -- krylov/matvec and pointfactor/outer scale 2.3-5.2x
(~bandwidth ratio); candidate scoring subscales (1.7x, latency-floored).
The Finals crossing gap is the REJECT STORM: final-4585 runs ~2,650 outers for
~313 accepts (88% rejects) on both GPUs, each reject re-paying the per-outer
fixed phases. `OCA_TAU_PT=1e-4` collapses it on 4585-block (324s -> 133s at
equal quality) but anti-composes with the scheduler and trades quality on
13682 -- a per-problem lever. Adaptive tau was subsequently REFUTED twice: the existing `tau_persist`
(V2) ladder collapses the storm but stalls at 1.15e7 -- a no-ftol control
(7,007 outers, 99% rejects, 620s, no further descent) proves the storm's
escalation cycles ARE the descent mechanism on this problem. Best known:
fixed OCA_TAU_PT=1e-4 (same depth as the storm at 2.4x less wall). A V3
(adaptive ladder FLOOR, preserving low-tau re-probes) is designed but ungated.
