# T2: iteration savings did not repay curved-step work

All five arms reach the registered targets on all 20 held-out cases, N=3.
Numbers below are medians of per-seed timing ratios after taking N=3 medians;
greater than one is faster than ordinary CPU LM.

| Arm | Depth speed | Rotation speed | Overall speed | Overall accepted iterations |
|---|---:|---:|---:|---:|
| Ordinary LM | 1.000 | 1.000 | 1.000 | 5 |
| LM + geodesic | 0.806 | 0.635 | 0.651 | 5 |
| Extra OCA recursion | 0.938 | 1.019 | 1.003 | 4 |
| Extra lower lambda | 0.850 | 1.149 | 0.928 | 4 |
| Defect-based hybrid | 0.889 | 0.975 | 0.970 | 4 |

Depth geodesic updates reduce median accepted iterations from 6.5 to 5 and
rejected attempts from 1 to 0. Nevertheless, derivative, RHS, trial and scoring
work outweigh that saving. The hybrid is faster than always computing a
geodesic correction but does not beat the simpler fresh-linearization LM
baseline, let alone the registered 1.10x gate. T2 is unsupported in this screen.

These are tiny CPU runs (typically 6–11 ms), useful for mechanisms, not GPU
speed predictions. Target quality is deliberately frozen rather than each
solver's final stop. At target crossing, point NRMSE exceeds 0.15 on 2/20
ordinary/hybrid cases, 4/20 geodesic/OCA cases, and 1/20 lower-lambda cases.
This shows that a cost target alone does not certify geometry; these are
target-crossing snapshots, not claims about fully refined endpoints. No state
with a nonfinite residual or nonnegative observed depth was accepted.

The analytic second directional derivative includes rotation–point cross terms,
perspective division, radial distortion and free intrinsic terms in the BAL
chart. Across ten tests its worst best-step finite-difference error is 5.18e-8.
The correction and OCA action reuse the same fixed numerical factors; a new
lambda creates new factors. The ordinary arm relinearizes after every accepted
step and provides the alternative use of the same overall time budget. The
full closed-loop comparison supersedes a separate snapshot-only timing contest;
candidate-level records remain available, but no matched-deadline snapshot
oracle was claimed.

## Prior art and exact difference

The construction is established geodesic acceleration: solve the LM system
again with the residual second derivative, and bound the correction relative
to the velocity. We use the paper's practical 0.75 bound in a fixed state-unit
metric, retain the ordinary candidate, and evaluate two safeguarded curve
parameters on the complete pixel objective. This is an implementation variant,
not a novel geometric method.
[Transtrum and Sethna, equations 9–15](https://arxiv.org/html/1207.4999).

RNC-LM already builds higher-order curve coefficients by repeated solves with
the same LM matrix; Algorithm 1 computes each RHS using derivatives of the
truncated geodesic residual. Our test only implements order two and adds a
BA defect-versus-filter allocation rule. Its failed timing gate provides no
basis for a novelty claim.
[Liu and Zhang, Algorithm 1 and section II](https://arxiv.org/html/2607.07623).

Reproduce with `python3 check_curvature.py`, then `python3 run_t2.py --split
development` and `python3 run_t2.py --split held_out`. The runner fixes BLAS
threads to one. `T2_PROTOCOL.md` predates comparisons; `t2_*` JSON files include
all costs, target hits, candidates, work counters, timing breakdowns and curves.
Eta2 remains the GPU incumbent. Next: T3 point relaxation before ranking.
