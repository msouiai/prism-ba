# Reproducing the ordered research screen

Use the repository's `research/geometry-agenda` branch. All commands below
run from the repository root. CPU scripts write their named JSON outputs
inside this package; use a separate checkout to preserve the published rows.
No original solver source or default configuration is changed by these scripts.

## Environment

Measured host: AMD EPYC 9354, Python 3.12.3, NumPy 2.1.2, SciPy 1.16.2,
Matplotlib 3.11.1. CPU experiments use one BLAS/OpenMP thread and FP64.
T1 uses an RTX 2000 Ada, driver 580.126.09, CUDA architecture sm_89.
Compiler invocation/source/binary hashes are in `capture_build_manifest.json`;
the incumbent's exact source and 44 headers are in the sibling frozen package.

```bash
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
python3 -m pip install --no-cache-dir --no-deps --target research/geometry_agenda/build/python scipy==1.16.2
python3 research/eta2_champion/build.py --check-only
python3 research/geometry_agenda/validate_package.py
```

NumPy and Matplotlib must also be installed at the versions above to reproduce
the recorded environment. Local SciPy installation is isolated in ignored
`build/python`. Timings will vary across hosts and library builds.

## T1: native instrumentation and predictive gate

The archived evidence can be analyzed without rerunning the GPU. Three
`evidence/t1-*.tar.xz` files contain original/off/capture logs and complete
native parent/step captures; archive and member hashes are listed in
`evidence/manifest.json`. Extract them under `/tmp/prism-geometry-agenda`
to restore the original directory names. Original BAL observations are read
from `/workspace/bal/{ladybug-49,dubrovnik-88,venice-52}.txt`.

For a native rerun:

```bash
python3 research/geometry_agenda/build_capture.py
python3 research/geometry_agenda/run_t1_capture.py
python3 research/geometry_agenda/analyze_t1_capture.py
python3 research/geometry_agenda/predict_depth.py
python3 research/geometry_agenda/run_t1_synthetic.py
```

`run_t1_capture.py` deliberately requires the measured original binary at
`/tmp/prism-rl-actor/build/prism-tr` and checks its SHA256. On another host,
build the sibling frozen package and make an explicitly recorded local
adaptation to that binary path/hash: do not silently call a rebuilt binary
byte-identical. The capture builder independently verifies frozen source and
headers. Native runs use an advisory GPU lock, 12 outers, N=3 original/off
repetitions and a separate capture cohort. `PRISM_AGENDA_OUT` selects new
scratch output; existing `result.json` files are reused by the runner.

## T2–T8: CPU experiments, in order

Synthetic and packed sample runs do not require a GPU. Development must
precede held-out pruning/policy evaluation. Protocols contain exact targets,
seeds, parameter grids, valid-domain policies and stopping conditions.

```bash
python3 research/geometry_agenda/run_t2.py --split development
python3 research/geometry_agenda/run_t2.py --split held_out
python3 research/geometry_agenda/run_t3.py --split development
python3 research/geometry_agenda/run_t3.py --split held_out
python3 research/geometry_agenda/run_t4.py --split development
python3 research/geometry_agenda/run_t4.py --split held_out
python3 research/geometry_agenda/run_t4_transfer.py --size small
python3 research/geometry_agenda/run_t4_transfer.py --size larger
python3 research/geometry_agenda/run_t4_transfer.py --size small --confidence --development
python3 research/geometry_agenda/run_t4_transfer.py --size small --confidence
python3 research/geometry_agenda/run_t4_transfer.py --size larger --confidence
python3 research/geometry_agenda/run_t4_real.py
python3 research/geometry_agenda/audit_cluster_scale.py
python3 research/geometry_agenda/run_t5.py --split development
python3 research/geometry_agenda/run_t5.py --split held_out
python3 research/geometry_agenda/run_t6.py --split development
python3 research/geometry_agenda/run_t6.py --split held_out
python3 research/geometry_agenda/t7_snapshots.py --split development
python3 research/geometry_agenda/t7_snapshots.py --split held_out
python3 research/geometry_agenda/run_t7.py --split development
python3 research/geometry_agenda/run_t7.py --split held_out
python3 research/geometry_agenda/t8_replay.py --split development
python3 research/geometry_agenda/t8_replay.py --split held_out
python3 research/geometry_agenda/run_t8.py
python3 research/geometry_agenda/uncertainty.py
python3 research/geometry_agenda/plot_results.py
```

`run_t4_real.py` regenerates the sample from native captures plus full BAL
observations and freezes a new feasible reference before timing. For a
strict repeat of published targets without the original large inputs, use
`replay_saved_real.py`; it reads the committed `evidence/t4-sampled-*.npz`
and `t4_real_targets.json`, writing `t4_real_replay.json` separately. T8 already
uses those packed samples and frozen targets directly.

The post-result cluster-scale replay is a geometry audit, N=1, and does not
replace the original N=3 timing records. The paired bootstrap resamples seeds,
not timing repetitions as independent scenes. Figures select seed100 (T4 v2:
seed300) by index, show all three repetitions, and export the plotted CSV.

## Gates and reproducibility limits

T1's controller, T6's adaptive radius schedule, T7's new filters, T8's RL, and
large native integrations were conditional branches whose prerequisites failed.
They are intentionally not claimed as implemented experiments. T4's positive
controlled result progressed to automatic partitions, larger synthetic cases
and real transfer before it was stopped.

The whole eight-track plan was committed before experiments; individual track
protocol files were written before their respective runs, but some were
committed later in batches. The T8 fallback correction is disclosed separately.
Neither source control nor this internal registration is an external timestamped
preregistration. `artifact_manifest.json` hashes final package contents and
records the environment; `validation.json` retains final check outputs.
