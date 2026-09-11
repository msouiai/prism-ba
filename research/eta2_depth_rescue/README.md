# One-shot depth rescue for Eta2

This branch tests two MFREE-inspired reliability interventions on frozen
single-shift Eta2 PCG: tighter/deeper CG before a final stop, and a one-time
radius expansion after extreme clipping. Both are opt-in. The original
algorithm, champion source, headers, flags and binary are preserved.

Read [PROTOCOL.md](PROTOCOL.md) for the pre-registered design and gates,
[FINDINGS.md](FINDINGS.md) for the outcome, and [summary.json](summary.json)
for all grouped results and individual no-regression gate failures.

## Reproduction

Prerequisites match `../eta2_champion/build.py`: CUDA nvcc, Eigen, RTX Ada
(`sm_89` in this prototype), Python and NumPy. The build first verifies the
frozen parent source and all 44 headers. It applies `patches.json` and the
small `.inc` files to a generated source under `build/`, without modifying
the original. Builds and measurements acquire `/tmp/prism_gpu.lock`.

```sh
python3 research/eta2_depth_rescue/build.py
python3 research/eta2_depth_rescue/run.py compatibility
python3 research/eta2_depth_rescue/run.py final
python3 research/eta2_depth_rescue/run.py venice
python3 research/eta2_depth_rescue/run.py screen
python3 research/eta2_depth_rescue/analyze.py
```

The harness expects the registered BAL bytes in `/workspace/bal` and the
frozen original binary at `/tmp/prism-rl-actor/build/prism-tr`. Its hash is
checked against `../eta2_champion/champion.json`. Existing result files are
reused, not overwritten; use a separate checkout/evidence directory for new
repetitions. Each row records the complete invocation and input/binary hashes.
The archive preserves both binaries and all compressed endpoint states.

## Flags

- `OCA_DEPTH_STOP=1`: one solve at cap 512 and residual ratio at most 1e-3
  before honoring an otherwise final stop, at the saved flat-streak damping
  center and existing radius.
- `OCA_DEPTH_DECLIP=1`: one solve at the next accepted state after a step
  with raw-norm/radius > 10 and rho in [.25,.75], with radius enlarged fourfold.

Both retain numerical safeguards, point safeguarding and true nonlinear
cost/model acceptance. Both fit the existing outer/time caps. On rejection
the accepted state stays unchanged and controller scalars are restored.
Stopping-probe rejection confirms termination; de-clipping rejection resumes
the original attempt. No target values or scene names enter either policy.

`DEPTH_RESULT candidate` records the incumbent best cost; if no scored
candidate improved the current cost it equals the current cost, rather than
reporting the rejected trial's larger objective. `trunc=1` means the original
Rayleigh cutoff failed (`pAp > 1e-14*pp`); it does not by itself prove strictly
negative curvature. The raw linear residual is recomputed before clipping.

Do not infer a speed gain from a faster failed run or an endpoint variation
after a rejected probe. CUDA reduction ordering is stochastic; the within-run
stopping witness is the relevant evidence of an actual stopping rescue.
