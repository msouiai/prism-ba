# Calibrated initialization stress test

Registered before input calibration and solver measurements, 2026-09-10.
Test the frozen conservative CG marginal-value rule against the sustained eta2
champion. Same binary: /tmp/prism-cg-value/build/prism-tr, SHA256
02ec2ea9e479e5752dde95fdf80799924c41488c564e67c454f0c46357fca8a7.
Both use initial lambda0.1 and fixed eta multiplier2. Candidate adds OCA_CGV=3.
No tuning, observation noise, fresh Caspar runs or large-scene extension here.

Scenes: Trafalgar126, Dubrovnik356, Venice89. Fixed original-objective targets:
105579.58394455544, 731369.19169166, 306319.16867216 respectively. Each solve
has4 native seconds and600 outers. Audit targets against full original FP64
SIMPLE_RADIAL observations with k2 forced to zero, as in the preceding study.

## Input construction

Keep original observation bytes, camera intrinsics, dimensions and observation
graph unchanged. Perturb only camera rotations/centers and point coordinates.
Use seeds17,29,43. For each seed draw one Gaussian direction: additive
angle-axis coordinates with base sigma0.001 radians, camera-center and point
coordinates with base sigma0.001 times median centered point radius. These
rotation perturbations are coordinate additions, not claimed isotropic SO(3).
Reconstruct translation t=-R*C after perturbing rotation and center.

Scale that same direction separately to give full initial reprojection RMS
ratios1.10 and1.50 (equivalently objective ratios1.21 and2.25). Calibrate against
the original objective only, without running an optimizer. Start amplitude
bracketing at0.125 and double up to64; then50 bisection steps. A change in any
observation's depth sign or nonfinite projection is an invalid upper bracket.
Fail input preparation visibly if a valid requested level cannot be reached;
do not resample a seed. Calibration relative RMS tolerance1e-6. Record actual
amplitudes, costs, projection displacement percentiles and depth-sign changes.
This equalizes one measure of starting difficulty, not conditioning or basin.

Verify original observation-byte hashes and unchanged intrinsic values on every
serialized variant. Recompute cost after reloading the written file. Clean
controls reference the untouched original file. Inputs are generated before
any performance run, hashed and frozen. Original files are never overwritten.

## Paired execution and scoring

Three scenes x (one clean + two levels x three seeds) x two arms x three timing
repeats =126 runs. Seeds represent initialization variation; timing repeats
do not count as extra seeds or independent scenes. Deterministically shuffle
the seven cases within each scene/repeat and alternate first arm. Locally
serialize GPU runs via /tmp/prism_gpu.lock. Disable diagnostic GPU probes and
per-iteration learning logging; retain existing native traces and CG counters.

Every run must match its calibrated initial cost within1e-7 and pass an
independent original-observation FP64 endpoint audit within1e-7. A target hit
requires an actual native TARGET event within4s and audited endpoint <=target.
Keep cap misses and stalls. Report each seed's N3 median/min-max separately,
target-hit counts first, then paired target-time speedups where both arms hit
all repeats. Withhold an all-case geometric speedup when any pair has misses;
conditional summaries must state their coverage. Also report endpoint costs,
outer iterations, rejects, matvecs, extra stops and numerical-repair fallback.

600 total native-second ceiling. No retries of failed performance measurements,
extra seeds, noise levels, target relaxation or post-result tuning. Candidate
remains experimental; this panel tests robustness rather than automatically
promoting a default. Store bulky inputs/states under /tmp/prism-cg-value-noise
and preserve compact source/manifests/traces/results under /workspace.
