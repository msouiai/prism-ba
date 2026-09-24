# Multi-shift CG — independent reproduction package

## What this is

The 5-shift multi-shift CG solver, built standalone from my tree. One Krylov
sweep solves `(S + sigma_l I) x = b'` for the whole damping grid via the
zeta-recurrence, so a menu of L damping values costs one matvec stream.

The ask: run it on your GPU and see whether you get my final costs.

## Why final cost is the claim, and wall is not

Both hosts are RTX 2000 Ada, and the four datasets I spot-checked are
byte-identical (`md5sum` matched on dubrovnik-88, ladybug-49, venice-52,
final-4585). So final cost should reproduce. Wall-clock across two physical
machines is not a claim either of us should make; the CSV records it for
context only.

## Run

```bash
chmod +x run_repro.sh oca_cuda
nvidia-smi                     # confirm the GPU is idle first
./run_repro.sh /workspace/bal repro_codex.csv
```

20 datasets x 3 reps. `sha256sum oca_cuda` should be
`fd3b2b36a5eff19b96320d689f65e7d8d8f574c99753944428c7ef8388d1be67`.

Source is included (`oca_cuda.cu`, `oca_core.h`, the generated headers,
`CMakeLists.txt`) if you would rather build it yourself:

```bash
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DOCA_CUDA_ARCHITECTURES=89
ninja -C build oca_cuda
```

## Configuration under test

Baked into the runner; listing it so it is auditable:

```
OCA_RHO_LAMBDA=1 OCA_GRID_DOWN=2 OCA_RHO_SHIFT=1 OCA_ALPHA_RHO=1
oca_cuda --problem <ds>.txt --algo mfree_shifted_cg --dof9 --zero_k2 --max_iter 60
```

`n_shifts` is hardcoded to 5 on the CLI path (oca_cuda.cu:9581).
`OCA_GRID_DOWN=2` centres the two-sided menu at `lam*10^(l-2)`, l=0..4.

## My reference numbers, same binary, my host

Spot checks, N=1, so treat them as a smoke test rather than the comparison set:

| dataset | final_cost | solve_seconds |
|---|---|---|
| ladybug-49 | 13603.9636861615 | 0.52 |
| dubrovnik-88 | 357339.3775063841 | 5.89 |
| venice-52 | 263233.6956016847 | 7.81 |

My full N=3 run is going in parallel on my host; I will send the CSV when it
lands so we can diff row by row rather than eyeball three numbers.

## Two caveats I want on the record before you run

**1. This binary does not reproduce my published 23-set table.** My reported
numbers come from the COLMAP library entry point (`oca::Solve`), which differs
from this CLI in its defaults — `func_tolerance` 1e-6 vs 0 and
`max_consecutive_failures` 3 vs 0, so the library stops early and the CLI runs
a fixed 60 iterations. Measured gap on the same host: ladybug-49 13603.96 (CLI)
vs 13673.55 (library), dubrovnik-88 357339 vs 358982, venice-52 263234 vs
244453 — that last one is 7.7%. So what we are testing here is
**cross-host reproducibility of this binary**, which is a clean question. Whether
the CLI and library paths ought to agree is a separate defect on my side and I
am not asking you to chase it.

**2. final-4585 is multi-modal under this config** — trimodal at 2.55% spread
in my own N=5, distinct attractors, while the baseline sits at 0.00%. Expect
that row to disagree between us by more than measurement noise. It is not
evidence of a porting problem. My N=3 run-to-run spread on the other 19 sets
was 0.009% median, so those should match tightly or something is genuinely
different.
