# Reproducing the bounded Schur/control experiments

Run commands from the repository root on the isolated research branch.
Measured environment: RTX 2000 Ada, driver 580.126.09, CUDA 12.8.93,
`nvcc -O3 -DNDEBUG -std=c++17 -arch=sm_89`, Eigen under
`/usr/include/eigen3`, Python 3.12 with NumPy and Matplotlib. CUDA's
`compute-sanitizer` is used for memory checks.

The original `gpu/oca_cuda.cu` and frozen eta2 package are never patched in
place. All generated files and executables go under this directory's ignored
`build/`. The source package is checksum-verified before generation. Archive
fingerprints identify the measured builds; a different compiler/toolchain or
atomic ordering can change trajectories, so regenerated BAL states need not
be byte-identical to the recorded captures.

## Read results without running a solver

Extract the compact raw archive to a new directory, then recompute the ledger:

```bash
mkdir -p /tmp/prism-physics-evidence
tar -xJf research/schur_physics_control/evidence/raw-logs.tar.xz -C /tmp/prism-physics-evidence
python3 research/schur_physics_control/summarize.py --data /tmp/prism-physics-evidence
python3 research/schur_physics_control/plot_results.py
```

The archive excludes matrices and binaries. It contains logs, invocation
flags, result records, protocols, capture/input hashes and build manifests.
`summary.json` is directly readable without extraction. `evidence/inventory.json`
records hashes and sizes for the compact archives and measured artifacts.

## Build and rerun the linear/target gates

These research harnesses expect BAL files named `muell-gba146.txt`,
`ladybug-598.txt`, `ladybug-49.txt`, `final-1936.txt`, and `final-3068.txt` in
`/workspace/bal`. Use a fresh output path to retain the original evidence:

```bash
export PRISM_PHYSICS_OUT=/workspace/prism-schur-physics-repeat
python3 research/eta2_champion/build.py --check-only
python3 research/eta2_champion/build.py
export PRISM_REFERENCE_ETA2="$PWD/research/eta2_champion/build/prism-eta2"
python3 research/schur_physics_control/build.py --part capture
python3 research/schur_physics_control/build.py --part fixed
python3 research/schur_physics_control/run_fixed.py
python3 research/schur_physics_control/build.py --part solver
python3 research/schur_physics_control/run_targets.py
OPENBLAS_NUM_THREADS=1 python3 research/schur_physics_control/prepare_menu.py
python3 research/schur_physics_control/build.py --part menu
```

Build calls must finish before their dependent runner. Each runner acquires
`/tmp/prism_gpu.lock`; the vendor/other solver harnesses must honor the same
lock if run concurrently. Memory requirements include the captured observation
fragments; allow roughly 1.3 GiB of disk for these captures and spectral files.
The fixed gate skips an already manifested capture but reruns its benchmarks.

`OCA_COARSE_RANK=8/16` activates the correction only in the generated solver.
It requires the frozen classical eta2 configuration and guards against shared
intrinsics, a different layout or an active learned/replay policy. Rank0 is
off. None of these flags changes the original executable.

## Delivered v2 controls and diagnostics

`evidence/v2-source.tar.xz` contains the delivered source/headers. The builders
use `/workspace/multishift_repro` when present, or restore the checked source
archive into `build/v2-source`. `PRISM_V2_SOURCE` can point to another copy.
The original binary is deliberately not committed. Repeating the *delivered
binary* parity/control runs requires `/workspace/multishift_repro/oca_cuda_v2`
with the fingerprint in `evidence/v2-source-manifest.json`; a rebuilt binary
must be labeled as rebuilt instead.

```bash
python3 research/schur_physics_control/build_audit_v2.py
python3 research/schur_physics_control/run_stall.py
python3 research/schur_physics_control/run_followups.py
python3 research/schur_physics_control/build_probe.py --arm eta2
python3 research/schur_physics_control/build_probe.py --arm v2
python3 research/schur_physics_control/run_probe.py
python3 research/schur_physics_control/build_probe.py --arm eta2 --extended
python3 research/schur_physics_control/build_probe.py --arm v2 --extended
python3 research/schur_physics_control/run_probe.py --extended
```

`run_followups.py` runs Ladybug's target transfer, the projected menu gate and
the two uninstrumented v2 control cohorts. `run_stall.py` performs the N=10
gradient/stop-window audit. Each terminal-probe runner uses N=3 and has its
own registered protocol. `OCA_GRAD_AUDIT=1` is required for the terminal probe;
`OCA_RELAX_PROBE=1` evaluates candidates **without replacing the final state**.
The extended probe is a distinct generated binary with 12 trials and extra
finite-difference scales, so the original four-trial binary is preserved.

## Independent algebra and cold workspace checks

```bash
nvcc -O3 -DNDEBUG -std=c++17 -arch=sm_89 -I/usr/include/eigen3 research/schur_physics_control/coarse_check.cu -o research/schur_physics_control/build/coarse-check -lcublas
flock /tmp/prism_gpu.lock compute-sanitizer --tool memcheck --error-exitcode 9 research/schur_physics_control/build/coarse-check
nvcc -O3 -DNDEBUG -std=c++17 -arch=sm_89 -I/usr/include/eigen3 -Iresearch/schur_physics_control/build research/schur_physics_control/cold_fixed.cu -o research/schur_physics_control/build/cold-fixed -lcublas
flock /tmp/prism_gpu.lock research/schur_physics_control/build/cold-fixed "$PRISM_PHYSICS_OUT/muell-gba146-o12" "$PRISM_PHYSICS_OUT/muell-gba146-o11"
```

The existing `check_math.py` checks the CPU derivations. The GPU algebra test
compares the implemented balanced inverse with a dense reference, checks
symmetry, positive definiteness and exact action on the coarse space. Its
wrapped history exercises both ranks. The cold probe includes workspace
allocation/free with input matrices already resident; it is not data-loading
or process-startup time.
