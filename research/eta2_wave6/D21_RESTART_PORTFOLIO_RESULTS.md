# D21 result: arithmetic restart portfolio reaches 37/38, but misses its median-time gate

## Verdict

The three-attempt B6v7 cascade crosses the preregistered high-reliability SPRT
boundary with **37/38 target hits (97.37%)**.  It is the best observed
Final3068 reliability in a fresh cohort on this machine.  It is not promoted
as the categorical campaign's operational winner because its median charged
native time is 4.263 seconds, above the registered 3.923-second ceiling.

The frozen Eta2 champion remains the scientific winner, B6v7 remains the
single-run systems winner, and the historical Eta2-to-MFREE cascade retains
the registered portfolio-winner label.  D21 is a useful Pareto alternative:
its mean and p90 are better than the historical cascade while its median is
about 11% slower.

## Fresh sequential result

| quantity | D21 result |
|---|---:|
| Episodes | 38 |
| Target hits | 37 (97.37%) |
| First-attempt hits | 24/38 |
| Second-attempt conditional hits | 8/14 |
| Third-attempt conditional hits | 5/6 |
| Median attempts | 1 |
| Mean attempts | 1.526 |
| Median charged native time | 4.263 s |
| Mean charged native time | 5.932 s |
| p90 charged native time | 10.039 s |
| SPRT log likelihood / upper boundary | 3.0167 / 2.9444 |

The beta-binomial descriptive posterior with a uniform prior is Beta(38,2):
its equal-tail 95% interval is 86.5--99.4%, and its posterior probability of
reliability above 90% is 91.2%.  The SPRT is the registered decision; the
posterior is reported only to show the finite-sample uncertainty that remains
behind a 37/38 point estimate.

The internal first attempts hit 24/38 and have conditional median crossing
time 3.2975 seconds.  Thus the reliability gain is large and causal: thirteen
of fourteen first-attempt misses were rescued by an identical fresh solver
launch.  The median episode becomes slower because 13/37 successful episodes
pay at least one full failed launch before crossing.

## Comparison with the existing portfolio

The collaborator-reported Eta2-to-MFREE cascade is 9/10 with median 3.84 s,
mean 6.59 s and p90 18.1 s.  D21 has higher observed reliability and improves
mean by 10.0% and p90 by 44.5%, but its median is 11.0% slower.  Those rows are
not a same-host randomized comparison: the MFREE composition used another
similar GPU and only ten assignments.  They support a tradeoff statement, not
solver superiority.

## Mechanism and scope

The fresh B6v7 process does not repeat a miss deterministically.  The second
launch succeeds in 8/14 cases and the third in 5/6, consistent with the banked
lag-one hit correlation of 0.022.  Floating-point reduction order selects a
new pseudo-orbit of the numerically sensitive outer map.  Treating those
pseudo-orbits as a portfolio turns run-to-run variation into a reliability
resource.

This is standard restart/portfolio logic and adds no novelty to Eta2's inner
algorithm.  It also spends up to three complete solves and does not improve a
single trajectory's convergence.  The result is operationally useful where
tail reliability matters more than median latency; it does not satisfy this
campaign's registered balanced promotion rule.  No retry-count tuning follows.

## Evidence

- `D21_RESTART_PORTFOLIO_PROTOCOL.md`
- `d21-development.json`
- `d21-registration.json`
- `d21-results.json`, `d21-summary.json`
- runner: `d21_restart_portfolio/run.py`

