# RL damping control for Prism: research and proposed pilot

Research date: 2026-09-09. Literature and source inspection only; no policy was trained and no new GPU benchmark was run.

RL is a plausible way to improve damping schedules, but the general idea is established prior art. The useful Prism-specific question is whether a small controller can trade nonlinear progress against the cost of solving the damped Schur system over several future steps. There is no measured RL speedup for our current champion.

## Closest prior work

| Work | Verified contribution | Relevance |
|---|---|---|
| Ruvolo, Fasel, Movellan, **Optimization on a Budget: A Reinforcement Learning Approach**, NIPS 2008 | Learns LM damping control with least-squares policy iteration using optimization-progress and budget information. Reports transfer from small regression tasks to a vision task. | Direct prior art for RL damping and a reason to start with a small value model. [Paper](https://proceedings.neurips.cc/paper_files/paper/2008/file/9a96876e2f8f3dc4f3cf45f02c61c0c1-Paper.pdf). |
| Belder, Vivanti, Tal, **A Game of Bundle Adjustment—Learning Efficient Convergence**, ICCV 2023 | Uses SAC to select continuous BA damping from a five-error history. Reward uses negative iteration duration and a convergence bonus. Evaluates KITTI/BAL and transfer from small synthetic problems. | Direct BA precedent. Both time-based reward and synthetic-to-real training are already claimed. Their reported gains do not establish gains over Prism or Caspar. [Paper](https://arxiv.org/pdf/2308.13270), [authors' repository](https://github.com/amirbelder/A-Game-of-Bundle-Adjustment---Learning-Efficient-Convergence). |
| Eimer et al., **DACBench**, IJCAI 2021 | Standardizes environments for dynamic algorithm configuration, including controller interfaces and benchmark settings. | Treat the BA implementation, observations, intervention timing, and reward as part of the experiment specification. [Authors' project](https://www.automl.org/automated-algorithm-design/dac/dacbench-benchmarking-dynamic-algorithm-configuration/). |
| Kumar et al., **Conservative Q-Learning**, 2020 | Addresses value overestimation under the distribution shift between offline data and a learned policy. | Historical solver traces alone do not justify extrapolating to unseen damping actions. [Paper](https://arxiv.org/abs/2006.04779). |
| Benjamins et al., **Instance Selection for Dynamic Algorithm Configuration with Reinforcement Learning**, 2024 | Studies training-instance selection to improve policy generalization in DAC. | Scene-family separation and representative training regimes are first-class requirements. [Paper](https://arxiv.org/abs/2407.13513). |

The public ICCV environment deserves an implementation audit before reuse: `step()` returns expected model improvement as its next observation, has a threshold-dependent Hessian computation path, and uses a sparse Schur solve. These details prevent treating it as a drop-in Prism controller. The paper description and repository should be reconciled rather than silently assumed identical. [Authors' environment source](https://raw.githubusercontent.com/amirbelder/A-Game-of-Bundle-Adjustment---Learning-Efficient-Convergence/main/ba_env.py).

SAC remains a sensible later continuous-action baseline: it is an off-policy actor-critic method with entropy-based exploration. It is not necessary for a three-action pilot. [Original SAC paper](https://proceedings.mlr.press/v80/haarnoja18b.html). Also distinguish using numerical trust regions inside an RL training algorithm from using RL to control a BA trust region; the former is not direct evidence for the latter.

## What our evidence says

1. **Immediate reward can be misleading.** In our four-state damping study, three of four choices selected for the largest next-outer gain lost their gain advantage after three outers. This was a small, reset-history diagnostic, not an equal-time policy comparison, but it motivates looking beyond one step. [Local evidence](identical_state_damping_results.md).
2. **The cost of an iteration is action-dependent.** The recent Muell control used depths `0,1,3,2,7,60,29,128`, followed by several more depth-128 solves. Krylov work took 3.327 s in the full profile, versus 0.045 s candidate evaluation. A policy must account for linear-system cost. [Profile and results](/workspace/prism-fast-start/RESULTS.md).
3. **Damping has distinct roles.** Some stalled trajectories had large controller damping while the numerical floor was tiny. Raising the floor cannot fix excessive nonlinear contraction. The policy should observe the floor but leave its enforcement to the numerical guard. [Schur recovery evidence](schur_recovery_results.md).
4. **Controller interactions matter.** Current radius and lambda updates are coupled; camera/point damping coupling also changes behavior. Independently predicting radius, camera damping, point damping, and CG tolerance would initially make attribution very difficult. [Controller ablation](controller_attribution_results.md).

These observations suggest two useful regimes to learn: preserve more regularization when decreasing lambda makes subsequent solves expensive, and relax excessive regularization when it prevents meaningful progress. Whether either action actually reduces time to target remains an experimental question.

## Mathematical motivation

At a fixed linearization, write coupled LM as

\[
(H+\lambda D)p=-g,\qquad D\succ0.
\]

With \(\widetilde H=D^{-1/2}HD^{-1/2}\succeq0\), the exactly scaled full system has

\[
\kappa_2(\widetilde H+\lambda I)
=\frac{\lambda_{\max}(\widetilde H)+\lambda}
{\lambda_{\min}(\widetilde H)+\lambda}.
\]

Increasing positive lambda reduces this condition number, potentially making the linear solve cheaper, while changing the step and its nonlinear progress. This identity is for a fixed, scaled full system. It does not guarantee fewer iterations for Prism's changing preconditioned Schur operator.

For BA, with camera block B, point block C and cross block W,

\[
S(\lambda_c,\lambda_p)=B+\lambda_cD_c
-W(C+\lambda_pD_p)^{-1}W^T.
\]

Changing point damping changes both S and the reduced RHS. It generally does not create a scalar identity shift, so arbitrary two-damping actions cannot all be obtained through ordinary multishift reuse. This is one reason to begin with the champion's coupled damping and a single proposal.

The ideal decision minimizes remaining time,

\[
V(s)=\min_a\mathbb E[\Delta t(s,a)+V(s')],
\]

with zero terminal value at the externally fixed quality target. Unlike minimizing next-step cost or rejection count, this objective can favor a modest immediate improvement that enables cheaper future solves. The full state includes geometry, controller memory, and relevant cached state. A short vector of solver statistics is a partially observed approximation, so history should be tested explicitly.

## Recommended controller

**Intervention.** After an accepted outer step, compute the champion's nominal next damping first. A policy then chooses a logarithmic correction:

\[
\lambda_{k+1}=\operatorname{clip}
(\lambda^{\rm base}_{k+1}10^{a_k},\lambda_{\rm numeric},\lambda_{\max}),
\qquad a_k\in\{-1,0,+1\}.
\]

Action zero reproduces the baseline update. Point damping follows the existing coupled rule. For the first experiment keep the baseline's radius update, acceptance, retry escalation, precision, numerical repair, stopping, and CG tolerance. Let the baseline handle rejection retries. This isolates learned accepted-step damping control; it does not yet learn retry management.

The radius may clip different lambda proposals to similar steps. Log pre/post clipping and effective damping, and verify that actions actually alter the solve. A later ablation could predict radius instead and derive damping consistently; do not add both controls at once.

**Observations.** Use roughly 15–25 already available scalars plus a short history: current log damping and numerical-floor ratio; previous effective action; actual/predicted reduction ratio rho; relative objective progress; normalized gradient/RHS norm; normalized camera-step/radius ratio; CG depth and depth-cap indicator; measured residual ratio if already available; previous rejects, rescues, and numerical rebuilds; recent solve duration/work; static observation and camera/point counts. Use validity masks for unavailable ratios. Collect expensive spectral or residual features only if an ablation justifies their cost.

Use logs, relative changes, and ratios to reduce dependence on scene scale. Do not use scene IDs, held-out reference costs, or future outcomes as observations. A four-step history is a proposed starting choice, not an established optimum. It supplies evidence about past damping without forcing arbitrary damping smoothness.

**Reward.** Every transition costs `-native_elapsed / scene_budget`, including feature extraction, inference, and all intervening retries. Stop successfully only on the fixed useful-quality threshold. Charge an additional unit penalty at a budget or stall termination without reaching it. Use undiscounted finite episodes initially; discounting by outer count would distort the time objective when actions have different durations. Under a strictly enforced normalized budget, successful episodes have total cost at most one, whereas failures incur the additional unit penalty. Handle budget overshoot explicitly.

Do not reward a small update or an early FTOL stop as success: a policy could otherwise win by making lambda enormous and freezing the solve. Do not charge a second large reject penalty when rejection time is already counted; acceptance rate is a diagnostic, not the optimization objective. A progress-shaped reward can be an ablation, but immediate loss reduction alone is not aligned with the user's time-to-target preference.

Targets may use a predeclared 0.5–1% quality tolerance from independent references. Small endpoint differences within the accepted tolerance should not disqualify a faster policy. Audit the original objective at endpoints.

**Learner.** Start with a small fitted action-value model and three actions. First collect branched rollout returns under baseline continuation, fit a value/ranking model, and test the resulting policy. This is rollout-guided policy improvement; merely regressing one-step candidate costs would not constitute a full RL solution. If it transfers, collect data from the improved policy and perform fitted policy evaluation/improvement. Use conservative action support and baseline fallback when validation shows unreliable predictions. A lightweight model can be exported to C++ for CPU inference once per outer step.

## Existing code: reusable pieces and gaps

The frozen champion source already contains `LearnPolicy`, `OCA_LEARN_LOG`, learned candidate ranking, and a horizon-Q mode. However the menu controller is gated on `L>1`; the selected champion uses `OCA_NSHIFTS=1` and `OCA_CLASSICAL_LM=1`. These hooks therefore do not implement the intervention proposed above. Source comments describe older ranking failures, but I did not locate their complete result package here; do not treat those comments as a new measured result. [Policy hook](/workspace/prism-model-followup/candidate/source.cu:10537).

The existing log schema includes rho/prediction fields, but the classical-LM branch does not populate the legacy `learn_rho` assignment used by the menu branch. Add explicit classical-LM telemetry and standards-compliant finite/null JSON fields before using those logs for learning. Use complete precision for checkpoint values. [LM update](/workspace/prism-model-followup/candidate/source.cu:11705), [logging](/workspace/prism-model-followup/candidate/source.cu:11894).

The existing replay mechanism restricts supported flags and excludes the champion's controller configuration. Extend and verify it before calling any branching a matched-state counterfactual. Restoring only BAL geometry resets radius, damping history, stopping counters and numerical floors, and can answer a different question. A no-intervention continuation must reproduce state/controller transitions within established numerical repeatability. [Replay implementation](/workspace/prism-model-followup/candidate/source.cu:9640).

Old traces are useful for feature distributions and baseline behavior. They contain no observed future outcomes for most unchosen actions, so they are not sufficient to validate offline policy improvement by themselves.

## Lightweight pilot and decision rule

1. **Freeze the baseline manifest**, including explicit initial lambda. The latest Muell fast-start study used 0.1 while the earlier 4.220 s champion command used default 10; choose and record the exact intended comparator before collecting any new data.
2. **Audit telemetry and checkpoint continuation** on one small problem. Verify action zero, true alternative actions, and no extra candidate solves during inference.
3. **Measure whether a usable signal exists.** Select 24 checkpoints across at least three training scene families and across opening, expensive-CG, and stalled regimes. For each, branch three first actions and continue the baseline for up to four outer steps: 288 outer slots before retries. Repeat ambiguous branches within a predeclared 10-minute native-GPU budget. Compare equal-time progress on a fixed horizon when target crossings are unavailable; do not compare unequal-work final losses as speed. Treat the resulting short-horizon ranking as development evidence, not final time-to-target proof.
4. **Fit and test a small policy** only if action differences exceed ordinary repeatability and can be predicted on an untouched development family. A per-state hindsight winner is optimistic and is not itself an implementable policy or a rigorous upper bound.
5. **Freeze one policy for N>=3 evaluation** on whole held-out scene families and one production scan. All crops, perturbations, and repeat runs of a recording stay in the same split. Muell has already informed our hypotheses, so it is a transfer check, not a pristine unseen benchmark. Include at least one genuinely unused recording for a generalization claim.
6. **Compare current champion, simple deterministic work-aware rule, learned policy, Caspar FP32, and Caspar FP64** on identical fixed targets. Record hit rate, native time including inference, time spent on retries, matvecs, capped solves, and independently audited cost. Report scene-level paired ratios and ranges; do not pool thousands of correlated iterations as independent samples. Repeat training seeds if stochastic training is used.

A proposed promotion rule is at least 10% median target-time improvement across the held-out panel, without losing previously reliable target hits. Report scene-specific regressions and uncertainty rather than rejecting low-single-digit timing variation automatically. If the branch choices are indistinguishable or a simple rule matches RL, retain the simpler controller and continue the preconditioning work.

## Contribution that would need to be demonstrated

“RL chooses LM damping,” “RL accelerates BA,” “use a time reward,” and “train on small synthetic problems” are already prior art. A possible contribution is a compact controller conditioned on measured linear-solve difficulty and model reliability, integrated with coupled damping and numerical recovery, that improves audited time-to-quality on modern GPU BA and production scans. This remains a hypothesis, not a novelty verdict. Required ablations remove the work features, history, and learned decisions individually and compare against the relevant deterministic controls.

The result of this research is a concrete, bounded experiment design. The incumbent solver remains selected until that experiment demonstrates a gain.
