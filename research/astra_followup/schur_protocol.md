# Track A3: residual-informed Schur enrichment

Registered before results. Use the *existing* frozen native Muell outer11->12
and Ladybug598 outer7->8 captures, plus Final1936 outer0 with no predecessor.
These are prior development systems, not held-out data. Reuse the exact frozen
Eta2 matrix-free kernels, normalized coordinates, mixed FP32 coupling storage,
FP64 reductions, block preconditioner and captured RHS/forcing threshold.
No nonlinear trajectories or new captures are needed. The adviser proposed a
CPU diagnostic; existing captures allow a more relevant bounded GPU replay.
Serialize under the GPU lock; no other timed experiments overlap.

Generate the predecessor's last32 normalized PCG directions once per repetition,
using the previous reference solver's cap128 and true-residual gate. This is a
shared parent-history acquisition, reported separately. Current arms all start
at zero, so a restart-only arm at activation is identical to plain PCG; no
mid-recurrence basis change occurs. The available basis may be from an unfinished
previous solve, as in the original negative recycling study.

Current-system arms: plain PCG; rank2/4 old previous-system Euclidean Ritz;
rank2/4 current generalized smallest-theta; rank2/4 current generalized modes
with largest w=(z'b)^2/theta. For the latter two, refresh all32 retained SV
columns (or the actual smaller count), including this full cost. Build
G=V'MV using the actual incumbent M=L L' after its numerical Cholesky safeguards,
not an assumed unmodified camera block. Whiten G after rank truncation at
1e-10 of its largest eigenvalue, solve current K=V'SV in that metric, and
reject nonpositive/ill-conditioned selected coarse systems. Form the balanced
inverse Q+(I-QS)M^-1(I-SQ), fixed throughout PCG. Current RHS selects modes,
never future iterations or endpoint cost.

Every arm uses the unchanged reference PCG cap128 and true residual test.
Report current setup+solve wall seconds, native event time, iterations, all
Schur products (refresh plus true-residual verification), selected rank,
captured forcing, actual residual and misses. Full-basis selection is an
expensive oracle, not a cheap live rank4 method. Refresh work cannot be hidden
behind advertised rank. The deep-history>=16 gate is retained for shallow
controls, with skipped activation reported.

One warm-up plus N=3 rotated arms. Current preconditioner construction and all
host transfers/eigensystems are inside wall timing; predecessor acquisition and
capture I/O are reported outside and are common to current-arm comparisons.
Stop unless setup-adjusted >=1.10x benefit survives against both plain PCG and
old Ritz on the deep Muell case without extra misses, and shallow cases skip
cheaply. If even the current-system oracle fails, do not implement a live
selection policy or rerun a native full-scene suite. Budget <15 minutes GPU
replay including checks; compact logs and mode diagnostics only.
