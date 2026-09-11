# Ceres setup sensitivity: registered bounded check

The primary frozen-binary study continues unchanged. This is a separate,
exploratory comparator check motivated by a source audit after the Final3068
primary target stage. No Eta2 configuration or primary target is revised.

The Ceres 2.2 full BAL example normalizes scene coordinates, sets gradient,
function and parameter tolerances to 1e-16, and exposes eta with default 0.01.
The frozen minimal driver does not normalize and retains Solver::Options
default tolerances and eta. These are distinct configurations; neither this
check nor radius-only development tuning establishes globally optimal Ceres.

Primary sources (pinned to the installed Ceres version):
- https://github.com/ceres-solver/ceres-solver/blob/2.2.0/examples/bundle_adjuster.cc
- https://github.com/ceres-solver/ceres-solver/blob/2.2.0/examples/bal_problem.cc

Final3068 only, fixed target 1744796.9841897595 already registered from the
original Ceres dogleg median before this check. N=3 per arm: run the control repetitions first, then alternate the other four arms,
600 iterations, 60 native seconds, 180 process seconds. New explicitly hashed
instrumented driver linked to the same installed Ceres. LM / iterative Schur /
Schur-Jacobi, initial radius 10000, eight threads, original observations and
k2 fixed to zero throughout. Five arms:

1. control: original minimal-driver options, no normalization.
2. normalize: only the scene-coordinate normalization is added.
3. strict_stop: only the three termination tolerances become 1e-16.
4. normalize_strict: both changes, original inner eta.
5. normalize_strict_eta01: both changes, and eta=0.01 as in the full example.

Normalization centers points by their coordinate-wise upper medians and
scales their median L1 deviation to 100. Camera centers receive the same
similarity transform. The transform is a change of world coordinates, not a
change to observations or the intended objective. Store its parameters and
verify objective invariance numerically before solving. Return endpoints to
the original world coordinates and independently audit compact exported
states using original observations. Preserve all failures and misses.

The target callback tests only accepted states. Native time cap and target
termination are instrumented; setup, normalization/audit and export are
outside native solve time and separately visible in the process/setup data.
Callbacks also stream accepted/rejected traces so a process failure does not
silently erase all prior observations. Exported states must pass the same
independent FP64 audit tolerance of 1e-6; no invalid hit is counted.

First validate that the new control retains the original initial objective
and reproduces the old LM endpoint regime (relative endpoint difference below
0.1% for the three control repeats). If it does not, preserve results and
investigate the adapter before attributing arm differences to configuration.
Do not pool these timings or endpoints into the old frozen Ceres N=3 medians.
Build, audit and time the entire stage under the shared measurement lock.
This is a bounded sensitivity screen, not a claim of best possible Ceres or
a replacement for the independent GPU baseline tier.
