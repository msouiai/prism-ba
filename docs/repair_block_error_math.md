# Camera, point and interaction model error

For a captured current state and its **actual selected repaired step**, define F_ab=F(Retract(a*dc,b*dp)). The projected Gauss–Newton change is

    q_ab = a*gc + b*gp + 0.5*(a^2*cc + 2*a*b*cp + b^2*pp).

We measure F00, F10, F01 and F11. Two extra objective evaluations beyond current/accepted cost identify the following finite-step error decomposition:

    E_c = F10 - F00 - (gc + 0.5*cc)
    E_p = F01 - F00 - (gp + 0.5*pp)
    E_cross = F11 - F10 - F01 + F00 - cp
    E_total = E_c + E_p + E_cross = F11 - F00 - q11.

This is an exact algebraic decomposition at the sampled endpoints. E_cross is the nonlinear interaction beyond the GN mixed coefficient, not the entire camera–point interaction. It includes higher-order mixed behavior; it is not necessarily a Hessian entry or a quantity that can be assigned uniquely to either damping parameter.

The camera-only and point-only predicted decreases are -q10 and -q01. A block agreement ratio is meaningful for damping only when the corresponding prediction is positive and appreciably above rounding uncertainty. A successful joint step does not imply either isolated block is a descent step: its mixed term can be essential.

For completeness, conditional predictions with the other proposed block already applied are -(q10+cp) and -(q01+cp), compared with actual gains F01-F11 and F10-F11. Their errors each include E_cross. They are not independent measurements that resolve ownership of the interaction.

We normalize errors by positive full-step predicted decrease and record (abs(q10)+abs(q01)+abs(cp))/abs(q11), a measure of cancellation in the model. Large cancellation makes isolated block-relative errors potentially misleading for a much smaller net joint decrease.

The experiment captures the first, second and fourth repaired accepted directions on both frozen-pair and relaxing-pair trajectories for Dubrovnik356 and Venice52. CPU reconstruction verifies all four costs and projected derivative coefficients. Separate damping feedback is conditional on a stable, identifiable block signature; a dominant interaction or undefined isolated ratios does not justify inventing a camera-versus-point update rule. The prior fixed-single/point-repair configuration remains the performance baseline.

## Conservative split-feedback hypothesis

The captured Dubrovnik directions have a reliable standalone point decrease, while their camera-only predicted decreases are negative. Venice's earliest repaired directions require camera–point coupling and neither isolated block predicts descent. Conditional agreement ratios stay near one on both scenes and do not separate their behavior.

This supports testing **eligibility**, rather than claiming ownership of interaction error: halve one block's retained damping only if its isolated trial actually decreases the current cost and has a positive, numerically resolved GN prediction with rho>0.75. Otherwise retain that component. The existing rounding band and damping floors apply. There are no upward updates. The combined nonlinear acceptance remains unchanged; isolated probes are diagnostic evaluations, not committed states.

The rule is a conservative experimental heuristic. Standalone descent is sufficient to pass this gate, but it is not necessary for a useful coupled direction. Consequently it may refuse beneficial damping changes or keep a component frozen. It also does not prove that changing a normal-equation damping parameter will improve a subsequent direction. A short online test must measure the full overhead and resulting trajectories.

Implementation uses OCA_REPAIR_SPLIT=1 with OCA_REPAIR_DAMPING=1: the combined prediction is audited while separate block decisions supply the updates. This avoids applying both the joint and split feedback laws. The prototype computes the combined model plus a five-coefficient model and two additional full objectives; timings include this deliberately straightforward implementation.

## Reusing the projected model

The split decision already needs gc,gp,cc,cp,pp. Its combined audit can therefore reuse s=gc+gp and q=cc+2*cp+pp instead of launching a second direct-model kernel. P=-s-0.5*q follows algebraically. The twelve saved steps agree with the separate direct prediction to9.84e-14 relative. This removes duplicate work and its16-byte allocation on the split path; the forty-byte coefficient reduction remains. The isolated true-cost probes and per-block feedback rule are unchanged. Near exact camera–point cancellation, deriving a squared norm by this sum can lose relative precision; here the combined prediction is audit-only and does not control the separate decisions.
