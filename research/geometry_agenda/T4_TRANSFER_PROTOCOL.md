# T4 conditional follow-up registration

The controlled held-out gate passed: nonlinear coarse speed is 1.79x/1.53x
fine-only and 1.46x/1.21x same-basis linear on weak/strong bridges. Proceed to
automatic partition and size transfer before treating the result as general.

New seeds 200–209, 3 repetitions, weak/strong bridge settings. First repeat
12 cameras / 180 points, then 30 cameras / 900 points (10 cameras, 300 points
per cluster as suggested by the brief). Same targets, 2-second total cap,
opening eight-step schedule. Arms: fine-only, known-linear, known-nonlinear,
automatic-linear, automatic-nonlinear. Charge automatic setup within total time.

Partition algorithm is frozen before outcomes: build a camera affinity from
Frobenius norms of diagonally camera-normalized off-diagonal Schur coupling
blocks, using undamped point pseudoinverses (relative eigenvalue cutoff 1e-10).
Spectral normalized-graph embedding into three dimensions, deterministic
farthest-point k-means, at most 30 iterations. Assign each unique point to the
cluster with greatest sum of normalized camera–point coupling. Relabel the
camera0 cluster as zero; point0 is kept in that fixed cluster for the common
scale gauge. No truth/known partition is used by this algorithm.

Record partition agreement only as an external diagnostic, never as an input.
For successful transfer, require >1.10x speed against fine-only and automatic-
linear, no additional misses/geometric failures in both bridge settings.
Only a passing result justifies a sampled real-scene follow-up.
