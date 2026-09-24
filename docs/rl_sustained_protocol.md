# Sustained forcing confirmation

Registered after the actor discovery panel, before this confirmation. Candidate:
the frozen actor binary, no learned policy, initial lambda 0.1, and
`OCA_RLA_FIXED_ETA=2` (twice the existing adaptive CG tolerance, capped at 0.5).
Incumbent: same binary with the extension disabled; initial lambda 10 on Muell,
0.1 elsewhere. These incumbent initializations were established before the actor
study. Other flags, acceptance checks, precision and objectives remain matched.

This is a new configuration comparison, not a retroactive pass of the actor
study's five-setting gate. Fixed eta2 at lambda10 lost badly on Muell and remains
a documented counterexample. The candidate is a fixed numerical configuration,
not an RL result or a novelty claim.

Primary: fresh alternating N=5 pairs on Trafalgar126, Final1936, Muell146 and
Final13682, at the unchanged fixed targets from the actor protocol. Additional
N=3 pairs on Final871 and Venice951 use targets 1953211.7798859142 (8s) and
2019363.9492517712 (12s), copied from the earlier expanded10 protocol. These two
scenes were excluded from current policy fitting and tuning, but were used in
earlier solver research. No pristine-holdout claim.

Sensitivity: N=3 largest-scene pairs at the tighter historical anchor
27318392.631312046, cap20s. Primary target remains 27591576.557625167.
Fresh N=3 Caspar32 and Caspar64 references at the primary largest target;
FP32 requests 0.999 times target, as in earlier studies, and must pass the same
CPU FP64 original-observation endpoint audit. Disclose this conservative buffer.

Report every arm's median [min,max] native target seconds, audited cost, outers,
rejects, matrix products and hits. Exclude loading, export and CPU audits from
native timing; report Caspar graph setup separately. No interpolation of target
crossings. Report six-scene geometric mean with equal scene weight, plus the
tighter-target check separately. All targets must hit; a useful candidate should
gain at least 10% geometrically without any scene losing over 10%. Small timing
differences alone are not meaningful. N=3/5 repeats establish repeatability on
these scenes, not population certainty.

Hard ceiling 400 cumulative native seconds, 600 outers per run, 180s process
timeout on largest, 45s otherwise. Serialize GPU via flock. Freeze binaries,
input hashes, protocol and code before execution. Save endpoints and manifests
under /tmp/prism-rl-sustained, compact evidence under /workspace when quota allows.
