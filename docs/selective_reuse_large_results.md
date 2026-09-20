# Selective reuse on a large BAL problem: final-4585

The unchanged selective policy transfers to this large scene by avoiding reuse on all five shallow expansions. It reaches the common target in both repeats, approximately matching the existing controller. Always-on reuse misses the target in both repeats. This validates avoiding overhead on this scene; it does not demonstrate a benefit from importing a Krylov basis.

## Protocol

BAL final-4585: 4,585 cameras, 1,324,582 points, 9,125,125 observations. Same immutable executable and selective depth rule as the preceding small-scene screen, without rebuilding or retuning. Existing paired demand controller versus always-on capture reuse (mode 3) versus selective reuse (mode 5). N=2, rotated/reversed order, sequential GPU lock.

Common objective target: 9,000,000; native budget: 20 seconds per run. The early target was fixed before these results, using older final-4585 traces only to choose a plausible short target. This is not a full-convergence comparison. The scene has older repository benchmarks but was not used to choose the new selective rule. No Caspar jobs or additional scenes were run.

Times below record the first accepted target crossing before cleanup/export. Each endpoint is independently CPU-audited. A speed ratio requires both compared methods to hit in both repeats. Budget checks occur at existing solver boundaries, so in-flight work can overrun the nominal budget and be discarded.

## Results

| Method | Target hits | Median time to target | Median exported cost | Median native return time |
|---|---:|---:|---:|---:|
| Existing controller | 2/2 | 19.156 s | 8,830,456.67 | 19.442 s |
| Always reuse | 0/2 | Missed target | 9,230,536.06 | 22.887 s |
| Selective reuse | 2/2 | 19.383 s | 8,830,464.63 | 19.659 s |

Selective reuse took 1.19% longer by median (0.988× existing/selective ratio), with effectively equal final cost. Existing times were 19.145 and 19.167 s; selective times were 19.197 and 19.570 s. N=2 does not support a strong interpretation of that small difference.

Always-on reuse finished around cost 9,230,536, 2.56% above the target. It returned after about 22.9 s because its last attempt overran the budget. Neither run crossed the target, so no equal-quality speed ratio against it is reported. The selective run returning at 20.093 s still qualifies: its certified crossing occurred at 19.570 s, before the 20 s cap.

## What the policy did

In both selective repeats, the five captured depths were **5, 9, 9, 10 and 8**. All lie below the reuse gate, which requires depth greater than 10. Therefore every expansion used ordinary wide CG. No basis imports, projection fallbacks or cooldown skips occurred. Narrow-vector capture still incurs copying/allocation overhead.

| Method | Accepted iterations | Operator calls | Scored candidates | Projection fallbacks |
|---|---:|---:|---:|---:|
| Existing controller | 26 | 419 | 234 | 0 |
| Always reuse | 24 | 589 | 227 | 2 |
| Selective reuse | 26 | 419 | 234 | 0 |

These counts were the same across both repeats within each method. All six runs had zero nonlinear rejections. Always-on reuse paid about 41% more operator applications than the existing controller while accepting fewer steps; its two projection fallbacks per run are additional work, not nonlinear rejection counts. This reinforces the distinction between a large overall problem and an expensive expansion worth recycling.

## Validation and artifacts

All six runs completed successfully, all exported states passed CPU auditing (maximum relative discrepancy 6.96e-15), and accepted traces passed finite/monotone checks. Target hits were verified as first accepted crossings. The study used 123.976 native solver seconds in total. No timed runs were excluded or repeated. Solver code and the selective rule were unchanged; only the reporter was generalized to read scene names from the frozen targets file.

Artifacts: `/workspace/prism-recycle-selective-large/`, including protocol, targets, frozen binary/source/headers, manifests, logs, states, per-run audits, summary and hashes. The existing broad queue remains paused; no benchmark jobs remain running.

```bash
python3 bench/selective_reuse_quality.py --root /workspace/prism-recycle-selective-large
python3 bench/summarize_selective_reuse.py --root /workspace/prism-recycle-selective-large
```

Keep the feature opt-in. This screen supports the selective rule as protection against unproductive reuse, but a positive reuse speedup still requires a case with eligible, costly expansions. Simply increasing the number of cameras is not sufficient.
