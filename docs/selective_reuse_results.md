# Selective Krylov reuse: short time-to-quality results

Selective reuse largely removes the overhead of always importing the captured basis in this screen. It is within 0.7% of the existing controller on both scenes, with no measured overall speedup over that controller. N=2 and Ladybug trajectory variability limit the strength of this result. The option remains disabled by default.

## Policy

`OCA_KRYLOV_REUSE=5` enables the work gate on top of the existing CG-capture mechanism and demand menu. With five shifts and a 64-vector basis, import is eligible only at saved depths 11–32 inclusive:

- At depth ≤ 2 × menu width, use ordinary wide CG: five residual certifications plus import overhead can consume the saving.
- Above half the basis capacity, use ordinary wide CG: leave room for extension when the smaller lambda needs a larger space.
- Otherwise try reuse. If the projected solve fails its true residual checks, fall back to ordinary CG and skip reuse for the next two expansions.

The thresholds are a conservative work heuristic, not a fitted performance model or a claim of optimality. No scene identifiers are used. The rule was frozen before these new results and was not tuned afterward. It changes only whether an expansion imports a captured basis. Existing narrow CG, nonlinear guards, damping selection and the certified projected-expansion implementation remain in place. Capturing the narrow vectors still incurs allocation/copy cost even when import is skipped.

## Equal-quality comparison

Same frozen binary and paired demand controller in all three arms: existing controller without capture, always-on capture reuse (mode 3), and selective reuse (mode 5). N=2 with rotated/reversed ordering. First accepted crossing is recorded by the existing target hook and independently CPU-certified. All 12 runs reached their target before the cap.

Ladybug-1197: target 366,600, cap 6 s. Dubrovnik-356: target 754,100, cap 12 s. The Dubrovnik target is the same early target as the previous capture study, **not** the older, harder 723,500 target. These are previously used scenes, not held-out validation or a Caspar comparison.

| Scene | Existing controller | Always reuse | Selective reuse | Selective vs existing time |
|---|---:|---:|---:|---:|
| ladybug-1197 | 2.823 s | 3.184 s | 2.841 s | +0.62% |
| dubrovnik-356 | 6.869 s | 6.955 s | 6.891 s | +0.32% |

On Ladybug, selective reuse took 10.8% less time than always-on reuse (1.121× ratio), bringing the median back near the existing controller. The two selective times were 2.654 and 3.028 s; the existing-controller times were 3.063 and 2.583 s. That spread prevents treating the small median difference as significant.

On Dubrovnik, selective reuse skipped all 58 expansions because their captured depths were too shallow. Existing and selective both used 799 operator calls and 1,368 scored candidates and finished at effectively the same cost, 754,099.11763. Selective took 0.32% longer; the remaining copy overhead and run variation are consistent with near-baseline performance, not a speedup.

## Decisions and work

Medians of two runs:

| Scene / method | Operator calls | Candidates scored | Reuse selected | Cheap skips | Capacity skips | Projection fallbacks |
|---|---:|---:|---:|---:|---:|---:|
| ladybug-1197 / legacy | 1367.5 | 462.5 | — | 0 | 0 | 0 |
| ladybug-1197 / always | 1548.5 | 451.5 | — | 0 | 0 | 1 |
| ladybug-1197 / selective | 1349.5 | 465 | 2.5 | 4 | 1 | 0 |
| dubrovnik-356 / legacy | 799 | 1368 | — | 0 | 0 | 0 |
| dubrovnik-356 / always | 790 | 1368 | — | 0 | 0 | 0 |
| dubrovnik-356 / selective | 799 | 1368 | 0.0 | 58 | 0 | 0 |

Selective reuse had no projection fallbacks in the timed runs. One always-on Ladybug repeat had two. The cooldown did not fire in these timings; its failure/recovery behavior was covered by the host policy test. Different trajectories mean the fallback difference alone does not prove how much time the gate saved.

## Verification and reproduction

The host test checks both depth boundaries, scaling with menu width, capacity reserve, two-expansion cooldown and recovery. The actual Ladybug-49 CUDA memory check exercised five reused expansions, two cheap skips and four capacity skips, reported zero sanitizer errors, and passed an independent CPU objective audit. Both CLI and core library built successfully.

All 12 timed endpoints passed CPU auditing (maximum relative discrepancy 3.93e-12), target-crossing checks and finite/monotone trace checks. Decision counts were matched to expansion logs. The timed screen used 59.539 native solver seconds. No timed runs were excluded or repeated, no larger scenes or Caspar jobs were started, and the broad queue remains paused.

Code: `gpu/selective_reuse.h`, integrated in `gpu/oca_cuda.cu`. Experiments: `bench/selective_reuse_quality.py` and `bench/summarize_selective_reuse.py`. Frozen protocol, targets, binary, source, headers, manifests, raw logs, exported states, audits and hashes are under `/workspace/prism-recycle-selective/`.

```bash
g++ -std=c++17 -O2 bench/test_selective_reuse.cc -o /tmp/test-selective-reuse
/tmp/test-selective-reuse
python3 bench/summarize_selective_reuse.py
# To run the frozen experiment; completed runs are retained:
python3 bench/selective_reuse_quality.py
```

## Assessment

This is a more practical opt-in reuse policy than always importing the basis: it preserves opportunities to reuse moderate-depth solves while avoiding the clear shallow-expansion and capacity-limit costs. It has not demonstrated a net speedup over the existing controller on these two scenes. The next evidence should come from a new scene or fixed-operator snapshots with genuinely expensive expansions, rather than another threshold search on these same results.
