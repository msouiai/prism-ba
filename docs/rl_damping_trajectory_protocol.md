# Complete-trajectory damping-policy search

Freeze before collection. Native solver budget <=900 seconds total, serial GPU
on host 2237c6528e79 / RTX 2000 Ada. Raw work under
`/tmp/prism-rl-damping-trajectory`; compact evidence persisted to `/workspace`.

The training unit is a complete solve to a fixed useful-quality target, not a
single action followed by baseline continuation. This is finite direct policy
search using terminal returns, not SAC/PPO or a learned value network. No new
claim of RL novelty is implied. Eight small feedback policies plus baseline
and the previous opening-2 comparator are frozen before measuring returns.

Feedback policy family: negative corrections when rho >=0.7 and previous CG
fraction <=0.25, or stricter rho >=0.95 / CG <=0.125; positive corrections only
at CG cap; or a mixture of the strict negative and cap-positive rules. Each
has a total intervention budget of 2 or 4 and skips the next boundary after
intervening. Actions multiply baseline next lambda by 0.1, 1 or 10. All solver
acceptance, radius, retry and numerical-floor safeguards remain intact.

The controller permanently falls back to baseline after a previous rejection,
numerical repair, rho outside [0.25,1.5], or relative progress below 1e-7.
It abstains when proposed baseline log10(lambda) is outside [-12,1]. This
fallback does not restore an earlier geometry or guarantee baseline speed.
No scene identity or size threshold is used. No replay in episode mode.

## Training and selection

Training scenes and fixed targets, chosen from existing baseline endpoints:
Ladybug-598: 180500; Dubrovnik-356: 730000; Venice-89: 305000. Four-second
native cap and 600 outers. Both initial lambda 0.1 and 10, N=3 for every
configuration, rotating arm order. Thus 180 complete training episodes.

Minimize mean log(time / matched baseline median), equally weighted across
scene/start-setting tasks. A target miss receives loss log(4 * cap / baseline
median); it is never reported as a measured crossing or speedup. Prefer
baseline on score ties. Report family-held-out selection: choose the policy
using the other families, then score the omitted family's actual complete
episodes. This separates policy-selection data from its family check.

Freeze the best nonbaseline feedback policy for diagnostic transfer even if
its selection score is worse than baseline. Retain baseline as the deployment
choice unless all transfer targets hit and no task regresses >5%, with median
task speedup >=1.10. These observed research scenes are not pristine datasets.

## Transfer and largest-scene test

N=3, same binary and flags, logging disabled for timing. Baseline, frozen
feedback policy, and opening-2 on Trafalgar-126 (target105579.58394455544,4s),
Final-1936 (5125687.352261469,8s), Muell-gba146 (1946488.746262194,12s),
both starting lambdas. No fitting to these outcomes.

Final-13682 is excluded from fitting and policy selection. Use its historical
fixed target 27591576.557625167,20s native cap,600 outers,N=3. Test baseline,
frozen feedback policy and opening-2 at the historical initial lambda0.1;
fresh Caspar FP32 and FP64 references use the existing checked binaries and
the same target (0.1% inward native margin for FP32). Input SHA256 must match
76ef34416fdca524b1ec6755b62ab33cba15c8b5b830b5ff38369c8cd609d736.
Original-observation CPU FP64 endpoint audits are required for every hit.
Native solve clocks include Prism local setup and exclude Caspar graph setup;
report setup separately. Loading, export and audit are outside solver clocks.

Plot causal recorded convergence curves with terminal timestamps aligned to
native crossing, as in the earlier Final-13682 study. Preserve misses, ranges,
all binaries, policies, run manifests and prior research conclusions.

## Training-target amendment — 2026-09-09T23:35:30.693661+00:00

After 32 initial training trials, the Ladybug target was recognized as a 0.049%-above-reference polishing target, inconsistent with the useful-quality convention. Those initial trials are retained but excluded from selection. This is a disclosed unblinded development correction, not an untouched preregistration. All three training targets now use 1.01 times the pre-existing baseline endpoints: Ladybug598 180411.357852; Dubrovnik356 724127.912566; Venice89 303286.305616. New run names begin train-q1. Transfer and Final13682 targets are unchanged, and none of their outcomes has been examined. Native budget includes the abandoned development trials.
