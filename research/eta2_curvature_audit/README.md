# Eta2 same-state curvature audit

**The three audited Venice52 curvature failures are caused by rounding the
camera–point cross blocks to FP32.** Replacing only those blocks with FP64
values makes the same directions positive while state, camera blocks,
point factors, camera scaling and damping remain fixed. This is a numerical
diagnosis, not a new optimizer or a measured speed improvement.

Read [FINDINGS.md](FINDINGS.md) for the comparison, mechanism, point-level
localization and limits. [PROTOCOL.md](PROTOCOL.md) was registered before
captures at commit `d2dbfa5`; diagnostic implementation was committed at
`db4d351`. The previous 76-run depth-rescue experiment remains unchanged.

## Reproduce

CUDA, Eigen and Python/NumPy requirements match the frozen Eta2 package.
The build verifies the original source/44 headers and the already-tested
depth-rescue generated source against its published hash. That source must
exist at `../eta2_depth_rescue/build/prism_depth.cu`; the evidence archive
preserves it. Alternatively the old depth-rescue build script regenerates it.

```sh
python3 research/eta2_curvature_audit/build.py
python3 research/eta2_curvature_audit/run.py
python3 research/eta2_curvature_audit/analyze.py
python3 research/eta2_curvature_audit/verify_rounding.py
python3 research/eta2_curvature_audit/localize.py
```

The capture runner uses `/workspace/bal/venice-52.txt`, exact inherited flags,
and a native diagnostic binary. It stops after the first curvature cutoff
inside the de-clipping probe and compares several operators at that same
state/direction. Captures include all matrix components, original and
alternative products, exact matrix state, analytic Jacobian rows, metadata,
stdout and hashes. Array data are preserved in the archive, not Git.
All compute and audits serialize under `/tmp/prism_gpu.lock`.

The analysis uses extended-precision accumulation and triangular solves
(`np.longdouble`, 64 significand bits here), and checks a nonnegative
Jacobian-energy formulation. It independently scores the exported state
against the original observations in CPU FP64. Jacobian rows themselves
come from the existing analytic GPU routine; this experiment is not a new
finite-difference validation of that routine.

`localize.py` is a post-hoc description of the worst rounding contributors,
not a point-ID-based correction policy. Existing completed captures are
not overwritten. Use a new evidence directory for additional repetitions.
No state updates, damping/radius recovery policies or precision changes are
committed by the diagnostic. Do not use these instrumented runtimes in a
performance comparison.
