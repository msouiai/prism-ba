# T6: bounded depth smoothing does not pass the speed gate

All depth-tube and ordinary runs reach the fixed targets, both parallax
settings, ten held-out seeds, N=3. Every arm receives all 36 terminal attempts
on the identical original objective. Radius-zero matrix identity and stage
gradient tests pass; invalid quadrature trials are rejected as whole states.

At low parallax, the 0.10 depth tube improves median point NRMSE from 0.1100
to 0.0920 and median final cost from 11.5067 to 11.4985, with the same one
geometric failure among ten seeds. Its time-to-target speed is only 0.578x
ordinary LM. The 0.02 tube runs at 0.523x and increases geometric failures
from one to three. Multiple starts run at essentially the ordinary first-hit
speed (the first branch is ordinary LM), with both branches' work retained.

At normal parallax, both depth-tube radii converge to the same median original
cost and geometry as ordinary LM after refinement, at 0.484x/0.423x speed.
The isotropic control is harmful: at radius0.10 only 7/10 low-parallax and 5/10
normal-parallax scenes reach target, and all have point-NRMSE>0.15. The small
isotropic radius can reach a low cost with poor geometry as well. These failures
remain in the result; no invalid sample was silently discarded.

**Verdict:** unsupported for convergence speed in this screen. Preserve the
qualified low-parallax geometric improvement but do not promote a smoothing
schedule. No adaptive radius policy is trained because the simple intervention
did not pass its registered cost gate. Current GPU incumbent remains Eta2.

## Mathematical and prior-art distinction

ProBA v2 represents lifted observations using optimizable isotropic 3D
Gaussians, projects their covariance into a 2D NLL, and adds 3D probabilistic
consistency plus other graph/regularization machinery. It is a permanently
different problem with additional variables. Our fixed bounded quadrature is
a temporary surrogate over the same shared point variables, with no learnable
variance and an explicit radius-zero return. It is neither a ProBA replication
nor evidence against that method.
[ProBA v2, sections 3.1–3.4](https://arxiv.org/html/2505.20858).

The isotropic surrogate penalizes transverse uncertainty as well as depth;
under perspective projection it can favor poor geometric paths. The observed
failures motivate diagnostic study but do not constitute a general theorem.
Reproduce `check_smoothing.py` then `run_t6.py --split development|held_out`.
`T6_PROTOCOL.md`, `smoothing_checks.json` and all `t6_*` raw records retain
quadrature, objective, invalidity, terminal-refinement and timing details.
