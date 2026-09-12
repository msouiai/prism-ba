# Passenger-cluster coarse diagnostic

CPU reference for `../../PROTOCOL_09_NONLINEAR.md`. It is separate from the
Schur-eliminated `../oracle` experiment and from the frozen native solver.

From the repository root, first run:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/eta2_research_20260912/coarse/nonlinear/test_model.py
```

Then run `run.py --capture CAPTURE --bal BAL --rep REP --output NEW_JSON` with
the same thread settings. Registered cells are Final3068 captures 0,5,6 and
repetitions 0,1,2. Results are append-only; existing outputs are refused.
`report.py` requires all nine rows and writes the complete ledger and findings.

The metric is the joint camera-plus-passenger pullback, held fixed for three
attempts. There is no point elimination and no restriction from the fine
radius. Every full objective score evaluates every original observation.
The diagnostic reports CPU wall including setup and all backtracking scores.
No files in the source captures or frozen solver are modified.
