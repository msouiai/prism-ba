# BAL collective-correction follow-up

Registered before collecting new comparison outcomes. Parent geometry agenda
commit e121e914b79aa3b632f76c402f50a6aac8969344. Original solver/defaults remain
unchanged; this is the six-DOF FP64 CPU mechanism reference.

Question: did the earlier greedy 24-camera samples suppress the collective
geometry, and does exact internal-projection invariance make the coarse
operation cheap enough to help on BAL-derived problems?

Use the same three original parent captures: Ladybug49, Dubrovnik88, Venice52.
Keep **all original cameras**. Sample points with RNG seeds60,61,62, up to
1,200 points each. First ensure twelve distinct valid tracks incident to every
camera, then fill uniformly from remaining valid points observed at least twice.
If coverage exceeds1,200, retain it and record actual size. Retain every original
observation of each selected point, no per-camera clipping. Exclude an entire
point only for an initially nonfinite/nonnegative-depth observation, recording
counts and exact indices. Camera0 and point0.z are common gauge constraints.
These are new sampled problems, not full original BAL or nine-DOF GPU runs.

Targets: for each packed input, ordinary LM120 attempts/8 seconds supplies a
feasible reference; freeze Fref+1e-3*(F0-Fref) before any comparison. Record
reference stopping/cap, never call it a global optimum. Use2e-5 gap only as an
optional secondary trace threshold, not a replacement primary target.

Arms: ordinary BA; eight full-objective linear coarse steps; eight original
nonlinear coarse steps; eight nonlinear steps evaluated on bridges plus the
constant internal cost; and a predeclared selective bridge-only schedule.
All coarse arms use the same automatic confidence-weighted partition and
return to identical ordinary BA. Selection uses current initial data only:
cross-cluster observation fraction<=.25, cross-cluster residual-energy
fraction>=.25, at least3 cameras and20 points per group. If the gate fails,
skip coarse motion, charging partition/feature setup. Do not tune thresholds
from measured times. No robust loss or hidden observation removal.

All arms get80 fine attempts/5 seconds total, including partition, all coarse
derivatives/candidates, diagnostics and final full-objective verification.
N=3, rotated order. No competing CPU/GPU benchmark runs during timing. Record
time to identical target, final cost, accepted/rejected fine attempts, coarse
steps, target hits, signed-depth validity, setup and total time. Keep failures.
After the first nine problem comparisons, do not expand automatically unless
there is a consistent>=1.10x gain with no extra misses. No endpoint quality
win claim from overshooting the target by a small amount.

The bridge-only solver must first pass equivalence tests against full residual
costs/Jacobians and exact nonlinear candidates on controlled and packed real
inputs. Internal invariance does not justify omitting internal residuals from
the *linear* coarse objective. Whole parent states are immutable. Numerically
degenerate coarse metrics trigger a recorded failure and ordinary fallback.

Publication/claim scope: this shortcut follows directly from submap invariance,
not a claim of new mathematics. Its incremental total-time value is unmeasured
until the matched arms complete. No GPU Eta2/Caspar claim from these CPU rows.
