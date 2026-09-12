# Registered native K8 additive prototype

Implementation of [PROTOCOL_01_NATIVE.md](../../PROTOCOL_01_NATIVE.md), derived
from the checksum-pinned Eta2 source. The original source and 44 headers are
verified on every build and never edited. Inverting the seven source overlays
recovers the frozen source byte-for-byte.

Current executable: `build/prism-coarse`; SHA256
`17ee0fad5a7c50636cb840976dc5ff43a046c4e5510a497769c5a69e0720c534`.
Exact compiler flags and local header hashes are in [build_manifest.json](build_manifest.json).

## Runtime rule

`OCA_COARSE=1` enables the experiment. All ordinary champion flags, CLI settings
and the scored objective remain the same. It activates at the first attempted
solve with at least eight accepted outers, last accepted relative decrease
below 1e-3 and current lambda below 1e-3. Activation is sticky. Memberships are
chosen at activation with deterministic farthest-point/Lloyd center clustering,
K=min(8,ncam), and remain fixed. Current centers, orientations and E rebuild
the native Sim(3) basis at every active attempt. CPU local SVD removes dependent
columns with normalized-column relative cutoff 1e-10; singleton scale columns
are omitted. Intrinsic basis rows remain zero.

The additive application is `BJ^-1 r + Z Ac^-1 Z^T r`. Ac uses the current
**production** Hcc, compact FP32 cross fragments, FP64 point triangular factors,
E and lambda. No coherent-reference operator is substituted. Coupled damping
means every active attempt rebuilds Ac, including retries.

One GPU warp gathers each point's actual observing clusters. A triangular solve
forms its small Gram contribution; a shared-memory accumulator and bounded
partial reduction produce Ac. No AZ or npoint-by-coarse buffer is allocated.
The point partial buffer is capped at 512*1596 doubles (6.54 MB); the local basis
uses 63*ncam doubles. The largest coarse matrix is 56-by-56. CPU clustering,
current geometry/SVD, transfers, sparse assembly, CPU Cholesky and GPU upload
are all inside `Prepare` and native solve wall. Each application performs GPU
restriction, small triangular solves and prolongation.

Nonfinite geometry, nonfinite/non-SPD Ac or a failed enabled parity oracle leaves
ordinary BJ active for the **entire attempt**, with a recorded fallback reason.
There is no extra damping floor, eigenvalue repair, matrix cache or Krylov reuse.

`OCA_COARSE=0` is the same-derived-binary off arm. `OCA_COARSE_ORACLE=1` streams
the unchanged native product through all coarse columns for an Ac parity check;
this is expensive diagnostic work and **must be unset/zero for a performance
panel**. It stores only one native vector/product at a time, not AZ. The default
deployed implementation uses direct point-cluster assembly.

## Attempt accounting

`OCA_ATTEMPT_TRACE=1` logs each attempt for both on and off arms, including
numeric-recovery continues and attempts terminated by target/budget checks.
`ATTEMPT_SUMMARY` reports:

- all native Schur products and the products inside the PCG loop separately;
- host native-attempt duration, without extra device synchronization;
- failed/rejected-attempt wall fraction;
- wall fraction of attempts whose retry index is greater than zero separately;
- numeric-recovery attempts.

The two retry fractions answer different questions and are not interchangeable.
The host timer includes the normal synchronous acceptance/BLAS operations; it
does not pretend to be a CUDA-kernel profiler. Setup wall is reported by
`COARSE_PREP`/`COARSE_SUMMARY`. `apply_enqueue_seconds` explicitly measures host
launch overhead only; full GPU application time is included in native solve
wall, not inferred from this enqueue timer. No standalone CPU/GPU setup split
has yet been profiled. Oracle products are counted and separately identified.

## Correctness and compatibility results

All evidence is in [evidence/correctness/](evidence/correctness/).

The synthetic native-kernel test uses **extracted unchanged** frozen
MFPass1/MFVinvApply/MFPass2 kernels, compact slot mappings, repeated camera/point
interactions, multi-cluster points and one unobserved point. Under memcheck:

| Check | Result |
|---|---:|
| Rank | 52 |
| Sparse Ac vs streamed native product | 1.70e-16 relative |
| Sparse Ac vs independent dense Schur | 2.03e-16 relative |
| Additive application vs dense reference | 2.36e-16 relative |
| Bilinear symmetry discrepancy | 2.22e-16 |
| Linearity discrepancy | 7.84e-16 |
| Tested preconditioner energy | 14.7625, positive |
| Deliberate indefinite-matrix fallback | Passed, unchanged BJ output |
| Memory errors / leaked bytes | 0 / 0 |

The real four-camera toy BAL also passes memcheck in both arms. It naturally
activates at outer 29 with rank 24, but at lambda=1e-16 its actual production Ac
is non-SPD. All 19 active attempts correctly use BJ fallback; oracle relative
errors remain below 4.7e-16. This is a production-operator limitation at that
state, not a sparse-assembly mismatch. Its sanitized setup times include the
oracle and are not deployed-runtime evidence.

N=3 Dubrovnik88 original-versus-derived-off compatibility, alternating order:

| Arm | Median endpoint | Native time median [range], seconds |
|---|---:|---:|
| Frozen original | 358945.5450 | 0.427965 [0.412103, 0.435607] |
| Derived off | 358944.6364 | 0.417811 [0.412264, 0.430155] |

Endpoint difference is -0.000253%, well below the standing 0.15% material-cost
threshold; timing ranges overlap. All runs use 33 outers. These are compatibility
results, not an active-coarse improvement or speed claim.

An initial bitwise-equality check of score_init failed: independent GPU
reductions differed by 4.88e-16 relative. The failed first summary is retained
as `compatibility_summary.json`. The separate
`compatibility_summary_scaled.json` states this discrepancy and its explicit
1e-10 roundoff budget. No run was discarded or repeated to improve agreement.

CPU geometry tests compare the compiled closed-form basis to the independently
verified finite-difference module. Normal-scale projector errors are at most
5.2e-12; an artificial world origin at 1e10 yields 2.13e-6 and rank 28 after the
registered dependence cutoff. All-coincident and singleton cases are covered.
This exceptional coordinate sensitivity is recorded in
[geometry_verification.json](geometry_verification.json).

## Reproduction and next boundary

```bash
python3 research/eta2_research_20260912/coarse/native/build.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 research/eta2_research_20260912/coarse/native/test_geometry.py
python3 research/eta2_research_20260912/coarse/native/build_toy.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 research/eta2_research_20260912/coarse/native/run_correctness.py
```

The correctness runner acquires `/tmp/prism_gpu.lock` per GPU run and reuses
already recorded rows. Parent coordination is still required for new GPU work.
No practical or tail efficacy panel has been run by this module. The original
champion remains the current winner pending the registered comparison.
