# Full-normal cubic witness screen

Brief 7 is parked: **0/3 required >20% mechanism wins**, nine valid N3 matched pairs, and almost identical projected LM/ARC decreases. [FINDINGS.md](FINDINGS.md) reports both directions, work and residual limitations.

[INTERPRETATION.md](INTERPRETATION.md) fixes the full-D whitening, projected cubic equation, saved-step sigma rule, matching control and no-clipping semantics before data. [verification.json](verification.json) contains the tiny shift-family, dense cubic, whitening and 64-vector checks. This module reads existing coherent reference APIs but changes no native solver or other module.

From the repository root:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python3 research/eta2_research_20260912/arc/verify.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python3 research/eta2_research_20260912/arc/run_witnesses.py
```

Existing rows require `--resume` and matching source/protocol hashes. Do not overwrite the verification file before resuming a banked run: its hash is part of the manifest. The complete sources and input hashes are in [results/manifest.json](results/manifest.json), paired traces in [results/pairs.jsonl](results/pairs.jsonl), and compact rows in [results/ledger.csv](results/ledger.csv). No arrays are persisted. CPU timings are diagnostic, not estimates of GPU time-to-target.
