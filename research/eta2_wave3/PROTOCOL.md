# Wave 3 registration: starved cameras and local actuators

Registered 2026-09-12 before wave-3 diagnostics or scores, against wave-2
commit 1cdd80a and the frozen Eta2 source/configuration. Follow the user's E1–E5
brief in order of its gates. No scored objective, champion default, or excluded
global policy changes. Native comparisons require the frozen source/header and
binary checks, original/off compatibility N=3, independent FP64 full-objective
rescoring, identical targets, N=5 tails and N=3 nine-cell practical panel.

Targets: Venice52 243740.27; Final3068 1744796.9841897595. Practical cells are the
unchanged wave-2 nine cells. Fresh cohorts stay separate. A 0.15% cost threshold
and disjoint empirical timing ranges are descriptive verdict gates. Preserve
both improvements and regressions; overhead is included.

E1: original three Final3068 and three Venice captures, Ladybug1197 healthy
witness, all five static-damping Venice terminal reconstructions, and fresh
opening rejected-step captures where old point snapshots were not retained.
Report observation counts, distinct >=3-observation tracks, mean track length,
all camera block eigenvalues, top-five raw camera norm shares, scaled eigenvector
loadings, explicit f/t_z loading, and signed one-dimensional cost scans out to
10 saved radii. Block spectra use the same point damping at each state.
For reproducibility use independent coherent FP64 Jacobians and point QR,
and separately include the native intrinsic model regularizer. The blocks are
diagnostics of the mathematical operator, not a claim of bit-identical native
fragment assembly. Check symmetry and a direct local residual Gram construction.

Critical coordinate qualification: the stored ninth coordinate is inactive k2.
Report its zero eigenvalue but use the eight active coordinates for starvation
tests and regularization. Otherwise every camera appears unobservable by design.
Compare count ratios to the camera median ("far below" = <0.25 of median), and
smallest active eigenvalue to the median smallest active eigenvalue (<0.01).
Report both predicates, not a forced binary classification. A dominant f/t_z
direction requires >50% combined squared scaled loading and >5% in each.
Fixed-point cost scans and point-completed scans must be labeled separately.

E2 witness screens: cap factors 3,10,30; local and global-scale spectral floors
epsilon 0.001,0.01,0.1. Recomplete points after every changed camera direction;
compute prediction on the actual full step. Report the intermediate capped norm
before any remaining global clip, camera IDs touched, and unaffected-camera
preservation. A remaining global clip does change healthy cameras; eigenvalue
regularization can also change their solution through Schur coupling. The brief's
bit-identical statement applies to local operator blocks or the cap transform,
not generally to the final coupled solution.

Select at most one parameter per family before native scores: exclude choices
touching >5% of cameras at the healthy Ladybug1197 witness, then maximize the
number of tail witnesses with true decrease above matched clipping and
intermediate norm/R <=2; break ties by fewer touched cameras, then weaker
regularization (larger cap factor or smaller spectral epsilon). If none survives,
record the kill and do not disguise the broad action as local. Each surviving
family is tested without the opening first. Stop promotion on >5% touched at a
healthy native scene, Venice <=2/5, or >=5 disjoint practical losses.

E3 opening grid is finite: eta 0.05/0.1/0.2, rejection window 1/2/3 accepts,
with tight forcing for the whole window or only until first accept (deduplicate
the one-accept cases). Match the frozen off and prior eta0.05/3-accept policy.
Run Venice N=5, then >=4/5 survivors on the full practical panel; a candidate
must keep >=4/5 and <=1.01 geometric-mean time ratio. Select lowest panel ratio,
then fewer disjoint losses; confirm selected rule in a fresh cohort. Repeat with
cap only if a local cap survives E2. No per-scene flags chosen after the grid.
E3 intrinsic gating is conditional on E1's explicit f/t_z test.

E4 compare accepted trajectories, not merely outer indices. Distinguish old
traces from complete state captures. No deterministic "miss seed" claim unless
reduction-order control actually reproduces the miss; otherwise use fresh N>=5
cohorts and report conditional witness evidence separately. Point-fixed camera
ratios and full joint model error are different quantities. E5 feedback remains
gated on an E2 result near ratio2 and Venice >2/5 without opening.

Storage: RAM is scratch only. Retain compact diagnostics and source on disk;
do not launch a scored grid unless durable endpoint/evidence capacity is secured.
Any reduced new snapshot retention is specified before its collection. Existing
unique evidence is preserved. Lower-priority arms that cannot run remain pending,
never labeled refuted.
