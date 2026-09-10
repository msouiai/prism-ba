# Final-13682 transfer of the frozen deep-CG policy

User-authorized extension after round6 completed. It does not alter that study's
failed promotion decision or train on this scene. Register before fresh solves.

Input: /workspace/bal/final-13682.txt, SHA256
76ef34416fdca524b1ec6755b62ab33cba15c8b5b830b5ff38369c8cd609d736.
13,682 cameras, 4,456,117 points, 28,987,644 observations. Original SIMPLE_RADIAL
L2 objective with k2 fixed zero. No initialization or observation perturbation.
Fixed historical target: 27,591,576.557625167 (half sum of squared pixel residuals).

Both arms use /tmp/prism-rl-deep-eta2/build/prism-tr, global initial lambda0.1,
sustained eta multiplier2 capped at0.5, and unchanged selected baseline flags.
Champion: no learned policy. Learned: the exact full policy from round6, verified
against its frozen analysis hash and copied locally before use. No fitting,
parameter adjustment, target relaxation, or alternative policy selection.

N3 per arm, alternating first arm in each pair. Native cap20s, outer cap600,
process timeout180s (loading/export excluded from native time). Local GPU lock
/tmp/prism_gpu.lock; host2237c6528e79 / RTX2000 Ada. Detailed policy logging off
for six headline timing runs. One additional learned diagnostic, same target and
caps with logging on, excluded from timing medians. Total native ceiling150s.

Every exported endpoint independently audited against original FP64 observations
with relative discrepancy <1e-7. Target hits require a native TARGET event within
20s AND audited endpoint <=fixed target. Report N3 median[min,max], cost, gap,
outers, rejects and matvecs. No finite speedup if either arm misses a repeat.
Report damping actions from the separate diagnostic, including repeated positive
corrections and CG depths. Curves show recorded steps, not interpolated crossings.

Preserve binary, policy, dataset, driver and protocol hashes before measuring;
reverify afterward. Keep raw endpoint states, logs and manifests under
/tmp/prism-rl-deep-eta2-large; persist a compact archive under /workspace.
No new Caspar runs; any older comparisons must be explicitly historical.
No production defaults changed. One scene cannot overturn the prior multi-scene
generalization failures, even if this transfer is successful.
