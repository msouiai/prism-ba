# Phase-aware fast-start and Schur-work study

## Question and protocol

Caspar FP32 reached coarse Muell-GBA146 error levels faster than Prism in the
prior comparison, while Prism reached the frozen useful-quality target much
earlier. This study tested whether Prism could borrow that early advantage
without changing the accepted objective, quality target, or its guarded
late-convergence behavior.

The isolated derivative is `build/prism-tr` (binary SHA-256
`79e9bbe6e9ea6821081f2b7fc78b396a7bc0521bcf221b950cf1743a90d6e0f5`). Its
only code change adds `OCA_CKPT_OPEN_OUTERS`: when nonzero, the pre-existing
`OCA_CKPT_OPEN` Krylov cap applies only to the first selected outer indices.
With the variable unset, the source retains the original behavior. The
candidate was frozen before measurement:

```text
OCA_CKPT_OPEN=16  OCA_CKPT_OPEN_OUTERS=3
```

It uses the cap only at outer indices 0–2, then restores the guarded solver.
The switch does not inspect objective value, target status, or endpoint
quality. Every endpoint below was independently recomputed on the original
observations in FP64 SIMPLE_RADIAL arithmetic. Exact commands, input hashes,
flags, traces, state hashes, and audit results are retained in
`protocol.json`, `results.json`, `summary.json`, and the `runs/` directory.

The three N=3 panels use pre-existing fixed targets and native solver time.
The Muell target is `1946488.746262194`; Ladybug-1723 and Final-1936 use their
historical one-percent targets. The two arms share the exact same binary,
inputs, command, `--lam0 0.1`, quality trigger, and time cap.

## Registered N=3 result

| scene | arm | certified target hits | target seconds, median [min, max] | matvecs, median [min, max] | final audited cost, median |
|---|---|---:|---:|---:|---:|
| Muell-GBA146 | guarded control | 3/3 | 4.543 [4.528, 4.550] | 1065 [1065, 1065] | 1945371.436 |
| Muell-GBA146 | fixed-window 16x3 | 3/3 | 4.544 [4.531, 4.545] | 1065 [1065, 1065] | 1945371.441 |
| Ladybug-1723 | guarded control | 3/3 | 0.432 [0.416, 0.434] | 116 [115, 136] | 452524.070 |
| Ladybug-1723 | fixed-window 16x3 | 3/3 | 0.423 [0.399, 0.426] | 134 [117, 140] | 452530.652 |
| Final-1936 | guarded control | 3/3 | 0.556 [0.552, 0.574] | 22 [22, 22] | 5095070.524 |
| Final-1936 | fixed-window 16x3 | 3/3 | 0.558 [0.557, 0.571] | 22 [22, 22] | 5095070.524 |

The candidate is **not promoted**. It made no material or reproducible change
on any panel. The small Ladybug time separation is accompanied by a larger,
variable matvec count and overlapping N=3 time ranges, so it is not evidence
of an acceleration.

There is an important provenance limitation. This new, internally paired
study passes `--lam0 0.1`, following the selected-candidate metadata. The
previous 4.220 s Muell champion report used the frozen source's CLI default
initial lambda (`10`) because its archived command omitted `--lam0`. Thus the
4.543 s control here is the correct baseline for this study's treatment, but
it must not replace the earlier 4.220 s result in an external comparison. All
comparisons in this table are nevertheless controlled because both arms use
the same command.

## Why the fixed window was inactive

The Muell control profile exposes the accepted Krylov depth and cumulative
matrix-vector products at each outer iteration:

| accepted outer | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CG depth | 0 | 1 | 3 | 2 | 7 | 60 | 29 | 128 |
| cumulative matvecs | 2 | 5 | 10 | 14 | 23 | 85 | 116 | 244 |

The proposed `16x3` policy covers only depths 0, 1, and 3. It therefore
produces exactly the same 1,065 total matvecs and same 16 accepted outers as
the control. The expensive regime starts at outer 6 and contains repeated
128-step solves. A meaningful fast-start policy would have to affect that
regime, where a shallow solve risks changing the nonlinear path.

