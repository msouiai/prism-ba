# Terminal coarse oracle

See [FINDINGS.md](FINDINGS.md): the registered practical gate fails on all three
Final3068 witnesses, so no further nonlinear collective rollout follows.

Example reproduction for one complete CPU repetition:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 research/eta2_research_20260912/coarse/oracle/run.py \
  --capture research/eta2_research_20260912/evidence/collect/final-3068-capture-0 \
  --bal /workspace/bal/final-3068.txt --rep 0 \
  --output research/eta2_research_20260912/coarse/oracle/results/final-3068-0-0.json
```

The runner refuses to overwrite an existing result. Repeat for witnesses 0, 5,
6 and repetitions 0–2. `report.py` requires every registered row, validates
operator/model/score checks, and writes `ledger.csv` and `summary.json`.
No GPU or full dense camera matrix is used; intermediate arrays stay in RAM.
