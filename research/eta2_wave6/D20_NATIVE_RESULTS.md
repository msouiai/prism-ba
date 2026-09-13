# D20 native verdict: the quotient gate is inactive on fresh Venice trajectories

## Verdict

**Reject D20 as a native Eta2 change.** The fixed-state quotient projection is
mathematically and causally strong, but the preregistered state does not recur
under the frozen champion on the fresh cohort. Venice52 finishes at 0/5 target
hits in both arms, with exactly identical endpoints in every common-input pair.
The hard 3/5 gate fails, so Final3068 and the practical panel were not run and
no threshold or gate tuning follows.

The frozen Eta2 champion remains the scientific winner. B6v7 remains the
systems winner.

## Registered Venice result

Five deterministic common-input pairs used `epsilon=1e-12` perturbations and
seeds 660048--660052 at the fixed target 243740.27.

| metric | control | D20 |
|---|---:|---:|
| target hits | 0/5 | 0/5 |
| median endpoint | 244961.576 | 244961.576 |
| median native wall | 3.522 s | 3.489 s |
| quotient projections | -- | 0 |

Every paired endpoint delta is exactly zero. The small wall difference is
ordinary timing noise and cannot be credited to an inactive intervention.

Four D20 runs have maximum raw/radius ratios of 74.43--74.50, below the fixed
threshold of 100. One reaches ratios 208.15, 229.33 and 222.53, with camera 34
carrying 99.32--99.59% of active step energy. Its globally weakest local block
belongs to camera 32, however, so the full registered gate declines to project.
That distinction is evidence rather than an implementation failure: the five
archived static-track-damping terminal states that passed the fixed audit and
the fresh frozen-champion states do not have the same local spectral ordering.

## What survived

At the archived states, direct quotienting remains the cleanest demonstration
of the global-clipping pathology: one camera-mode component contains 99.9973%
of raw energy, and removing it changes the fixed-state true decrease from about
1.60 to 481 while leaving all other camera coordinates exactly unchanged.
Native convergence shows that this witness is conditional on the trajectory
that produced it. It is therefore a diagnostic result, not a run-everywhere
algorithm.

Feature-disabled compatibility passed exactly in endpoint SHA256, accepted
costs, controller decisions, hit, outers, rejects, products and audited cost.
The zero projections and exact paired endpoints confirm that the enabled
implementation also leaves the trajectory untouched when its gate is false.

## Reproducibility

- Protocols: `D20_SLOPPY_QUOTIENT_PROTOCOL.md`, `D20_NATIVE_PROTOCOL.md`
- Build and runner: `d20_sloppy_quotient/`
- Fixed audit: `d20-sloppy-quotient-results.json`,
  `d20-sloppy-quotient-summary.json`
- Native registration and results: `d20-native-registration.json`,
  `d20-native-compatibility.json`, `d20-venice-results.json`,
  `d20-venice-summary.json`

