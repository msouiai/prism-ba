# Isolated sustained-eta2 research champion

This directory contains the exact frozen source of the measured Prism champion and the latest speed/curvature findings. It is an opt-in research solver. The original `gpu/oca_cuda.cu`, original build targets and default algorithm configuration are unchanged by this package.

## Build and run

Requires Python 3.11+, CUDA/NVCC and Eigen headers. From the repository root:

```bash
python3 research/eta2_champion/build.py --arch sm_89
python3 research/eta2_champion/run.py --problem /path/to/problem.txt --seconds 8
```

Choose the CUDA architecture appropriate to your GPU. The measured host was an RTX 2000 Ada (`sm_89`). The binary is written only to `research/eta2_champion/build/prism-eta2`.

For a registered target and an independently auditable endpoint:

```bash
python3 research/eta2_champion/run.py \
  --problem /path/to/problem.txt \
  --target YOUR_FIXED_TARGET \
  --seconds 8 \
  --state-out /path/to/endpoint.state
python3 research/eta2_champion/bench/audit_prism_state.py \
  /path/to/problem.txt /path/to/endpoint.state
```

Replace `YOUR_FIXED_TARGET` with a positive cost. The auditor additionally requires NumPy. Inspect the exact flags using `run.py --problem /path/to/problem.txt --dry-run`. Validate source/header hashes without compiling using `build.py --check-only`.

The launcher clears inherited experimental solver variables and applies `champion.json`: single-shift coupled LM, initial lambda 0.1, sustained CG forcing multiplier 2, radius control, point safeguard, compact mixed storage and numerical Schur recovery. Lambda adapts during the solve. Learned policy, multishift menu and periodic retriangulation are disabled. This experiment uses SIMPLE_RADIAL with k2 fixed to zero.

## Findings and evidence

- [Latest frozen comparison](docs/speed_novelty_results.md): 153 measured runs on Ladybug-539, Trafalgar-138 and Final-394; three quality tolerances and N=3 per configuration. Prism was fastest among evaluated configurations in all nine scene/tolerance comparisons, with 27/27 target hits. Caspar FP32 reached 16/27 and FP64 21/27; both Ceres CPU arms reached 27/27.
- [Protocol](docs/speed_novelty_protocol.md) and [comparison figure](docs/figures/convergence/frozen_new_instances_time_to_target.png).
- [Curvature novelty assessment](docs/curvature_novelty_assessment.md): numerical recovery did not activate before the practical targets. The separate late-stage diagnostic does not establish an incremental fixed-target speed benefit from curvature sizing. No claim of universal fastest BA or proven curvature novelty is made.
- [Champion selection](docs/rl_sustained_results.md), [earlier recovery ablations](docs/schur_recovery_results.md), and [numerical diagnosis](docs/model_followup_results.md).
- `results/` contains frozen targets, exact input URLs/hashes, configurations, per-run results, timing summaries, the late diagnostic and the archive manifest. `results/summary.csv` retains misses; a median is supplied only for 3/3 target hits.

The exact measured binary SHA256 is `1e3d2cf22a8a43075114e0ca2024923dad330461e35d0074938d0412cd77ecc0`. `source_manifest.json` verifies the source and all 44 headers. A different compiler/toolchain may produce a different binary hash; no binary is committed here.

`bench/` preserves the original study harness for provenance; those scripts retain the originating machine's absolute artifact paths. They require path relocation and the pinned Caspar builds to rerun the complete experiment elsewhere. The portable entry points for the champion are `build.py` and `run.py`. `provenance/` also preserves the actual recovery-control source and instrumented Ceres driver used in the new comparison.

Large datasets, binaries and raw-state archives are excluded from Git. On the originating machine, the verified GPU evidence archive is `/workspace/prism-speed-novelty-gpu.tar.xz` (36 exact states), and the full archive is `/tmp/prism-speed-novelty-evidence.tar.xz` (198 exact states). Archive hashes and scope are in `results/persistent-archive-manifest.json`. These local paths are provenance, not downloadable GitHub resources.

## Publication scope

Every addition in this publication belongs under `research/eta2_champion/`. The existing algorithm can continue to be built and run through its original entry points. This package is not a promotion of the champion to the default solver.
