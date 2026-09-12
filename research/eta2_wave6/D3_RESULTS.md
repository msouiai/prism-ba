# D3 results: FP64 fragments remove the numerical jump but do not improve reliability

## Verdict

The FP64-fragment arm fails the preregistered production gate.  The sequential
test stopped at its lower boundary after 35 paired inputs: FP64 won 8 of the 18
discordant pairs and FP32 won 10.  This is evidence against the registered
claim that FP64 would own at least 70% of discordances; it is not evidence that
FP64 is intrinsically harmful.  The ordinary two-sided exact McNemar test is
non-significant (`p=0.815`).

The speed result is decisive.  On all 15 double-hit pairs FP64 was slower to
the identical registered target.  Its FP64/FP32 target-time ratio was
`1.2165--2.2189`, with median `1.6342`.  The registered production limit was
`1.25`.  Therefore no compact high-plus-low fragment representation is built
from this mechanism.

This separates two properties that had been conflated.  D2c/D2d established
that FP64 fragment storage makes the trajectory vastly more continuous under
infinitesimal input changes.  D3 establishes that this smoothness neither
raises Final3068 target reliability nor preserves target speed.  The basin
lottery is real at finite scale; removing one numerical perturbation changes
which trials reach which basin rather than consistently selecting the good
one.

## Registered design

- Scene: Final3068, full plain-L2 objective.
- Target: `1744796.9841897595`.
- Inputs: 35 unseen, deterministic PCG64 perturbations at `epsilon=1e-10`,
  seeds `640000--640034`.
- Pairing: both binaries consumed byte-identical BAL files; arm order
  alternated by pair.
- Binaries: deterministic B6v7 path, differing only in stored Jacobian
  fragment type (FP32 or FP64).
- Limits: 45 native seconds and 600 outers.
- Endpoint: independently rescored in FP64 before its temporary state was
  removed.
- Sequential hypotheses on discordant pairs: `q0=0.50`, `q1=0.70`,
  `alpha=0.05`, `beta=0.10`, at most 60 pairs.

All 70 processes completed normally.  Every manifest's input hash matches its
pair.  Maximum independent endpoint-audit relative error was `4.27e-13` for
FP32 and `4.45e-12` for FP64.  No run hit the wall or outer cap.

## Primary outcomes

| outcome | pairs |
|---|---:|
| both hit | 15 |
| FP32 only hit | 10 |
| FP64 only hit | 8 |
| both miss | 2 |
| total | 35 |

| quantity | FP32 fragments | FP64 fragments |
|---|---:|---:|
| hits | 25/35 (71.4%) | 23/35 (65.7%) |
| Wilson 95% interval | 54.9--83.7% | 49.2--79.2% |
| target time, all hits, median | 7.907 s | 12.755 s |
| target time, all hits, range | 4.539--11.279 s | 11.385--16.351 s |
| native wall, all runs, median | 7.679 s | 12.053 s |
| outers, median | 66 | 128 |
| rejects, median | 7 | 9 |
| Schur products, median | 340 | 471 |

The sequential log likelihood ratio was `-2.4165`, past the registered lower
boundary `-2.2513` and far from the upper boundary `2.8904`.  A neutral
Beta(1,1) descriptive posterior for FP64's share of discordances is
Beta(9,11), with 95% interval `0.244--0.665`; this is descriptive rather than
the preregistered decision rule.

The median endpoint costs over hits and misses together were
`1,742,772.93` (FP32) and `1,744,302.62` (FP64).  This small aggregate
difference is not used as a win: the paired hit outcome and identical-target
time were primary, and the failed endpoints occupy distinct modes.

## Interpretation

The D2 result remains valuable as a diagnosis of the numerical map.  It does
not justify spending FP64 bandwidth in the production solver.  FP32 fragment
rounding acts as a finite perturbation early in the trajectory; at the tested
shell it sometimes helps and sometimes hurts.  FP64 suppresses the
perturbation, but then follows a longer trajectory and enters good and bad
basins at statistically unresolved proportions.

Consequently:

1. do not promote FP64 fragment storage;
2. do not build FP32-high plus a low residual solely to recover D2 continuity;
3. retain the FP64 build as a diagnostic instrument for paired forensics;
4. use deterministic paired experiments to assess interventions, because the
   8-vs-10 discordance split shows that unpaired N=5 cohorts can reverse a
   conclusion even when each arm is internally deterministic.

Raw scalar evidence is in `d3-results.json`; the registered calculation is in
`d3-summary.json`; per-run logs and manifests are under the ignored
`evidence/d3-precision/` tree.
