# Ordered bundle-adjustment geometry agenda

The supplied [brief](brief.tex) defines eight hypotheses. Execute them in order,
honoring each prerequisite and stop rule. Negative results are valid outcomes;
an untested idea must remain pending. The production incumbent is frozen Eta2
(`research/eta2_champion/champion.json`, original binary SHA256
`1e3d2cf22a8a43075114e0ca2024923dad330461e35d0074938d0412cd77ecc0`).
The freshly fetched master is `8c56130`; no later promoted solver supersedes
the incumbent in the available repository. Original implementations and prior
experiments remain intact. Generated implementations live in this directory's
ignored build folder, on `research/geometry-agenda`.

| Order | Hypothesis | Status | Decisive gate |
|---|---|---|---|
| T1 | Projection-aware model-error control | Closed: predictive gate failed; retain diagnostics | See T1_RESULTS.md. |
| T2 | Curved updates versus filtering depth | Closed: timing gate failed | See T2_RESULTS.md. |
| T3 | Nonlinear point relaxation before ranking | Closed: rankings change, but post-only is cheaper | See T3_RESULTS.md. |
| T4 | Nonlinear collective corrections | Closed: controlled gain, sampled-real transfer failed | See T4_RESULTS.md. |
| T5 | Observability-aware robust continuation | Closed: false-bridge and timing gates failed | See T5_RESULTS.md. |
| T6 | Temporary depth-tube smoothing | Closed: cost outweighs limited geometric benefit | See T6_RESULTS.md. |
| T7 | Spectral interpretation of OCA search | Closed: quality gate failed; simple menu wins | See T7_RESULTS.md. |
| T8 | Allocation among useful computations | Closed: local prediction does not transfer to faster solves | See T8_RESULTS.md; conditional RL training not justified. |

## Shared contract

Reproduce the frozen GPU incumbent before intervening. Distinguish reduced
linear-system residual, full GN/filter residual, and actual nonlinear residual
defect. Cached numeric factors are reusable only while their matrix is unchanged.
Every candidate has an immutable parent and a complete independent state.

Start with tiny algebra/derivative tests and pinhole synthetic problems, then
screen small real BAL inputs. Synthetic references explicitly fix one camera
pose and one independent depth coordinate for scale; their first prototypes use
fixed intrinsics and a valid projection domain. These CPU references establish
mechanisms, not GPU speed claims against the 9-DOF Eta2 configuration. Real
incumbent instrumentation preserves its existing variables and gauge convention.
Any promotion gate must reconcile these differences before a head-to-head claim.

Use ten paired held-out synthetic seeds per setting, with separate development
seeds. Register targets before comparative timings, retain misses, and require
at least 1.10x median time-to-target gain with no additional geometric failures
before a candidate can replace the incumbent. Diagnostic exports and probes are
charged and reported separately from uninstrumented timing runs.

Publish switchable code, primary-source comparisons, raw records, tests,
reproduction commands and a supported/unsupported/inconclusive verdict for
each completed track. Report progress and the current incumbent in chat.

## Initial T1 scope

1. Check the exact pinhole identity and local retraction Jacobians.
2. Reproduce original Eta2 and generated instrumentation-off endpoints on
   Ladybug49, Dubrovnik88 and Venice52, N=3, 12 accepted-outers maximum.
3. Capture every full proposal, backtrack proposal and point-safeguard proposal
   in the first 12 outers on these small scenes. Also measure a fresh reduced
   residual before camera-radius restriction, separately from the recurrence
   residual. Captures are diagnostic cohorts, not speed measurements.
4. Evaluate signed depth changes, perspective versus camera-coordinate defect,
   radial/intrinsics defect, full GN residual, true cost and reconstruction
   validity from immutable captures. No new step controller is enabled yet.
5. Use pinhole synthetic development/held-out settings to test the predictive
   gate. Continue to a penalty/step-control prototype only if it adds signal.

`capture_geometry.py` initially reuses the existing exact fixed-direction BAL
reader/retraction from `bench/local_curvature_model.py` on the preserved WIP
checkout; additions are isolated here and validated against native costs.
