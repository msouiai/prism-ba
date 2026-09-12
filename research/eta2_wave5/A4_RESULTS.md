# A4 settling result: lower acceptance threshold

The fresh preregistered N=10 cohort does not promote `rho_min=1e-3`.

| Scene | Arm | Hits | Conditional target time, median [range] | Endpoint median [range] | Rejects, median |
|---|---|---:|---:|---:|---:|
| Final3068 | frozen/off | 4/10 | 3.953 [2.620, 4.247] s | 1,788,452.66 [1,740,521.14, 1,949,407.27] | 12.0 |
| Final3068 | rho001 | 6/10 | 5.190 [3.418, 7.228] s | 1,744,749.35 [1,740,115.11, 1,875,352.57] | 6.5 |
| Venice52 | frozen/off | 0/10 | — | 246,339.58 [244,954.30, 247,591.19] | 7.0 |
| Venice52 | rho001 | 0/10 | — | 247,762.66 [247,746.34, 250,262.80] | 0.0 |

The Final3068 hit-count change is unresolved (two-sided Fisher exact
`p=0.6563`) and its conditional crossings are slower.  On Venice the endpoint
ranges do not overlap; the lower threshold is 0.578% worse at the medians
(Mann-Whitney `p=0.000183`) while neither arm reaches the registered target.
The intervention does reduce rejections, but it accepts weak-model steps that
lose enough endpoint quality to fail the promotion rule.  The champion's
acceptance threshold remains unchanged.

All endpoint states were independently rescored in FP64.  Exact state hashes,
curves, logs, attempt traces, build/source hashes and command manifests are in
`a4-results.json` and the ignored `evidence/a4/` tree.  States were removed only
after audit because the host is at its volume quota.
