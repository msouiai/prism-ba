# D4 result: monotone soft acceptance is not a production candidate

## Verdict

The preregistered deterministic paired experiment stopped at its 60-pair cap
without crossing either sequential boundary.  The soft arm hit the registered
Final3068 target in 41/60 pairs, versus 38/60 for the deterministic control,
but the discordant outcomes were only 12 soft-only versus 9 control-only.  The
registered conditional-benefit estimate is therefore 12/21 = 57.1%, with an
exact 95% interval of 34.0%--78.2%.  This does not establish the registered
70% benefit (SPRT log likelihood ratio -0.560; boundaries -2.251 and 2.890).

The production gate fails.  D4 stops here without a Venice or practical-panel
stage and without tuning the scaling law.  The frozen scientific champion and
the wave-5 systems candidate are unchanged.

## Registered design

The test used 60 previously unseen, deterministic Final3068 perturbations at
field scale `1e-10`, seeds 650000--650059.  Both arms received the same input
bytes in each pair and arm order alternated.  The fixed target was
`1744796.9841897595`; each run had 600 outers and 45 native seconds available.

The active rule applies only to a full proposal that decreases the plain-L2
cost but has `0 < rho <= 0.1`.  It replaces `d` by
`alpha*d`, `alpha=rho/0.1`, recomputes both the full plain-L2 cost and the
quadratic prediction, and commits only a finite, predicted, true-cost descent.
The recomputed rho drives the unchanged Eta2 controller.  Every other path is
unchanged.

Promotion required all of:

1. the upper sequential boundary for a 70% conditional win probability over
   the 50% null;
2. at least one real soft commit; and
3. median soft/control target time no greater than 1.20 on double hits.

## Results

| Quantity | Control | Soft acceptance |
|---|---:|---:|
| Target hits | 38/60 | 41/60 |
| Median endpoint cost | 1,743,793.57 | 1,743,090.42 |
| Median native time | 7.008 s | 7.196 s |
| Median outers | 60.5 | 63.5 |
| Median rejects | 6 | 5 |
| Median Schur products | 307.5 | 289 |

Paired outcomes were 29 double hits, 10 double misses, 12 soft-only hits, and
9 control-only hits.  The one-sided exact paired test against equal odds is
not significant (`p=0.332`).  On the 29 double hits, the median target-time
ratio was 1.0769, with range 0.4717--2.3145.  The paired median endpoint change
was +0.0059%, far below the 0.15% resolution rule and with a range dominated by
basin changes (-10.41% to +12.74%).

The arm reduced median rejects by one and median Schur products by 6.0%, but
used 5.0% more outers and 2.7% more native wall overall.  Thus fewer rejects
did not mean faster convergence.

## Mechanism audit

The active rule fired 213 times and committed 206 times.  Median `alpha` was
0.4316.  All 206 committed scaled proposals had lower true cost than the
original full proposal, so the implementation did what its local argument
predicted.  The seven noncommits were correctly rejected after recomputation.
Every logged alpha and recomputed rho passed the arithmetic identity checks;
all endpoint rescoring errors were at most `1.40e-10` relative.

Only two soft runs had no activation.  In both pairs the derived binary and
the control ended with byte-identical states and identical costs.  Two
separate flag-off compatibility runs also matched the control cost traces and
endpoint hashes exactly.  The outcome difference therefore comes from the
registered intervention rather than build drift.

The important negative is causal: turning a low-rho descent into an even
better immediate descent often avoids the rejection that would have changed
damping and radius.  The resulting trajectory can spend more accepted outers
in the same basin.  Conversely, the same smoothing rescues some control
misses.  The two effects are comparable, which explains the 12-versus-9
discordance and broad timing range.  Continuity of the outer map at the rho
threshold is not sufficient for reliable Final3068 convergence.

## Scope

This is a controlled perturbation-shell experiment, not an estimate of
ordinary deployment randomness.  The sequential lower boundary was not
crossed, so the result is **unresolved for a small benefit**, not evidence that
soft acceptance is intrinsically harmful.  It is sufficient to reject D4 as a
production change under the registered 70% reliability target and overhead
gate.

Machine-readable evidence is in `d4-results.json` and `d4-summary.json`; the
immutable setup is in `D4_PROTOCOL.md`, `d4-registration.json`, and
`d4-build-manifest.json`.
