# Bounded native additive prototype: proposed implementation

This is an implementation recommendation for the parent agent to register,
not an executed optimizer experiment. Start with K=8 and the additive map

`z = M_BJ^-1 r + Z (Z^T A Z)^-1 Z^T r`.

Keep the production operator, point factors, forcing rule, damping, radius,
retraction and rescue unchanged. In particular, the coherent CPU reference
used by the spectral audit must not replace the champion's mixed-storage
production A. The deflation spectrum establishes motivation, not the spectrum
of this different additive preconditioner.

## Basis and lifecycle

Use the already verified native Sim(3) tangent and deterministic K=8 center
clustering. A simple single global rule is to choose cluster membership once
from the initial cameras, update centroids and tangent values on each accepted
outer, and transform by the current E. This rule differs from the witness
screen's fresh terminal clustering and must be stated as such. Alternatively,
repeat the exact terminal-screen clustering every outer and charge its cost;
do not switch between these choices after observing scene results.

The finite-difference module verifies the closed form; runtime uses the closed
form with 9-by-7 local camera blocks and zero intrinsic rows. Normalize each
cluster's columns and use the same rank-aware local orthogonalization. A
singleton has six modes; cap K at ncam and omit zero modes. No dense 9n-by-7K
basis storage is needed: store each camera's cluster index and local block,
plus at most a 7-by-7 transformation per cluster. With K=8 there are at most 56
coarse coordinates. Report ranks and all basis overhead.

For a first correct prototype, CPU local SVD of a cluster's tall seven-column
matrix is acceptable only with transfer and assembly times charged. GPU small
Gram/QR implementations need a rank/parity check because squaring the basis
condition can change rank. An optimization should follow a correctness gate,
not be mixed into the first scientific A/B.

## Coarse matrix without retaining AZ

Use **the exact same** stored cross fragments Gp/Gc, Hcc, current E and current
point triangular factors Rf that native `Kv` uses. Let physical local basis
blocks be `B_i=E_i Z_i` and gather, per point,

`T_j = sum_observations W_ij^T B_i`.

T_j has seven columns per distinct observing cluster, capped at 56. The small
matrix is

`Ac = sum_i B_i^T Hcc_i B_i + lambda Z^T Z - sum_j T_j^T V_j^-1 T_j`.

The Hcc term already contains the native intrinsic solve prior; do not add it
twice. With zero intrinsic modes its direct contribution vanishes, but preserve
the source term in parity checks. Point damping is coupled to lambda: factors
and Ac must refresh whenever effective damping changes on a retry. No frozen-Ac
or factor-reuse shortcut is part of this first prototype.

For numerical consistency, form each point subtraction as a Gram matrix of a
triangularly solved T_j, with the orientation verified against native
`MFVinvApply`. This changes only coarse assembly, not the production operator.
Gather point observations with the existing point CSR and explicitly honor the
fragment-slot layout. Duplicate observations must accumulate into the same
camera/point or cluster/point block rather than be deduplicated.

A point rarely touches every cluster. Exploit its actual cluster list and
assemble only the corresponding `(7*k_j)` block; do not unconditionally form
56-by-56 contributions for every point. Bounded shared-memory work per point
or a small point batch avoids storing a 3*npoint-by-56 buffer. Reduction order
and atomic overhead remain measured implementation costs. A first version can
be slower; it must still report the entire setup cost.

A streaming application of the native operator to all 54–56 columns is useful
as a **correctness oracle** for Ac, never as a hidden free setup. At Venice0
the champion used one CG iteration: fifty extra Schur products per attempt
would defeat the purpose. Compare direct assembly against streamed `Z^T A Z`
on a tiny synthetic case and the first witness before any timing grid. Do not
retain AZ in the additive path.

## Application and fail behavior

Leave the existing two camera triangular solves intact. Add one segmented
`Z^T r`, one at-most-56-dimensional SPD solve and one local `Z*u` addition.
Keep this map fixed within one PCG solve. CPU solves synchronized every CG
iteration would impose avoidable overhead; use an on-device small Cholesky and
triangular solve or a library path with its launch costs measured.

The mixed-storage A can lose positive definiteness near problematic tails.
If Ac is nonfinite or its Cholesky fails, report the failure and use ordinary
block-Jacobi for the **whole attempt**. Do not silently add a new diagonal
floor to Ac or change lambda. Register this fallback before comparison; it is
a run-everywhere numerical policy, not scene selection. Existing numerical
guard behavior and original champion remain frozen.

## Minimal implementation gate

1. Feature disabled: identical source path, hashes and target behavior to the
   frozen baseline; the experiment lives in an overlay/branch.
2. Feature enabled on a toy: Ac agrees with direct native Z^T A Z; additive
   application agrees with a CPU dense reference, remains linear/symmetric and
   positive when Ac is SPD, and does not change k2.
3. First Venice0 witness: rank, Ac symmetry/factorization, setup/apply time,
   PCG residual and actual full-objective proposal. Repeat source point
   residual qualifications; a better linear direction need not be nonlinear
   useful at Venice1.
4. Only then the parent's single registered global rule and N>=3 target grid,
   including screens where the coarse projection was poor. Report crossings
   in both directions and all setup/CPU-transfer overhead. Do not infer a
   large-scene crossover from this one 52-camera witness.

This is established multilevel/deflation machinery applied to a specific
matrix-free inexact-LM architecture. Prior-art overlap and the limited possible
novelty are in [the mathematical audit](../literature/MATH_AND_PRIOR_ART.md).
