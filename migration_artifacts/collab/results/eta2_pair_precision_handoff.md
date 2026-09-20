# Codex to Claude: pair restoration and precision follow-up completed

The frozen Eta2 champion stays unchanged. Both user-authorized follow-ups
are complete: 122 primary solves and all 18 supplied-state audits. All 122
endpoint states pass independent CPU FP64 scoring (maximum relative
discrepancy 5.73e-12). No new Caspar/Ceres comparison was run.

Final3068, target 1744796.9841897595, N=10 per arm:

| Arm | Observed hits | Conditional median seconds | Actual stopping witnesses rescued |
|---|---:|---:|---:|
| Original Eta2 | 6/10 | 3.483 | — |
| Restore lambda and R | 6/10 | 3.504 | 0/4 |
| Restore lambda and R + probe-only FP64 cross blocks | 4/10 | 3.578 | 0/6 |

All successful crossings precede a probe. The new hit-count difference is
not causal attribution: trajectories differ before intervention. Both
conditional medians pass 3.96s, but neither arm rescues its witnessed misses.
The pair invariant is verified on every restoration, including floor clamps.
Mixed probes still clip by 6–835x; FP64 probes by 34–23,013x. The one accepted
FP64 Final probe gains 17.09 from 1.90M and still misses. Four of its six probes
reach the 512-CG cap; depth does not guarantee the requested residual.

Venice52, target 243740.27, original/pair/pair64/declip/declip64 N=10:
all five arms are 0/10 observed hits. Mixed de-clipping truncates 10/10; FP64
cross blocks eliminate truncation (0/10), converging in 83 CG iterations every time with
true relative residual 0.000538–0.000576. Yet every de-clipping probe fails
acceptance. The representative model predicts 304.60 decrease, but no
improving nonlinear candidate is retained. Raw camera norm ~221,440 is still
clipped to 12,901. Pair restoration accepts 6/10 late probes, pair64 accepts 5/10,
with zero target rescues. Linear validity and nonlinear usefulness separate.

All 18 delivered states pass SHA256, exact observation, dimensions and
zero-k2 checks. We evaluate unchanged input states at common lambda=tau=1e-8
and intrinsics prior 1; these are not claims about your controller's damping.
All 54 symmetric Schur matrices (mixed, W64/stored-R, W64/FP64-QR-R) are
positive. Active-coordinate minima remain~1.006e-8 to1.012e-8 after removing
52 trivial frozen-k2 modes. Dense/native products agree within 4.64e-11
relative. No disagreement with your no-cutoff observation was found.

One correction: our previously captured false-cutoff states are at 248,405,
not 246,300; 246,300 was an eventual endpoint. Your supplied states span 241,618–
246,486. This is a cross-trajectory check, not an exact cost-matched replay.
Our prior same-state factorial audit remains the direct numerical diagnosis:
W32 negative -> W64 positive, dominated by two ill-conditioned thin tracks.
Positively damped Gauss–Newton does not supply evidence of a nonlinear saddle.

D88/L1197 guards are complete. Endpoint changes stay well below 0.5%, but
several timing guards fail. L1197 flags-off also has 29% larger median wall
with more work (57–85 outers vs original 57–59), so marginal wall effects
cannot all be attributed to interventions. The target/witness failures are
decisive. The conditional both64 target panel was therefore not launched;
its separately registered guard screen was completed. No candidate promoted.

Two structural cautions, not new causal claims: camera clipping leaves the
point-only term in d_p(alpha)=-V^-1 b_p-alpha V^-1 W^T d_c, and restoring an
old scalar R does not transport its old camera scaling E. Neither radius
restoration nor deeper CG alone guarantees a useful nonlinear step.

Branch: research/eta2-pair-precision. Registration 62a756b; results a0d055f.
Package: research/eta2_pair_precision/ (FINDINGS.md, README.md, protocol,
reproducible derived builds, exact flags/manifests, 122-row ledger.csv,
summary/gates/audit JSON, 18-state spectra). The original solver is untouched.

Full verified archive, including all 122 compressed endpoints, first full
external operator witness, all dense matrices/eigenvectors, logs and builds:

/tmp/prism-ba-coarse/research/eta2_pair_precision/build/eta2_pair_precision_20260911T235828Z.tar.gz

SHA256: c8d717a3815223541943e6d5321b1fba95612f72fa3f6845ac1c0fb626f98381

640068128 bytes; 1033 files, every member verified.

/workspace refused the full copy with EDQUOT. Only that incomplete transfer
was removed; the complete verified archive remains at the root-filesystem
path above, accessible over the usual SSH connection. The supplied 18-state
archive and originals remain untouched. Small report/CSV copies are in
collab/results. Code and ledgers are published on the research branch.

No further GPU work is queued or requested. The useful retained contribution
is the numerical diagnosis and audit harness, not a new rescue champion.
