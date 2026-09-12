# ROS2 witness reference

Brief 12 is **parked after a failed registered gate**: 27/27 valid CPU rows, one gain/work win and two losses versus two coherent fixed-chart LM steps. [Findings](FINDINGS.md) contain the full comparison and mechanism.

This directory implements a two-RHS ROS2 step over a coherent full normal operator, with stable point QR and dense camera Schur factors. The complete fixed-chart interpretation, including SO(3) gradient transport and combination-preserving point completion after camera clipping, is in [INTERPRETATION.md](INTERPRETATION.md). It does not modify the frozen solver.

From the repository root:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python3 research/eta2_research_20260912/rosenbrock/verify.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python3 research/eta2_research_20260912/rosenbrock/run_witnesses.py
```

The runner verifies pinned baseline/config, protocol, source and input hashes; it resumes existing rows without rerunning them. [results/ledger.csv](results/ledger.csv) is the compact table; [results/rows.jsonl](results/rows.jsonl) retains raw and feasible proposals, acceptance, linear certificates and work; [results/manifest.json](results/manifest.json) pins provenance. Costs use all original observations and k2=0. CPU timings are not GPU speed estimates.
