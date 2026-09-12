# C1 protocol: graph observability before a local prior

Registered before computing any effective-resistance score on a BAL scene.
This stage is diagnostic only.  It does not change the frozen Eta2 champion,
its stopping rules, or the scored objective.

## Graph and scores

Duplicate camera--point incidences are collapsed.  A point observed by `m >= 2`
cameras contributes a clique whose edge weight is `1 / (m - 1)`.  Thus each
track contributes unit weighted degree to each camera that sees it, rather than
letting a long track contribute `m - 1` times as much as a short track.  The
resulting camera Laplacian is `L`.

The primary global observability score is `diag(L+)`, the diagonal of the
Moore--Penrose inverse.  Its ranking is also the ranking of a camera's mean
effective resistance to all other cameras, because

`sum_j R_eff(i,j) = n * L+_ii + trace(L+)`.

For each connected component, `diag(L+)` is estimated with 256 deterministic
Rademacher edge projections, seed 630001:

`y = L+ B^T W^(1/2) q`,  `diag(L+) ~= mean_q y^2`.

A grounded sparse factorisation is reused for every right-hand side and each
solution is centred to zero mean.  Isolated cameras are reported separately.
On Venice-52, where a dense pseudoinverse is cheap, the estimator must achieve
Spearman rank correlation at least 0.90 and median relative error at most 20%
against the exact diagonal before results on larger scenes are interpreted.

The local graph statistics are observation count, unique-track count, tracks
of length at least three, mean track length, unweighted covisibility degree,
normalised weighted degree, and unweighted k-core number.  A single sparse gate
is fixed in advance:

1. effective-resistance score in the top 1% of cameras, including ties only by
   stable camera-index ordering; and
2. either normalised weighted degree or k-core number at or below its scene's
   25th percentile.

The gate therefore touches at most `ceil(0.01*n_cam)` cameras (which can be
slightly more than 1% as a fraction for finite `n_cam`).  No threshold is
retuned by scene.

## Scenes and discriminating predictions

The scenes are evaluated in this order:

1. Ladybug539, the requested first locality screen;
2. Final3068, the count-starvation positive control;
3. Venice52, the geometric-starvation negative control;
4. Dubrovnik88, a calm small-scene control.

The primary positive prediction is that Final3068 camera 550 lies in the gate
and in the top 1% by effective resistance.  It has only 13 unique tracks versus
a scene median of 314.5 and carries 82--99% of the recorded high-ratio witness
step norm.  The secondary check reports ranks for every camera in the three
recorded witness top-five sets; it is descriptive and cannot replace the camera
550 prediction.

Venice camera 34 is expected not to enter the gate.  It has 2,959 tracks and its
weak mode is the geometric focal/optical-axis-translation ambiguity, which a
visibility graph cannot observe.  Treating this miss as expected is registered
before seeing the graph score.  Ladybug539 and Dubrovnik88 test whether the gate
remains sparse and whether selected vertices really occupy the weak tail of
both global and local connectivity.

## Decision

The graph gate is considered validated for a native prior only if:

- the Venice estimator validation passes;
- Final3068 camera 550 is selected;
- selected cameras are at most `ceil(0.01*n_cam)` on every scene; and
- Venice camera 34 is not selected.

If camera 550 is selected but its resistance rank is indistinguishable from its
unique-track-count rank, the result supports a cheap count gate but provides no
evidence that effective resistance adds information.  A native prior then uses
the count gate as the simpler actuator.  If camera 550 is missed, no graph-fed
prior is built.  If Venice camera 34 is selected, the count/geometric distinction
is revisited before any intervention.

Any later camera prior is a separate, preregistered native experiment.  This
diagnostic alone cannot support a speed, quality, or novelty claim.

## Arithmetic clarification after the first scene

Ladybug539 has `ceil(0.01 * 539) = 6` cameras, or 1.113% as a fraction.  The
original prose said both the exact ceiling rule and "at most 1%".  The latter is
impossible under the former for most finite camera counts.  Before evaluating
the positive or negative controls, the decision rule is clarified to use the
already registered integer ceiling.  No threshold, score, selected camera, or
prediction changed.
