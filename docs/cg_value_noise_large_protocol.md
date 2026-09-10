# Largest BAL initialization stress

User explicitly requested Final13682 after the small-scene stress test. This
separate extension is authorized despite the earlier automatic extension gate
having failed; it does not change the earlier verdict or promote a default.

Frozen binary /tmp/prism-cg-value/build/prism-tr, SHA256
02ec2ea9e479e5752dde95fdf80799924c41488c564e67c454f0c46357fca8a7.
Champion: initial lambda0.1 and sustained eta multiplier2. Candidate adds
OCA_CGV=3. Original SIMPLE_RADIAL L2 observations, k2 fixed zero, unchanged
intrinsics, original target27591576.557625167. No Caspar or observation noise.

One clean case plus mild initialization noise at seeds17,29,43, each at1.10x
the original full initial reprojection RMS. Same perturbation directions as the
small-scene generator: base Gaussian sigma0.001 per angle-axis coordinate,
and0.001 times median centered point radius per camera-center/point coordinate.
Reconstruct translations t=-R*C. This is additive angle-axis coordinate noise,
not isotropic SO(3). Original observation bytes and camera intrinsics preserved.

CPU calibration uses all observations in chunks of250000. Bracket amplitude
from0.125, doubling to at most64. A changed observation depth sign or nonfinite
projection is an invalid upper bracket. Use a safeguarded secant step when
both bracket costs are finite; clip its bracket fraction to[0.1,0.9], otherwise
bisect. Stop at relative RMS error <=1e-7 or50 steps; require final error<=1e-6.
No optimizer is used in calibration. Fail visibly rather than resample seeds.
Report median/p95/max image displacement because full RMS can be dominated by
a small set of fragile observations and is not a universal difficulty measure.

Generate and verify all inputs before any performance runs. Freeze input,
binary, generator, protocol, baseline flags, driver and audit hashes. Check
observation bytes, intrinsics, calibrated serialized cost and depth signs.
Original input remains untouched. No parameter tuning after observing results.

Four inputs x two arms x three timing repeats =24 runs. Deterministically
shuffle inputs in each repeat and alternate first arm. Serial GPU lock at
/tmp/prism_gpu.lock. Native cap20s and600 outers per run, process timeout180s
for loading/export. Total native ceiling550s. Diagnostic GPU probing and
learning logs disabled. Independently audit every endpoint on original FP64
observations (<1e-7 relative error), and compare native initial cost with CPU
calibration (<1e-7). Hits require native TARGET within20s and audited endpoint
<=target. Preserve misses and stalls; no target relaxation or extra runs.

Report each input's N3 median/min-max, hit count, endpoint gap, outers, rejects,
matvecs and CG-value interventions. Withhold a finite all-case speedup if any
case misses in either arm. Seeds are initializations, not extra timing repeats
or independent scenes. No population-level robustness claim.

Bulky inputs/states in /tmp/prism-cg-value-noise-large. Compact durable source,
binary, manifests, logs and traces under /workspace. No production changes.
