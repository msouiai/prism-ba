# Fixed covisibility projection pre-test

This feasibility proposal preceded the parent registration in `../../PROTOCOL_01_GRAPH.md`. Its subsequent execution is reported separately in `FINDINGS.md`. The previous geometric negative applies to its measured basis: a K8 partition containing 3,058 of 3,068 cameras in one cluster is not evidence against a balanced covisibility coarse space.

## Available dependency

No local METIS executable, METIS/SCOTCH shared library, `metis`, or `pymetis` module was present. NumPy, SciPy and NetworkX were present. The parent authorized an isolated installation of the 275,908-byte PyMetis2025.2.2 CPython3.12 manylinux wheel; its SHA256 is `e355cd0de2ee17e50f8022970727c7edc98a56136f2db6d623c632b6e7150a96`. It is installed only in `../../build/deps/graph-pretest-pymetis-2025.2.2` relative to this directory, with wheel/source URL, installed file hashes and synthetic API verification under `dependencies/`.

The weighted CSR API supports integer edge weights, vertex weights and explicit runtime options. The installed binding accepts all proposed options, reports int64 index/weight storage, and reproduces a two-clique synthetic partition in three identical repeats. No fallback graph algorithm is needed. [PyMetis functionality documentation](https://documen.tician.de/pymetis/functionality.html), [pinned package metadata](https://pypi.org/pypi/pymetis/2025.2.2/json).

## One frozen graph rule

Use the original Final3068 BAL observation camera and point IDs, independent of witness state, residual values, camera locations, targets or measured missing directions. Let B be binary camera–point incidence: repeated observations of the same point in a camera contribute one incidence to this graph only. All original observations remain in the solver's scored objective. Form integer W=B Bᵀ, clear its diagonal, retain every positive edge. Thus W_ik counts distinct shared points exactly; there is no edge threshold, geometric truncation, track reweighting, or observation dropping.

Partition the same graph once for each requested K in {8,32,128}, capped at ncam, and reuse its labels on all three Final witnesses. Use unit camera weights, k-way weighted edge-cut minimization (`recursive=False`, `objtype=CUT`), equal target weights, `ncuts=1`, `niter=10`, `ufactor=30`, `seed=20260912`, `contig=0`, `numbering=0`. These are one set of options, not a seed or balance sweep. Canonicalize output labels by each part's minimum camera ID; this changes names only. Pin the wheel and record all options because a fixed random seed does not imply identical partitions across different METIS versions.

Disconnected graphs are passed unchanged with contiguity disabled. Do not add connecting edges or drop isolated cameras. Report connected components, isolates, empty parts and actual balance. If METIS returns an invalid or empty part, retain the failure and do not repair the partition silently. K=ncam is the deterministic singleton case. Integer rounding can prevent exact equal sizes, so report actual min/median/max and the complete size vector rather than assert a continuous balance ratio is attainable.

## Matched projection and gauge handling

Reuse the verified native-retraction finite-difference basis, column scaling/rank rule, captured E and camera-step sign conventions in `../diagnostic.py`. Change only the cluster labels. Read each saved reference repetition and report the same three differences: raw reference minus actual Eta2, equally clipped reference minus actual Eta2, and raw reference minus raw Eta2. Compare against preserved geometric results for the same capture/K/reference. N3 here means arithmetic/reference repetitions; it is not three independent nonlinear trajectories.

Report the total projected norm fraction and the legacy after-global-removal fraction for direct comparison. Additionally compute an explicitly gauge-free coarse projection. Let Q be the blockwise orthonormal coarse basis, G the existing orthonormal global similarity basis, and T=QᵀG. The orthogonal projector onto range(Q) intersect range(G)⊥ is

    P_free = Q [I - T (TᵀT)^† Tᵀ] Qᵀ.

Evaluate it on delta_free=(I-GGᵀ)delta, using the same relative SVD rank tolerance1e-10 for T. Only an at-most-seven-column coefficient matrix is required; do not materialize a dense 9n-by-7K matrix. Report removed rank, global containment error, residual gauge leakage, original difference norm, gauge-removed norm and fraction. Compare the same explicit projector for graph and geometric labels, leaving all original legacy numbers intact. Global similarity is a geometric invariance, not an exact null space of the damped camera Schur system. If the graph is disconnected, separately flag that seven global modes do not remove independent component similarities; do not interpret such coverage as resolved physical coupling without a component-gauge audit.

Final witness0's raw/equally clipped missing directions are extremely small. Retain original near-zero policy and norms, but explicitly mark this known case as numerically sensitive even when it lies just above the formal machine-epsilon threshold. Do not turn a large fraction of negligible missing work into a mechanism claim.

## Graph and memory diagnostics

Report weighted edge cut, total edge weight, graph edge count, unique incidence count, collapsed duplicate count, components/isolation, partition size distribution and rank per camera/extrinsic dimension. To match the existing ~395 cross-observation figure, assign each point the cluster of its first observation in original BAL order and count observations whose camera cluster differs. Also report all observations on tracks seen by multiple clusters. These two observation counts differ from weighted clique-edge cut and must not share a label.

Use int64 SciPy sparse multiplication for exact shared-point counts. For this pre-test ncam=3068 bounds the full adjacency to9.41million entries. Check a conservative memory estimate before multiplication and stop with a resource diagnostic if it exceeds the registered budget; never sparsify to fit. Keep graph/basis arrays in RAM, save compact labels/counts/hashes/JSON only. One CPU thread; partition/basis/projection/loading/hash costs and peak RSS are reported. No GPU, native solver, objective change or speed claim is involved.

## Synthetic verification before witnesses

Verify exact weighted incidence against explicit distinct-point enumeration (including duplicate observations); weighted cut against explicit pair sums; disconnected/isolated graph handling; deterministic same-seed repeat labels; known global-gauge and nongauge coarse vectors; gauge-free projector symmetry/idempotence/orthogonality; and agreement with a dense null-space reference on a small fixture. Hash the original frozen source/44 headers and imported diagnostic before any comparison.

The resulting pre-test can establish that a sensible graph basis captures missing camera directions. It cannot establish spectral improvement, model usefulness, reduced rejects, target hits or speed. A native graph-coarse arm remains a separate decision after mechanism evidence.
