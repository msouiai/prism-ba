# Five additional large BAL instances — 2026-09-07

Frozen compact FP64 mode 2, unchanged selected rearm-only multi-shift policy,
guarded single-shift, and frozen Caspar FP32 defaults. Five cases selected
before results; N=1 per method, 30-second native solve budget, 180-second
process timeout. No parameter retuning or added repeats. Method order was
multi, single, Caspar, not randomized. The two Venice instances are related
snapshots; five BA instances do not represent five independent landmarks.

Sources: [Final](https://grail.cs.washington.edu/projects/bal/final.html),
[Venice](https://grail.cs.washington.edu/projects/bal/venice.html), and
[Dubrovnik](https://grail.cs.washington.edu/projects/bal/dubrovnik.html).
All five were absent from the earlier local dataset collection.

| Instance | Cameras | Points | Observations |
|---|---:|---:|---:|
| final-871 | 871 | 527,480 | 2,785,977 |
| final-961 | 961 | 187,103 | 1,692,975 |
| venice-951 | 951 | 708,276 | 3,748,892 |
| venice-1778 | 1,778 | 993,923 | 5,001,946 |
| dubrovnik-356 | 356 | 226,730 | 1,255,268 |

## Endpoints and native runtimes

CPU raw-z FP64 final cost, lower is better. Actual native solve runtimes may
exceed 30 seconds: late candidates are discarded, but unfinished attempts
are allowed to finish. Methods may stop early under their own stopping rules.
Times are not common time-to-quality crossings or equal end-to-end latency.

| Instance | Multi cost | Single cost | Caspar cost | Multi s | Single s | Caspar s |
|---|---:|---:|---:|---:|---:|---:|
| final-871 | 1,930,140.380 | 1,933,945.323 | 1,947,510.498 | 30.127 | 30.828 | 10.002 |
| final-961 | 1,666,895.209 | 1,665,593.838 | 1,666,488.445 | 12.775 | 11.433 | 10.015 |
| venice-951 | 1,956,230.315 | 1,977,688.262 | 2,104,975.029 | 30.092 | 30.696 | 6.316 |
| venice-1778 | 2,073,005.194 | 2,065,732.464 | 2,112,881.772 | 31.576 | 30.829 | 30.059 |
| dubrovnik-356 | 717,947.402 | 739,372.270 | 1,059,504.274 | 30.354 | 30.104 | 30.001 |

| Instance | Multi vs Caspar cost | Single vs Caspar cost | Multi vs single cost |
|---|---:|---:|---:|
| final-871 | -0.892% | -0.697% | -0.197% |
| final-961 | +0.024% | -0.054% | +0.078% |
| venice-951 | -7.066% | -6.047% | -1.085% |
| venice-1778 | -1.887% | -2.232% | +0.352% |
| dubrovnik-356 | -32.237% | -30.215% | -2.898% |

Negative cost differences favor the numerator. Small differences are not
statistical wins: each cell has one run, and atomic-order variation can
change trajectories and stopping. Do not divide unequal-quality runtimes
and call the ratio an algorithm speedup.

## Work, memory, and stopping

| Instance | Method | Accepted | Rejected | Matvecs | Scored | Rearms | GPU MiB sampled | Overshoot s | Stop |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| final-871 | selected | 51 | 0 | 3285 | 806 | 0 | 1216 | 0.127 | budget |
| final-871 | single | 51 | 0 | 3496 | 548 | 0 | 1166 | 0.828 | budget |
| final-871 | caspar32 | 108 | 65 | — | — | — | 654 | 0.000 | damping limit |
| final-961 | selected | 38 | 0 | 2353 | 667 | 0 | 730 | 0.000 | relative improvement |
| final-961 | single | 39 | 0 | 2142 | 420 | 0 | 712 | 0.000 | relative improvement |
| final-961 | caspar32 | 162 | 96 | — | — | — | 408 | 0.000 | damping limit |
| venice-951 | selected | 45 | 0 | 2379 | 741 | 0 | 1586 | 0.092 | budget |
| venice-951 | single | 44 | 0 | 2578 | 472 | 0 | 1520 | 0.696 | budget |
| venice-951 | caspar32 | 76 | 34 | — | — | — | 848 | 0.000 | damping limit |
| venice-1778 | selected | 23 | 0 | 2062 | 431 | 0 | 2076 | 1.576 | budget |
| venice-1778 | single | 33 | 0 | 1966 | 346 | 0 | 1984 | 0.829 | budget |
| venice-1778 | caspar32 | 128 | 92 | — | — | — | 1112 | 0.059 | budget |
| dubrovnik-356 | selected | 270 | 8 | 6044 | 2600 | 1 | 602 | 0.354 | budget |
| dubrovnik-356 | single | 229 | 0 | 6639 | 1993 | 0 | 582 | 0.104 | budget |
| dubrovnik-356 | caspar32 | 4199 | 5 | — | — | — | 342 | 0.001 | budget |

Work counts include unfinished overbudget work; GPU memory is sampled process
usage, not an allocator-certified peak. Caspar rejection counts are native
trace rejected iterations; PRISM reports its rejected attempts. Damping-limit
exit is a solver stopping decision, not a certificate of optimality. If rearm
never activates, do not attribute a result to that safeguard.

## Numerical checks and interpretation

PRISM preserves FP64 arithmetic and raw-z projection; Caspar FP32 uses its
native epsilon-guarded projection. The common CPU endpoint scorer uses raw-z.
Initialization is also affected by Caspar's float conversion. Thus this is a
practical implementation screen, not a matched-precision algorithm ablation.
Setup boundaries remain as in [fixed-policy validation](fixed_policy_validation.md).

| Instance | Multi CPU/GPU relative error | Single CPU/GPU relative error | Caspar native/CPU final gap | Caspar initial quantization gap |
|---|---:|---:|---:|---:|
| final-871 | 1.33e-15 | 1.08e-15 | 0.007458% | 0.000005% |
| final-961 | 1.12e-15 | 1.12e-15 | 0.000139% | 0.000026% |
| venice-951 | 1.19e-16 | 9.42e-16 | 0.067888% | 0.000022% |
| venice-1778 | 3.03e-15 | 1.24e-15 | 0.000060% | 0.000146% |
| dubrovnik-356 | 3.24e-15 | 3.15e-16 | 0.000049% | 0.000020% |

All successful PRISM endpoints pass the independent CPU audit at 1e-7
relative tolerance. Exact exported state hashes are verified. Frozen binary,
input hashes, commands, flags, logs, stderr, protocol, and sampler output are
retained at `/workspace/prism-five-large/`. Original results remain separate
from earlier cohorts. Reproduce with `python3 bench/five_large_screen.py`
after preparing the frozen artifacts and downloading the five scenes.
The downloader now accepts three additional public cases without changing
its default REPRODUCE dataset list. Python compilation and diff checks pass.
The broader queue stays paused; solver defaults are unchanged; nothing pushed.