## Tests of the two obvious cheap-work alternatives

These are single-run development diagnostics, intentionally not N=3 ranking
claims. Their promotion criterion was a clean certified target hit and at
least a 10% Muell target-time improvement over the 4.543 s paired control.

| mechanism | target time | accepted outers / rejects | matvecs | audited cost | decision |
|---|---:|---:|---:|---:|---|
| paired guarded control (N=3 median) | 4.543 s | 16 / 0 | 1065 | 1945371.436 | reference |
| cap 16 at every healthy outer | 4.726 s | 19 / 1 | 1077 | 1946124.930 | reject, slower |
| `OCA_JIT_J=1`, recompute Jacobians in Krylov passes | 15.724 s | 16 / 0 | 1065 | 1945371.443 | reject, 3.46x slower |

Keeping the shallow cap globally did not save total work: its less accurate
steps required three additional outers, one rejection, and 12 more matvecs.
It reached the target but was 4.0% slower in this diagnostic. Recomputing
Jacobians preserved the full nonlinear trajectory almost exactly—the same
accepted outer count, matvec count, and audited endpoint—but was much slower
than reading the existing compact fragments on this GPU. Neither route
deserves an N=3 extension.

## What consumes Muell time

An Nsys CUDA-kernel profile of the first eight guarded Muell outer iterations
(244 matvecs, eight candidate evaluations) assigns the following kernel time:

| kernel family | cumulative CUDA time | share |
|---|---:|---:|
| `MFPass2<9,float>` | 375.9 ms | 28.8% |
| `MFAssemble<9,float>` | 368.2 ms | 28.2% |
| `MFPass1<9,float>` | 326.2 ms | 25.0% |
| fused RHS and diagonal | 96.0 ms | 7.3% |
| point inverse application | 47.8 ms | 3.7% |
| candidate scoring and remaining kernels | 90.4 ms | 6.9% |

The two Schur product passes account for 53.8% of device kernel time and
assembly for another 28.2%. The solver's own phase profile over the complete
Muell solve agrees: 3.327 s in Krylov work, versus 0.737 s assembly, 0.243 s
point-factor/RHS work, and 0.045 s candidate evaluation. Thus the
single-shift guarded champion is not bottlenecked by lambda-menu scoring.

`MFPass1` must first form the point-side accumulation `W^T v`; only after the
point-block inverse can `MFPass2` form `W V^-1 W^T v`. That Schur dependency
prevents a simple fusion of the two streams. The useful route is therefore to
reduce the number or cost of the late, deep products while retaining their
linear-solve quality.

## Conclusion and next candidate

The current winner remains the guarded Schur-accurate Prism configuration.
No fast-start cap or on-the-fly-Jacobian variant from this study is a valid
replacement. Caspar's coarse-error lead is real, but copying its shallow,
fixed-depth behavior into this late-converging Prism path only moves work to
extra nonlinear iterations or rejections.

The next mathematically grounded candidate is a stronger Schur
preconditioner, rather than a lower Krylov cap: approximate the off-diagonal
camera coupling in `Hcc + lambda*D - W*V(lambda)^-1*W^T` so that the same
inexact-Newton criterion takes fewer than 128 products. It must be tested
first as a same-trajectory linear-residual diagnostic, then against a
pre-registered N=3 target panel. Only after it lowers deep-solve products
should kernel work focus on the two Schur passes; JIT Jacobian recomputation
is ruled out for this hardware and stored-fragment format.

## Artifact map

- `build/source.cu`, `build/build.log`, and `build/prism-tr`: isolated source
  change and reproducible binary.
- `run_study.py`: registered N=3 paired runner.
- `run_global_cap_diagnostic.py` and `run_jit_diagnostic.py`: bounded
  development diagnostics.
- `run_nsys_profile.py` and `nsys/muell-first8-kernels_cuda_gpu_kern_sum.csv`:
  profiling command and raw kernel accounting.
- `runs/`, `profile/`, `explore-global-cap/`, and `explore-jit/`: commands,
  flags, logs, traces, state files, and FP64 endpoint audits.
