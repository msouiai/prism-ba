# A1 targeted exact two-view repair — native verdict

The fixed-state mechanism test passed, but the native policy failed its
preregistered tail gate and is not a promotion candidate.

At the two recorded E4 proposals, Lindstrom's two-step epipolar correction
followed by an inhomogeneous 3x3 normal-equation triangulation reduced the
point-250233 costs from 256.303 and 1794.509 to 0.033476 and 0.033443.  Only
`3.24e-5` of the original 1538.206 hit/miss gap remained (`2.11e-8` as a
fraction), and the recomputed full-step trust ratios were 0.5028 and 0.5026.
The detector selected that point in both directions and selected at most
0.1411% of points in the nine healthy fixed-state captures.

The derived binary was endpoint-identical to the frozen champion with A1 off
(relative median difference `2.8e-15`).  In the live smoke test A1 spent
4.34 ms over six candidate evaluations, repaired 64 of 215 eligible tracks,
and changed the endpoint by only -0.034%.

The paired native tail result at N=5 was:

| Scene | Champion hits | A1 hits | Champion endpoint median | A1 endpoint median | Champion conditional target time | A1 conditional target time |
|---|---:|---:|---:|---:|---:|---:|
| Venice52 | 0/5 | 0/5 | 246,357.394 | 256,589.281 (+4.15%) | — | — |
| Final3068 | 3/5 | 3/5 | 1,744,268.771 | 1,743,339.805 (-0.053%) | 3.492 s | 4.660 s |

On Final3068, median rejects rose from 7 to 17 and the A1 kernel itself took
0.321 s at the median.  Across five runs it saw 19,505 eligible proposals and
accepted 11,709 local repairs.  Venice saw 3,062 eligible proposals and 878
repairs; its A1 kernel median was 0.083 s.  These counts are cumulative across
all candidate attempts, but they show why the fixed-state locality screen did
not imply trajectory locality.

The result separates two claims.  Exact per-track algebra does repair the
specific rational-model failure in E4.  Using local true-cost improvement to
apply that repair throughout a nonlinear trajectory is unsafe: many individually
better track choices alter the basin and make the global endpoint worse.  This
is another instance of the measured selection-perturbation law, alongside
geodesic correction and surrogate openings.  The practical panel was skipped
under the registered tail rule.

Artifacts: `a1-replay.json`, `a1-native-detector-validation.json`,
`a1-compatibility-summary.json`, `a1-smoke-summary.json`,
`a1-tails-results.json`, and `a1-tails-summary.json`.
