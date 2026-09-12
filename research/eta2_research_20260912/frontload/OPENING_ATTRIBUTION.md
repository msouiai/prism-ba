# Venice opening trace audit: one proposed attribution arm

The next parsimonious test is **disable radial camera clipping for the first three accepted outers only, retaining the production operator, ordinary Eta2 forcing, strict radius acceptance and all existing safeguards**. After three accepts, restore ordinary clipping and carry the live controller history forward. This is a proposed global rule, not an implemented or tested new arm.

The audit reads all five already completed Venice off/on pairs. It launches no solver. `audit_opening.py` checks alignment of the radius/model/attempt traces, records the first three accepts including retries, and hashes the input logs in `results/opening_attribution.json`. The evaluated binary remains the frozen frontload binary `24e08d038c4232b6d6a9278e6fa34242b9e9ac5488786bdcc83ecbce2c18b9f9`, derived reversibly from champion source `22c18359a526526ae0a5b5109187878ab1cef33b453f6bbddc2aa92597a607d8`.

All five repeats show the same opening decisions and work counts; the costs and radii below are their medians.

| After accepted step | Frozen off cost | Combined frontload cost |
|---|---:|---:|
| Initial | 11,152,062.773 | 11,152,062.773 |
| 1 | 2,274,695.154 | 2,104,980.250 |
| 2 | 1,506,203.560 | 1,506,370.325 |
| 3 | 1,127,133.181 | 1,393,631.425 |

The frontloaded first step is better, but this lead disappears by step two: its cost is then 0.0111% higher. The major discrete branch occurs at the third proposal. The off raw camera norm is 9,578.85 against radius 6,450.71; clipping produces an accepted proposal with rho 0.99788. The combined arm's raw norm is 9,603.64 against radius 6,208.49. Its unclipped proposal has positive prediction 472,495.57 and rho 0.99731, yet it fails the strict radius check. The native acceptance code confirms this is a radius rejection, not a failed nonlinear model or curvature cutoff.

That rejection shrinks the combined arm's radius by four and multiplies lambda by sixteen. Its retry at lambda 0.04 takes a smaller, accurate step, leaving the following handover:

| Opening/handover measure | Off | Combined frontload |
|---|---:|---:|
| Opening attempts | 3 | 4 |
| Opening PCG iterations | 13 | 23 |
| Opening Schur products | 16 | 27 |
| Opening attempt seconds, median | 0.03922 | 0.11501 |
| Opening attempt seconds, range | 0.03902–0.04312 | 0.11473–0.12428 |
| Handover lambda | 0.000625 | 0.004 |
| Handover radius | 12,901.41 | 1,552.12 |
| Registered Venice target hits | 0/5 | 5/5 |

The successful combined arm enters ordinary Eta2 with **6.4 times larger damping and 8.31 times smaller radius**, while its cost is **23.64% higher** after three accepts. Thus the observed benefit is not simply more cost reduction purchased in the opening. The traces support testing whether the radius rejection and resulting conservative trajectory are the important intervention.

This does not prove that unclipping causes the final target hits. Tighter forcing and coherent rows already alter the first step, state, radius bootstrap and residual history, and nearly equal scalar costs do not imply equal states. In particular, the comparison cannot isolate a precision effect. The merit of the proposed arm is that the off raw third step already violates its radius by a wide margin, so it tests the visible discrete branch without the coherent-row allocation/factorization overhead or the forced deeper CG work. If it fails, the remaining alternatives are changed directions or an interaction; no scene-specific tuning follows from this audit.

The mechanism should be described as **rejecting oversized opening steps instead of projecting them**, not as accepting larger steps. Strict radius acceptance remains active. It may increase opening rejects and harm other scenes; the completed combined grid already has such regressions, including Final3068. Any confirmation must use one frozen rule everywhere and retain both signs of the common-panel and tail results. This report makes no new global promotion claim and no population-reliability claim from N5.

The opening timings above use the existing host attempt clock with no added synchronization. The report leaves the parent harness's registered target timing and native solve timing definitions unchanged; it does not substitute endpoint wall for crossing time.
