# Rigid-cluster camera projection diagnostic

This implements the CPU geometry/projection part of [Brief 0](../PROTOCOL_00.md).
It does not implement a coarse preconditioner, run an optimizer, modify the
capture, or establish a target hit. Frozen champion source/header hashes are
verified before reading each capture.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 research/eta2_research_20260912/coarse/test_diagnostic.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 research/eta2_research_20260912/coarse/diagnostic.py CAPTURE_FOLDER --output research/eta2_research_20260912/coarse/audits/capture.json
```

Requires NumPy and SciPy. Existing output files are not overwritten. Input and
output hashes and capture metadata make each result independently traceable.
No CUDA libraries or inherited `OCA_*` variables are consulted.

## Input interface

All binary arrays are little-endian FP64, with the exact element counts below.
Metadata is one `key=float` per line and must include integer-valued `ncam`
and `npt`. The expected captures already contain these files:

| File | Shape / convention |
|---|---|
| `R_state.f64` | `(ncam,3,3)`, world-to-camera rotation |
| `t_state.f64` | `(ncam,3)`, world-to-camera translation |
| `X_state.f64` | `(npt,3)`; validated but not used in camera projection |
| `intr_state.f64` | `(3,ncam)`, focal, k1, k2; k2 must be zero |
| `E.f64` | `(ncam,9)`, positive scaling satisfying `dc=E*z` |
| `eta2-0.step` | Full native tangent, `9*ncam+3*npt` elements |
| `eta2_raw_scaled.f64` | `(ncam,9)`, **positive** CG solve vector; physical raw camera step is `-E*raw` |
| `exact-N.step` | Full native tangent, all available reference repetitions |
| `exact_clip-N.step` | Matched full native tangent after radius clipping and point recovery |
| `native_directions.csv` | Optional certification records, copied into the output per repetition |

Missing paired reference files, size errors, nonfinite values, improper
rotations, nonpositive E, or nonzero k2 produce explicit errors. Missing
certification is recorded as missing, not interpreted as success. The script
validates point array sizes/values but does not evaluate residuals or certify
that observations match; use the main Brief-0 audit for that.

## Fixed geometry and rank policy

Requested K is always 8, 32, 128, capped at ncam. Initialization starts with
the center farthest from the mean, then repeatedly chooses the farthest center
from existing seeds. Lowest camera index resolves ties. Lloyd iterations stop
when labels stop changing, with a cap of 100. Empty clusters receive the
farthest member of a nonsingleton donor, again with deterministic index ties.
Coincident centers therefore remain deterministic and every cluster is
nonempty. K=ncam directly assigns one camera per cluster. Actual K, membership,
sizes, convergence and empty-cluster repairs are reported.

Each cluster gets world rotation, translation and log-scale modes about its
centroid. The finite world action transforms centers and orientations together;
the native tangent is recovered using `Log(R_new R_old^T)` and additive
translation differences. The identical translation increment is evaluated in
algebraically factored form to avoid subtracting enormous absolute translations;
this matters for outlying Final3068 cameras. Central differences use epsilon=1e-5. Its derivative
is compared with the independent closed form, including `dw=-R*omega`.
Intrinsic modes remain zero.

Z is `E^-1 Zraw`. Each disjoint camera block has only seven columns. Column
normalization precedes rank-revealing SVD so arbitrary mode units do not decide
rank; the cutoff is 1e-10 times the largest normalized singular value. The
output contains both raw and normalized singular values, column norms and the
retained rank. Singleton scale modes are dropped. The blockwise orthogonal
projector is mathematically equivalent to the full block-diagonal projector;
no large dense QR or Schur matrix is built.

## Output interpretation

For every reference repetition and K, the output reports three differences:

- `exact_minus_eta2`: exact raw camera step minus the actual inexact Eta2 step.
- `exact_clip_minus_eta2`: equally clipped reference minus Eta2.
- `exact_minus_eta2_raw`: exact raw camera step minus Eta2's raw camera step.

All use the captured scaled-camera metric `||E^-1 dc||_2`. Fractions are
orthogonal projected norm divided by total norm, not squared energy fractions.
Differences smaller than `100*machine_epsilon*max(reference_norms,1)` are
labelled negligible with an undefined (`null`) fraction. Extrinsic and
intrinsic norms are separate because the basis has no intrinsic directions.

Global geometric similarity modes are retained as required by the protocol,
but their separate projection and the fraction after global-mode removal are
also reported. These are not exact null modes of the damped Schur operator.
Finite-difference error in global-span containment is recorded. The remaining
projection uses the full cluster span after subtracting the global component;
it is not a new separately constructed gauge-free preconditioner.

On Venice52, K=128 becomes 52 singleton clusters, usually rank 312: all six
extrinsic coordinates per camera. A high fraction there can be a trivial
consequence of a nearly complete extrinsic basis. It is not evidence for a
cheap useful coarse level. Strong projection at K=8, after global-mode removal,
is the more informative mechanism evidence. Neither proves time-to-target gains.

The registered kill rule concerns **all** valid witnesses and K values. These
outputs do not automatically promote an experiment or pool reference repeats
as independent nonlinear runs. CPU diagnostic times are reported for
reproducibility, not compared with native solver runtime.

## Verification

[verification.json](verification.json) records finite-difference/native-sign
checks, first-order retraction error scaling, exact global projection invariance,
deterministic ties/empty clusters, block-versus-dense projection, expected
singleton/global ranks, intrinsic orthogonality, raw-CG sign interpretation,
and capture immutability. These are synthetic CPU checks, not BAL results.

## Spectral and full-normal supplements

[SPECTRAL_FINDINGS.md](SPECTRAL_FINDINGS.md) reports the registered first-Venice
K=8 symmetric Lanczos/dense-spectrum check, retained failed combined gate, and
separately measured camera parity. `spectrum.py` adds Hcc/Cdiag and the original
BAL observations to the input interface; `test_spectrum.py` independently checks
the Schur and spectral algebra. Outputs in `spectra/` must not be mistaken for
the projection schema in `audits/`.

The parent's follow-up authorized CPU point back-substitution completion at
the three fixed Venice camera directions. `refined/` holds separate `.step`,
normal-residual metadata and full-objective reports. `evaluate_refined.py` uses
the existing unmodified witness evaluator. Original capture files are never
replaced. [NATIVE_ADDITIVE_DESIGN.md](NATIVE_ADDITIVE_DESIGN.md) is the proposed
next implementation, not an executed solver or selected winner.
