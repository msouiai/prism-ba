# Depth-graft handoff — Codex, 2026-09-11

Completed the requested tests: **76 native runs**, all endpoint states checked
against fixed observations in independent CPU FP64. Frozen Eta2 remains the
champion; neither proposed one-shot graft passes its improvement gate.

- Final3068 at 1744796.9841897595, fresh N=10: original **6/10**, stop-depth
  **7/10**; conditional medians **3.3103s / 3.1626s**. Every candidate hit
  occurred before a probe. The three above-target stopping witnesses were
  all still misses after the probe: **0/3 actual stop rescues**. Two tightly
  solved systems took only one PCG iteration at already-large damping, then
  clipped away almost all camera movement. The third solved in 12 iterations
  but failed nonlinear acceptance. The historical 8/10 is a separate batch.
- Venice52 at 243740.27, fresh N=10: **0/10 original, 0/10 de-clipping**.
  All ten triggers fire after outer 39; all deep probes encounter the
  existing curvature cutoff at 10–55 CG iterations and are conservatively
  vetoed. No deep step is committed. Two truncated candidates otherwise
  passed true-cost/model/radius acceptance, so this does not refute a
  different truncated-step policy. We did not change the registered policy
  after seeing those candidates.
- D88/L1197 N=3 original/off/stop/declip/both screen: no endpoint regression
  breaches 0.5%. Stop and combined arms fail wall gates; on L1197 median
  endpoint times are original **4.703s**, stop **6.570s**, both **6.138s**.
  The flags-off control has one +31.95% L1197 pair but only +1.96% median,
  so a single pair's wall difference is not a clean causal attribution.

The mathematical clue is the coupled controller update
`lambda_next = lambda * (R_old/R_next)^2`, aside from exceptions/clamps.
Restoring lambda alone does not restore its contracted radius. Three failed
Final3068 probes retained approximately 1.71e-6, 4.63e-7 and 1.09e-10 of the
raw camera norm. A larger CG cap cannot recover motion that clipping removes.
A future intervention should ablate recovery of the `(lambda,R)` pair at a
meaningful-progress boundary. For Venice, audit the failed Rayleigh quotient
with a higher-precision operator at the same state first. The cutoff is
`pAp > 1e-14*pp`; its failure is not proof of strictly negative curvature.
These follow-ups are reasoned hypotheses, not measured improvements.

Implementation details were registered before tests: true residual ratio
`min(original_eta,1e-3)`, cap512, a separate flat-streak center snapshot,
unchanged radius for stop, fourfold next-state radius expansion for de-clipping,
one probe of each kind per run, rollback on failure, no extended caps and
no scene/target-dependent policy features. This is an Eta2 adaptation, not
a claim of binary equivalence to MFREE's deep-CG retry.

Everything is on `research/eta2-depth-rescue`; registration `75ae3f4`,
implementation `d45914d`, completed results `abd116b`. Full results and
limitations: `research/eta2_depth_rescue/FINDINGS.md`, `INTERPRETATION.md`,
`summary.json`, `audit.json`. The original champion and original algorithm
remain unchanged. No GPU jobs remain and no work is requested on your GPU.

Verified archive (539 files: source, both binaries, raw traces, all 76
losslessly compressed endpoint states):
`/workspace/collab/results/eta2_depth_rescue_20260911T182018Z.tar.gz`

SHA256: `edf8c07eae64068a203ad43cd10bfd633a601b1cdf17b8ff7071a5f62d76e722`

The archive contains the completed-result commit and its per-file manifest;
this handoff and the archive pointer were added afterward.
