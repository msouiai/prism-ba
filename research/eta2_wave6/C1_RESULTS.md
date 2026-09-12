# C1 result: graph observability works, but count explains the target case

## Registered verdict

The effective-resistance diagnostic passes every registered check, but it does
not earn a place in the native solver.  It correctly selects Final3068 camera
550 and correctly does not select Venice camera 34.  For camera 550, however,
the resistance rank is 8/3,068 and the ascending unique-track-count rank is
7/3,068.  On the four scenes the rank correlation between log resistance and
negative log track count is 0.849--0.976.  The expensive global statistic adds
no failure-linked information over the cheap count statistic in the case this
experiment was designed to explain.

| Scene | Cameras | Graph edges | Resistance/count Spearman | Selected / ceiling | Selected cameras |
|---|---:|---:|---:|---:|---|
| Ladybug539 | 539 | 41,132 | 0.849 | 6 / 6 | 488, 509, 522, 523, 528, 529 |
| Final3068 | 3,068 | 989,046 | 0.976 | 31 / 31 | includes 534, **550**, 3041 |
| Venice52 | 52 | 1,296 | 0.971 | 1 / 1 | 41 |
| Dubrovnik88 | 88 | 3,335 | 0.976 | 1 / 1 | 51 |

The finite-size ceiling is `ceil(0.01*n_cam)`, so six of 539 and one of 52 are
slightly more than 1% when written as fractions.  This arithmetic ambiguity was
clarified after Ladybug and before the two registered controls; no score or
threshold changed.

## Estimator validation

On Venice52, the 256 deterministic edge-projection estimate was compared with
the dense exact Moore--Penrose inverse:

- Spearman rank correlation: **0.9725** (registered minimum 0.90);
- median relative diagonal error: **4.59%** (registered maximum 20%);
- worst relative error: 23.34%;
- exact and estimated top-one camera: both camera 41.

The weighted-degree construction also passes its identity check: because a
track clique has edge weight `1/(m-1)`, each linked track contributes exactly
one weighted degree to every observing camera, to floating-point rounding.

## What the scores explain

Final3068 camera 550 is the positive control.  It has 13 tracks versus a scene
median of 314.5, is selected by the gate, and previously carried 82--99% of the
raw step norm in the three high-ratio witnesses.  Cameras 534 and 3041, two
other low-count witness leaders, are selected as well.  Ordinary-count weak
directions such as cameras 853 and 2816 are not selected, which is consistent
with the graph measuring combinatorial support rather than local projective
conditioning.

Venice camera 34 is the negative control.  It has 2,959 tracks, ranks only 13th
by resistance, and is not selected.  Its measured weak mode mixes focal length
and optical-axis translation, so visibility alone cannot reveal it.  This
confirms the registered distinction between count starvation and geometric
starvation.

There is some graph information beyond counts on scenes without a linked Eta2
failure.  Ladybug cameras 528 and 529 rank fourth and fifth by resistance while
ranking 289th and 271st by track count; both sit in low-degree, low-core parts of
the sequence.  Dubrovnik camera 51 ranks first by resistance and ninth by count.
These are valid structural bottlenecks, but this campaign has no evidence that
regularising them improves an Eta2 trajectory.

## Consequence

Do not add the 256-projection resistance estimator to the production path.  Its
Final3068 analysis alone takes about six seconds on the CPU, longer than Eta2's
typical time to the registered target, and it reproduces a track-count rank that
is available at load time.  The mathematical diagnostic is useful: it validates
camera 550 as a graph-starved vertex and rules out graph starvation as the
Venice mechanism.  It does not support an algorithmic or novelty claim.

The next local-prior experiment, if run, should use a preregistered fixed count
gate.  It must begin with a fixed-state Final3068 witness test because wave 3
already showed that other local damping/capping rules can identify a weak camera
and still worsen the nonlinear trajectory.  No native prior was selected or
tuned from these graph results.

Machine-readable reports are `c1-*.json`; the compact verdict is
`c1-summary.json`.  Synthetic checks are in `c1-verification.json`.
