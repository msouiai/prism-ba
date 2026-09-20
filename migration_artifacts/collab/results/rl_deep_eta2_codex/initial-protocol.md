# Deep-CG learned damping against sustained eta2

Round 6, registered before fresh measurements. Muell-gba146 is excluded from
training, checkpoint selection, fitting, normalization and tuning. It has been
observed in earlier research and is a held-out transfer scene for this retry,
not a pristine unseen recording. Final1936 and Trafalgar126 are also excluded
from training. No target or policy changes after transfer outcomes.

All arms use initial lambda 0.1 and sustained eta multiplier 2 (cap 0.5), the
current champion. An isolated derivative of the frozen actor binary only adds
OCA_RLA_FIXED_ETA to the replay configuration fingerprint. No solver arithmetic
changes. Parent/new/zero-policy compatibility, exact checkpoint feature restore,
continued-trajectory parity and eta-mismatch rejection must pass before labels.

Training scenes: shallow Ladybug49, Dubrovnik88, Venice52, at accepted boundaries
1,3,5,7; deep sources Ladybug598 and Dubrovnik356, early boundaries 1,3 plus up
to four actual deep-CG checkpoints each. Scout each deep source for 100 outers,
10 native seconds. Candidate boundaries must be accepted, followed by a decision,
have previous CG >=64/128, be >3 and separated by >=3 outers. Try candidates in
increasing outer order, at most eight per scene. Capture and verify saved feature
depth >=0.5 before any action labels; record failed candidates without resampling
from performance results. Require at least two verified deep states per deep scene
or report an incomplete coverage test. Maximum 24 training states.

Each checkpoint branches into actions -1,0,+1, N3, rotating order. Actions multiply
the baseline proposed next lambda by 0.1,1,10 with unchanged numerical bounds.
Continue up to 32 outers (previous pilots used 4 and 12), cap 6 native seconds.
Training return: causal accepted-cost AUC normalized by checkpoint cost and the
shortest actual elapsed continuation duration among its nine branches. Score
4-outer prefixes of the same traces as a horizon diagnostic. Report actual lengths
and horizons, including early stalls. Single intervention followed by champion
continuation is deliberately retained to test the original learned-policy recipe;
it does not eliminate the mismatch with repeated deployment interventions.

Fit the same fixed ridge model: 64 history features, clipped standardized inputs,
ridge 10 and intercept penalty 0.01. No hyperparameter search. Fit an additional
shallow-only 32-outer model from the three shallow scenes, with its own training-only
normalization, to isolate the added deep-source data. The full model and shallow
control are both evaluated regardless of offline scores. No Muell labels enter.

Leave one whole family out: omit every Ladybug or Dubrovnik scene, respectively,
not just an individual size. Venice fold omits Venice52. Fit/normalization use only
the remaining families. Report offline held-out AUC advantages and run each fold's
policy on its family probe: Ladybug598 target 182215.47143052; Dubrovnik356 target
731369.19169166; Venice89 target 306319.16867216, all cap 4s. These are existing
1%-tolerant training-reference targets. Probe arms: champion, fold policy,
opening-decay; N3 each. These probes cannot select or modify the transfer policy.

Transfer arms: champion, full learned, shallow-only learned, opening-decay. The
opening comparator multiplies proposed next lambda by 0.1 at boundaries 1 and 2
only, then uses champion control. N3 per arm/scene, rotating serialized arm order.
Fixed targets/caps: Trafalgar126 105579.58394455544 / 4s;
Final1936 5125687.352261469 / 8s; Muell-gba146 1946488.746262194 / 12s.
600 outer cap. Logging disabled for headline timing. Every endpoint independently
audited against original FP64 observations, relative discrepancy <1e-7. Hits require
actual native TARGET <=cap and audited cost <=target; no interpolated crossings.

Promotion requires all full-policy transfer repeats hitting, median scene speedup
>=1.10 versus sustained eta2, and no scene >5% slower. Also report geometric ratio,
Muell result and opening-decay comparison; learning must outperform the simple
schedule to justify its complexity. Failed family checks preclude a general claim.
Sub-percent endpoint differences below target are not penalized. Report misses
and gaps rather than fabricated finite speedups.

Final1936 mechanism diagnostic: separately log up to 32 outers for champion, new
full learned policy and the frozen earlier extended policy (historical pathology
control), with the same target/cap. Exclude diagnostics from timing medians. Report
every baseline/used lambda and explicitly count 0.025 -> 0.25 corrections and any
repeated positive-action streak. No rescue tuning after observing pathology.

Serial local GPU lock /tmp/prism_gpu.lock, host2237c6528e79 RTX2000 Ada. Native
study ceiling 2000s including smoke/scouts/captures/branches/diagnostics; bounded
by phase caps. No Caspar or largest-scene extension. Preserve binary/source hashes,
policy hashes before transfer, all runs and failures. Compact durable evidence in
/workspace, raw evidence /tmp/prism-rl-deep-eta2. No production defaults changed.

A negative result supports a conclusion about this specified controller, features,
return and research panel. It does not establish that every learned damping policy
or every state-dependent controller must lose to constants.
