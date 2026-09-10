# Registered learned-control follow-up, 2026-09-10

Parent: completed curvature-study binary and immutable manifest. Isolated
artifacts: `/tmp/prism-rl-actor`. Production defaults remain unchanged.

## Controls, state and safeguards

Train a CPU softmax actor with 20 bounded features and state-dependent logits.
Inputs are prior lambda, rho and its change, CG fraction, raw camera/radius
ratio, prior forcing tolerance, GN directional multiplier and its change,
PCG Ritz condition estimate and validity, relative objective progress,
progress from initial cost, observation/point-camera scales, two work/model
interactions, radius activity, and remaining intervention budget. No target,
future outcome, scene ID or reference timing is provided to the actor.

Actions are baseline, lambda/2, lambda*2, and (for joint actors) eta/2 or eta*2
for one outer. Forcing changes are clipped to [1e-12,.5]; a no-op leaves eta
arithmetic unchanged. At most three nonzero actions per solve, with an idle
boundary between actions. Numeric repair permanently ends interventions;
poor rho, rejection or tiny progress temporarily abstains until the previous
outer is clean. Lambda floors, incumbent rescue/radius/acceptance and the
explicit true-residual check are retained. One decision per outer. No replay
support and no inference on an additional GPU.

## Three learning experiments

1. `lambda-time`: three actions, elapsed-time plus potential shaping.
2. `joint-time`: five actions, the same reward.
3. `joint-rate`: five actions, sum of per-outer capped gain/time rewards.

The last reward is an intentionally different objective, not claimed to be
equivalent to time-to-target. All winners are assessed by actual target time.
Define P as normalized capped log progress toward the registered target.
For time training, the return from a sampled decision is
`-(terminal_seconds-decision_seconds)/Tref + (1-P_decision)`, with an additional
`-4*cap/Tref` on failure. This is the reward-to-go from undiscounted elapsed
time plus a potential Phi=P-1, with Phi=0 at every absorbing terminal.
For rate training, sum future `Delta P / (Delta seconds/Tref)` and apply the
same failure penalty. Use absolute solver-budget timestamps at decisions and
outer completions, so retries and policy/feature overhead are charged.

Train on-policy by REINFORCE with a ridge state-value baseline fitted ONLY
to earlier batches. The first baseline is zero. Eight updates, twelve
episodes per update (one per task), fresh sampled actions and fixed distinct
seeds. Actor gradient sums decisions per episode, then averages episodes.
Clip global gradient norm at 1, use Adam ascent with learning rate .05,
betas(.9,.999), epsilon1e-8; clip coefficients to [-5,5]. No entropy bonus.
Initial action probabilities are .5 for baseline and the remaining .5 split
equally among other actions. Final update is frozen for greedy evaluation;
no checkpoint selection or tuning using transfer results. Train all three
experiments for the same 96 episodes each (288 total).

## Training tasks and target registration

Six scenes: ladybug49/598, dubrovnik88/356, venice52/89. Initial lambdas .1
and10 for each. For the three larger training scenes, inherit unchanged
targets from the curvature study. For the three added small scenes, run the
parent for eight outers at lambda.1, N=3; freeze target at 1.01 times median
audited endpoint. Require that target to improve initial cost by at least1%.
Record targets before actor training. Each task has 600-outer/4-native-second
caps. Measure N=3 incumbent target times to establish Tref. If baseline cannot
hit a task reliably, disclose and exclude that task before any fitting.

Calibration and training are not performance claims. Stochastic optimization
episodes use changing policies; they are not presented as N=3 evaluations
of a fixed solver. Final greedy policies receive separate N=3 training-task
evaluation, then frozen transfer. Training-family sample counts are tiny;
no claim of broad RL generalization or novelty follows.

## Evaluation and checks

Fresh N=3 comparisons: incumbent, the three learned policies, and fixed
eta multiplier2. Transfer uses exactly the completed curvature panel:
Trafalgar126 lambda.1, Final1936 lambda.1, Muell146 lambda.1 and10,
then Final13682 lambda.1. Targets/caps remain respectively
105579.58394455544/4s,5125687.352261469/8s,1946488.746262194/12s,
and27591576.557625167/20s. These are excluded from fitting; previous research
has used them, so they are not pristine unseen scenes. Logging is disabled
for performance, with separate causal diagnostic runs. No new Caspar runs.

Before training: verify softmax derivatives against finite differences,
reward telescoping and gain-rate partition counterexample, independent
Python/C++ action probabilities, budget/cooldown/no duplicate intervention,
and N=3 parent/new-off/zero-actor numerical compatibility. Validate every
endpoint with the original-observation CPU FP64 audit. Record binaries,
policy hashes, seeds, commands, per-action probabilities and reward terms.

Report median[min,max], hit counts, final cost, outers, rejects and matvecs.
Primary aggregate is geometric mean task speedup; count two Muell lambdas
as related settings, not independent scenes. A promising candidate needs all
targets, >=10% aggregate speedup and no task >10% slower. Smaller regressions
are reported rather than automatically disqualifying. A favorable result
requires subsequent confirmation; a fixed forcing rule winning is not
evidence that RL itself helped. Initial study ceiling:1000 native solver
seconds, including calibration, fitting, checks and evaluations.

## Additional sampling evaluation, registered before transfer

Training-side diagnosis after update8: on all collected training states, the
greedy action is baseline for all three actors (661/454/605 state samples).
Exploratory gains therefore cannot be attributed to the greedy controller.
Preserve the planned greedy panel and add a separate stochastic evaluation
of the frozen policies, without refitting or changing weights.

Arms: fresh incumbent, the three trained samplers, and the untrained five-action
sampler with the original .5/.125/.125/.125/.125 probabilities. Use common
registered seeds910000+repeat across sampling arms, N=5 on the four medium
tasks and N=3 on Final13682. Rotate order. Report each distribution, misses,
median/min/max and compare against the fresh baseline from this same panel;
never count samples as fixed-policy noise alone. Keep sampling seeds out of
the actor state. Per-action logging is off for these timings. This adds115
primary runs under the existing1000-native-second ceiling. No selection uses
transfer outcomes. The change is motivated by training behavior, before any
new transfer or largest-scene outcomes have been inspected.
