# Muell GBA146 production-scan variant screen

**Scope.** N=3 target-crossing test on `muell-gba146` (493 cameras, 313,987 points, 2,118,671 observations), a well-conditioned real production scan. All endpoints were independently scored in CPU FP64 against the original observation set. Native times are host-local solver times; input loading and auditing are excluded.

## Verification and target

The independent loader read initial cost **2,442,177.030208319**, agreeing with the delivered anchor 2,442,177.030208 at the reported digits. The target was preregistered after, and only after, three no-treatment fixed-five calibrations: median audited endpoint 1,936,804.722649; fixed target **1946488.746262** (= 0.5% above that median). The three calibration endpoints were 1936804.722649, 1936804.611221, 1936805.542973.

The target is a shared quality level; every measurement run reached it. Reported endpoint cost is the independently audited stopping state, so it is descriptive of threshold overshoot and is not a convergence-quality ranking.

## N=3 results

| Arm | Target hits | Crossing seconds, median [min, max] | Final audited cost, median [min, max] | Outers, median [min, max] | Rejects, median [min, max] | Native seconds, median [min, max] |
|---|---:|---:|---:|---:|---:|---:|
| control-single | 3/3 | 13.858 [12.299, 14.383] | 1946318.6 [1945863.6, 1946389.3] | 29 [26, 30] | 0 [0, 0] | 13.872 [12.313, 14.396] |
| control-five | 3/3 | 12.363 [12.208, 12.392] | 1945795.1 [1945356.9, 1946318.5] | 20 [20, 20] | 0 [0, 0] | 12.378 [12.236, 12.411] |
| tr-single | 3/3 | 16.331 [16.330, 16.967] | 1946066.3 [1945791.2, 1946068.3] | 28 [28, 33] | 0 [0, 0] | 16.345 [16.344, 16.981] |
| tr-five | 3/3 | 18.792 [17.705, 19.348] | 1945971.7 [1944465.1, 1946430.2] | 29 [26, 30] | 0 [0, 0] | 18.806 [17.720, 19.362] |
| retri-single | 3/3 | 15.164 [13.455, 44.669] | 1946303.0 [1946038.8, 1946354.4] | 31 [30, 69] | 0 [0, 0] | 15.184 [13.477, 44.685] |
| retri-five | 3/3 | 10.930 [10.928, 12.395] | 1946027.8 [1945421.1, 1946047.4] | 18 [18, 20] | 0 [0, 0] | 10.952 [10.944, 12.409] |
| annealed-s-five | 3/3 | 13.154 [12.761, 15.308] | 1946084.9 [1945981.4, 1946407.1] | 24 [22, 26] | 0 [0, 0] | 13.169 [12.782, 15.322] |
| schur-guarded-lm | 3/3 | 4.220 [4.216, 4.232] | 1945209.7 [1945209.6, 1945209.7] | 19 [19, 19] | 0 [0, 0] | 4.229 [4.225, 4.242] |

## Interpretation

- Fixed five shifts beat the matched single-shift control: 12.363s versus 13.858s (1.12× speedup).
- Periodic pointwise DLT retriangulation with five shifts is a modest production-scan win: 10.930s versus 12.363s (1.13× speedup), with 18 median outers versus 20. Its single-shift version is slower and has a 44.669s tail, so repair does not rescue a narrow menu here.
- Camera-block radius TR loses in this regime: five-shift TR is 18.792s (1.52× the fixed-five control), and single-shift TR is 16.331s (1.18× its single-shift control). Every measured run has zero rejects, supporting the explanation that there is no reject storm for the radius controller to suppress.
- The annealed point-damping profile is also slower than fixed-five on this warm production scan. It is therefore a quality/floor candidate, not the production-speed choice on this instance.
- The frozen Schur-guarded LM champion reaches the same target in 4.220s (2.93× faster than the shared-source fixed-five control), with 19 outers, zero rejects and 927 matvecs in every repetition. It is a different frozen source/binary, so this establishes an all-in candidate result rather than attributing the gain to one switch.
- The preregistered TR+retriangulation combination was **not run**: both isolated mechanisms had to beat fixed-five by more than 3% in all-target N=3 comparison; TR was consistently slower. This avoids a post-hoc stack test.

## Provenance

- Input SHA-256: `33de7cd28b7f0e91550f8af332990ac8e84b13b35563e9429c8f64849e58ba6c`.
- Shared-source combined binary SHA-256: `a53d0cdb776ece065d19f92ff68a6ce740b91ed136e8ee16e16ba0c060b55cc0`. It is the frozen camera-TR one/five-shift source plus the committed pointwise DLT reset.
- Schur-guarded candidate SHA-256: `117773562d33949cdbfdc27905d1f23a2cc1faedb7f77c3e619c17caa50a86dc`.
- Exact commands, environment flags, traces, exported states, audits and raw logs are retained in `runs/`; per-run table is `measurement_rows.csv`.
