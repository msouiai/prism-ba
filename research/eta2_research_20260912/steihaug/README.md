# Boundary-truncated PCG prototype

Status: CPU algebra, GPU metric memcheck, tiny BAL memchecks, and N=3
source-off compatibility passed. No performance grid has run. This is
Brief 3's isolated implementation, not a new champion. Read the
[protocol draft](PROTOCOL_DRAFT.md) for the one candidate and its limitations.
Completed checks are in [FINDINGS.md](FINDINGS.md).

`build.py` verifies the frozen source and all headers, applies
uniqueness-checked substitutions, and reverses them to verify original-source
parity. `OCA_STEIHAUG=0` (or absent) takes the original arithmetic branches and
allocates no STCG GPU storage. Compiler trajectory parity still needs a
same-binary disabled-arm gate. Source/defaults outside this folder are untouched.

Build and CPU verification:

```bash
python3 research/eta2_research_20260912/steihaug/build.py
OPENBLAS_NUM_THREADS=1 python3 research/eta2_research_20260912/steihaug/test_linear.py
python3 research/eta2_research_20260912/steihaug/test_attempt_trace.py
```

`boundary.h` is the same shared host routine used by the CUDA solver and the
CPU test. The tests compare against dense linear solves and whitened-coordinate
CG, verify boundary/model properties, exercise true indefinite and positive-but-
cutoff matrices, and sample 1000 scalar boundary roots over large scales.
They do not assume exact-arithmetic M-norm monotonicity survives roundoff:
the SPD interior test records a 3e-9 relative late-iteration decrease, which
is why direct Gram products are used.

GPU correctness commands, **only after coordination**:

```bash
nvcc -O2 -std=c++17 -arch=sm_89 research/eta2_research_20260912/steihaug/test_metric.cu -o research/eta2_research_20260912/steihaug/build/test-metric
compute-sanitizer --tool memcheck research/eta2_research_20260912/steihaug/build/test-metric
```

The metric test uses the actual GPU kernel, nontrivial lower triangular blocks,
NaNs in unused upper triangles, a partial CUDA block, and a long-double CPU
reference. Then run the campaign's tiny BAL fixture under compute-sanitizer
with all champion flags plus `OCA_STEIHAUG=1`; check every accepted `STCG` row
has `norm <= radius*(1+1e-8)`. The full performance protocol remains the parent
campaign's responsibility.

`check_gpu.py metric|toy|compatibility` reproduces the authorized correctness
checks, hashes inputs/binaries/flags before each run, audits the saved full
objective, and acquires `/tmp/prism_gpu.lock` separately for every GPU run.
It is not a performance-grid launcher. The frozen `run.py` scrubs unknown
OCA flags, so setting `OCA_STEIHAUG` outside that launcher will not enable
this arm; construct the explicit environment as `check_gpu.py` does.

`STCG` rows record outer, retry, termination reason, attempted CG depth/cap,
untruncated next-iterate M-norm when known, actual evaluated camera M-norm,
radius, nonlinear acceptance, cumulative metric wall and Gram calls. Reasons:
0=interior/cap, 1=radius boundary, 2=finite curvature-cutoff boundary,
3=invalid arithmetic retained current iterate. `ATTR_RADIUS` retains its
field names, but its norms/radii are M-norms in this arm; `raw_norm` is the
terminal STCG iterate, not a hypothetical uncomputed unconstrained solution.
No extra matvecs are spent estimating discarded iterations.

For both arms set `OCA_STCG_ATTEMPTS=<path>`. The common RAII host timer
covers complete attempts, including numerical-repair continues, with no
additional GPU barriers or candidate evaluations. It records PCG iterations,
all Schur products, acceptance, curvature events and numeric restarts, and
writes rows plus totals at solver exit. `retry_entry_wall_fraction` counts
work on entries reusing the unchanged state; `not_accepted_wall_fraction`
counts work whose attempt was not accepted, including numeric restarts.
The trace's total excludes setup and final cleanup but its buffering/output
overhead remains in the solver's native wall measurement. Do not enable
`OCA_LEARN_LOG` for timed rows: that older logger adds blocking norm work.

The scalar radius is reinterpreted in the rebuilt preconditioner's metric on
each attempt. This is an explicit variable-metric policy, not a transported
fixed physical radius. In particular, this arm cannot by itself distinguish
an improvement due to the norm change from boundary truncation or removal of
the persistent numerical floor.
