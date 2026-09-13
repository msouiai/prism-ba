# D22 result: terminal exact two-view polish is active but too small

## Verdict

D22 fails its preregistered first screen and stops before the extension,
Venice52, and practical-panel gates. Five deterministic common-input pairs on
Final3068 give `2/5` target hits in both the control and D22 arms, with zero
D22-only and zero control-only hits. The frozen Eta2 champion and B6v7 systems
candidate remain unchanged.

This closes exact two-view triangulation as both an always-on candidate policy
(wave-5 A1) and a one-shot fixed-camera stopping audit (D22). The per-track
algebra works: the terminal pass is active and strictly decreases the audited
objective. The available decrease is two orders of magnitude below the
registered materiality threshold.

## Registered experiment

D22 leaves deterministic B6v7 bit-identical until Eta2's normal FTOL or failure
rule proposes termination. If the target has not already been reached, one GPU
pass visits every exactly two-observation track at fixed cameras. It undistorts
the SIMPLE_RADIAL measurements, applies Lindstrom's deterministic two-step
epipolar correction, solves a 3x3 DLT problem, and keeps the replacement only
when the exact distorted-pixel track cost falls while the registered depth-sign
and horizon-margin checks pass. A full GPU cost is recomputed before commit.

The feature-off binary matches the deterministic parent exactly on Ladybug539:
endpoint bytes, accepted-cost and decision hashes, audited cost, hit, outers,
rejects, and Schur products all agree.

## Final3068 screen

The fixed target is `1744796.9841897595`. Inputs are fresh deterministic
`epsilon=1e-12` perturbations with seeds 660058--660062.

| Quantity | Result |
|---|---:|
| Control hits | 2/5 |
| D22 hits | 2/5 |
| D22-only / control-only hits | 0 / 0 |
| Terminal audits invoked / committed | 3 / 3 |
| Eligible two-view tracks | 510,966 |
| Improving replacements | 32,561 |
| Median terminal relative decrease | 0.0013036% |
| Relative-decrease range | 0.0004483--0.0035949% |
| Median active/control native-wall ratio when invoked | 1.000024x |
| Wall-ratio range | 0.999104--1.001443x |
| Exact preterminal paired paths | 5/5 |

The advancement rule required one D22-only hit or a median terminal decrease
above `0.15%`. The observed median is about 115 times smaller.

| Seed | Control cost | D22 cost | Winning tracks | Cost decrease |
|---:|---:|---:|---:|---:|
| 660058 | 1,759,596.7631 | 1,759,588.8745 | 610 | 7.8885 |
| 660060 | 1,773,960.3233 | 1,773,896.5516 | 14,415 | 63.7717 |
| 660061 | 1,911,830.5131 | 1,911,805.5911 | 17,536 | 24.9220 |

The kernel takes about 4.96--4.98 ms per invoked run. Summed local track
decrease agrees with the deterministic full-objective decrease to rounding.

## Mechanism conclusion

The E4 point was exceptional: wave-5 A1 reduced its track cost from `256/1795`
to about `0.033` and removed the recorded branch gap. D22 shows that this does
not generalise to stopped Final3068 states. Many fixed-camera tracks are
individually improvable, but their total missing decrease is negligible
relative to the target gap. The remaining failure is not principally a failure
to triangulate two-view tracks at the terminal cameras. A subsequent
stationarity test must include camera motion and camera--point alternation.

## Evidence

- `D22_TERMINAL_TRACK_POLISH_PROTOCOL.md`
- `d22-registration.json`
- `d22_terminal_track_polish/build-manifest.json`
- `d22-compatibility.json`
- `d22-final3068-results.json`
- `d22-final3068-summary.json`
