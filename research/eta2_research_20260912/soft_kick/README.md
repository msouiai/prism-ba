# One terminal soft-mode kick

The native prototype is correctness-ready for the parent's registered grid.
There is **no efficacy result here yet**; frozen Eta2 remains the current
winner. The runtime flag is `OCA_SOFT_KICK=0/1`, off by default, and the binary
is `build/prism-soft-kick`.

The solver derives one K8 gauge-free generalized coarse Ritz mode only after
a reason-tagged FTOL stop survives the champion's existing confirmation
policy. It rebuilds at the stopped state, uses the actual PCG metric, completes
points homogeneously, and scores one bounded-energy ray. A permitted temporary
uphill move resumes ordinary LM with current damping, radius, numerical floor
and forcing history. The final output retains the better of the pre-kick and
continued full states. Details are fixed in [PROTOCOL_11](../PROTOCOL_11.md)
and [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md). The older feasibility
proposal records source-hook reasoning; its open choices are superseded by
the registration and implementation notes.

Build and correctness commands, from repository root:

```sh
python3 research/eta2_research_20260912/soft_kick/build.py --check-only
python3 research/eta2_research_20260912/soft_kick/build.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python3 research/eta2_research_20260912/soft_kick/run_correctness.py
```

The runner uses `/tmp/prism_gpu.lock` for every GPU process. Compilation uses
`/dev/shm/prism-soft-kick-tmp` for temporary files; executable outputs stay in
this module. The build manifest pins the original source, 13 exact reversible
substitutions, local and reused headers, protocol and binary. Existing native
geometry/assembly kernels are read-only dependencies; no additive coarse
preconditioner is enabled and no frozen source/default is edited.

Set `OCA_STCG_ATTEMPTS=/absolute/run/attempts.json` in both timing arms for the
exact common lightweight attempt ledger. It covers fresh assembly, retries,
numerical continues and the kick probe. A probe row has zero PCG iterations
and `accepted=false` as an **ordinary LM** acceptance field. That is not a
rejected nonlinear step when the kick is admitted. `SOFT_KICK_ATTEMPT` records
its explicit trace index, outcome and freshness/history assertions. Use:

```sh
python3 research/eta2_research_20260912/soft_kick/parse_trace.py RUN/attempts.json RUN/stdout.log --out RUN/trace_audit.json
```

The parser excludes identified probe rows from ordinary failed-LM work,
reports intervention work separately, retains raw retry-entry statistics,
and checks that ordinary accepts and all matvecs match native totals. The
first fine continuation after a kick has `need_assembly=true`, so it is not
an unchanged-state retry. The legacy log may contain an initial FTOL marker
that was subsequently intercepted; do not treat presence of any such marker
as proof of the final termination reason.

`OCA_SOFT_KICK_ORACLE=1` is a correctness-only switch adding all-basis native
operator comparisons and charging their products. Leave it unset in timed
runs. The artificial FTOL=1,K=1 tiny fixture is likewise correctness-only.

[CORRECTNESS.md](CORRECTNESS.md) reports the checks and retained initial
harness failures. Performance, target hits and any continuation verdict belong
to the parent-owned registered grid, not to these smoke tests.
