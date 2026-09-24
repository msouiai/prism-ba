# Follow-up: rewards and learned control for Prism

The curvature threshold pilot is complete and did not displace the incumbent.
The next experiment will train a small stochastic policy by policy gradient,
rather than search a fixed menu of threshold rules. This is an experimental
extension, not evidence of RL novelty or a claimed speed improvement.

## Prior work and implications

[A Game of Bundle Adjustment, ICCV 2023](https://openaccess.thecvf.com/content/ICCV2023/papers/Belder_A_Game_of_Bundle_Adjustment_-_Learning_Efficient_Convergence_ICCV_2023_paper.pdf)
already learns BA damping with RL and motivates delayed convergence rewards.
Learning lambda, remembering recent errors, and rewarding fast convergence
are therefore not new claims. Prism's open question is whether a policy can
improve its guarded, inexact, preconditioned solver at equal quality.

[Ng, Harada and Russell, 1999](https://ai.stanford.edu/~ang/papers/shaping-icml99.pdf)
characterize potential-based reward transformations that preserve optimal
policies under their stated assumptions. For our finite undiscounted episodes,
the relevant identity is simply telescoping potential differences, with the
same terminal potential on success and failure and a separate failure cost.
Shaping does not create counterfactual information or guarantee sample-efficient
learning with approximate state features.

[Sutton, Precup and Singh, 1999](https://people.cs.umass.edu/~barto/courses/cs687/Sutton-Precup-Singh-AIJ99.pdf)
provide the semi-Markov framework for actions with variable duration. A BA
outer can contain very different amounts of CG and retry work. Counting all
outers equally or discounting only by outer count changes the speed objective.
This study uses undiscounted finite episodes and explicitly charges seconds.

[Williams, 1992](https://gwern.net/doc/reinforcement-learning/model-free/1992-williams.pdf)
provides the REINFORCE policy-gradient foundation. A small softmax actor with
state-dependent logits is sufficient to test learned decisions without GPU
neural inference or an external RL framework. A past-data state-value baseline
can reduce gradient variance without needing an environment differentiable
through BA. This does not guarantee an improvement from a small training set.

[Ceres' nonlinear solving documentation](https://ceres-solver.readthedocs.io/latest/nnls_solving.html)
describes inexact solves and their forcing tolerance. This motivates a second
control dimension: change CG accuracy directly instead of using lambda to
make the linear system easier. We retain the incumbent residual verification,
lambda floor, radius guard and true-objective acceptance.

## What does “gain” reward actually optimize?

For a fixed target T and starting cost F0, define normalized capped progress

```
P(F) = clip(log(F0 / max(F,T)) / log(F0/T), 0, 1).
```

1. Total capped gain `sum Delta P` equals one for every successful episode.
   It cannot distinguish a fast solve from a slow one.
2. Uncapped gain additionally rewards overshooting the quality threshold,
   even when that costs time the user does not value.
3. Summing per-step gain rates `sum Delta P / Delta t` is not the same as
   total gain divided by total time. Splitting one constant-rate step into
   two steps doubles that summed reward without improving the trajectory.
4. For successful fixed-target solves, the overall rate `1 / total_time`
   ranks deterministic trajectories correctly, but expected reciprocal time
   is a different stochastic objective from expected time.

Our proposed time reward is `-Delta t / Tref`, where Tref is a measured
training-task baseline time. Add potential shaping

```
r' = -Delta t/Tref + Phi(next) - Phi(current),
Phi = P - 1; Phi(terminal) = 0.
```

Its total is `1 - total_time/Tref` plus a declared penalty for failure.
Terminal potential is zero for ALL absorbing ends, including timeouts; a
failure receives an explicit penalty, not a fabricated target crossing.
Thus gain can provide a dense signal while keeping elapsed time authoritative.
At fixed state, complete Monte Carlo shaping returns differ by a state-only
term, so an exact value baseline would cancel it: shaping is not a magic
source of better credit assignment. Its usefulness with an approximate
baseline must be measured.

## Three concrete alternatives

- Learn residual lambda corrections of factors {1/2,1,2}, instead of decade
  jumps. Condition on recent model agreement, work, curvature, radius activity
  and scale-normalized progress; retain a bounded intervention count.
- Give a learned policy two additional actions: halve or double the current
  forcing tolerance for one outer, capped at the incumbent maximum .5. This
  separates linear-solve effort from nonlinear damping.
- Train the same joint action policy with a summed gain-rate reward as a
  deliberately separate objective, and compare it with elapsed-time plus
  potential shaping. Choose winners only by fresh audited time-to-target.

The first pilot used a narrow controller class and a few training problems.
The follow-up adds a second small problem per training family while preserving
held-family/size transfer distinctions. Existing scenes are familiar research
data, not a new population sample. Baseline and fixed forcing controls must
be retained to distinguish learning from a useful constant setting.

## Audit of the completed curvature trajectories

Relabeling all 162 successful training trajectories confirms that capped
total gain is identical across arms. Uncapped gain favors `curv-down-strict`,
elapsed-time rewards favor `curv-mixed-strict`, and the summed gain-rate
diagnostic favors baseline. The latter is not a claim that gain-rate rewards
always perform worse; here it chooses a conservative arm. It establishes that
these objectives can select different policies. Legacy gain-rate timing uses
outer telemetry and omits setup, so only the actual native target-time scores
are used for performance claims. Code: `bench/audit_rl_rewards.py`; full values
are in `/tmp/prism-rl-actor/reward-audit.json`.

## BA-specific coupling worth exploiting

Prism's current forcing heuristic uses the ratio of consecutive reduced-RHS
norms: `eta = min(.5, .9 * ||b_new||^2 / ||b_old||^2)`. In coupled damped BA,
the reduced RHS itself depends on point damping, schematically

```
b_reduced(lambda) = b_c - W (V + lambda D_p)^-1 b_p.
```

Consequently a lambda intervention can change both the step regularization
and the requested linear-solve accuracy, even at otherwise fixed geometry.
This is a reason to expose forcing tolerance to the actor and to compare
direct forcing control against damping-only actions. It does not prove that
the current forcing heuristic is suboptimal on any particular scene. The
five-action pilot changes one control at a time; simultaneous two-dimensional
actions or holding forcing fixed during a lambda change would be separate
follow-ups if the measured results justify them.

## What the forcing discovery changes

The fixed eta2 discovery reduced Final13682 from28 to19 matrix products and
from5 to4 accepted outers at the registered target. It also hurt Muell when
combined with lambda10. These observations motivate a separate frozen
configuration confirmation; they do not establish a universally better
forcing term. See `rl_sustained_protocol.md` for the prospective comparison.

[Eisenstat and Walker, 1996](https://users.wpi.edu/~walker/Papers/forcing_terms,SISC_17,1996,16-32.pdf)
analyze how forcing accuracy controls inexact Newton convergence and explain
the cost of solving a local equation too accurately when the nonlinear model
is inaccurate. This supports investigating oversolving here, but their root
finding assumptions do not directly prove convergence for Prism's damped,
Schur-reduced, clipped Gauss–Newton steps.

For our own quadratic diagnostic, let the SPD damped system be A d = -g and
let e = A d + g. The exact damped quadratic minimizer is d_star, so

```
q(d) - q(d_star) = 0.5 e^T A^-1 e.
```

This measures the model improvement left unclaimed by an inexact solve.
A lower spectral bound m>0 gives an upper bound ||e||^2/(2m). A minimum Ritz
value from an explored Krylov space is generally NOT such a lower bound for
the full matrix. Treating it as a certified bound would reverse the logic.
Radius clipping also changes the step after this identity is applied.

Three next policy designs now have a concrete purpose:

1. **Persistent options.** Choose baseline forcing or eta2 for a whole phase,
   with an escape after rejection/model failure. The current actor's three
   isolated one-outer interventions cannot represent the discovered constant
   strategy. Train full-trajectory option returns before increasing network
   size. The options/SMDP reference above supplies the temporal framework.
2. **Marginal-work stopping.** Estimate additional quadratic improvement per
   next CG block from existing residual/Lanczos history, then compare its
   predicted time benefit with the previous nonlinear model discrepancy.
   This is a proposed diagnostic/policy input, not a proven stopping bound.
   Keep the existing residual check and true objective acceptance authoritative.
3. **Constrained whole-episode reward.** Optimize time while enforcing target
   hit probability on a separate validation set. A multiplier updated from
   misses can replace a hand-selected training failure penalty; it cannot
   replace audited target checks. A recent related example uses constrained
   RL for chemistry solver selection, not BA, so its gains do not transfer:
   [Ikponmwoba and Owoyele, 2026 preprint](https://arxiv.org/abs/2604.00264).

These are follow-up designs, not implemented claims. First confirm whether a
single fixed forcing configuration already explains the useful improvement.
