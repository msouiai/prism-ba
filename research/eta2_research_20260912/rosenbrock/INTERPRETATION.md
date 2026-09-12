# Brief 12 implementation interpretation, fixed before witness data

The parent accepted these details before any ROS2 BAL comparison. They make
the committed [protocol](../PROTOCOL_12.md) precise without adding a tuning
parameter. All algorithms act on the same fixed base coordinate q:

```
R(q)=Exp(q_rotation) R_base
t(q)=t_base+q_translation
intr(q)=intr_base+q_intrinsics, q_k2=0
X(q)=X_base+q_point.
```

Both D and the base chart stay fixed at the witness. If J_native is the
camera Jacobian in the current state's left perturbation coordinates, its
rotation columns in the fixed chart are
`J_native_rotation J_left(q_rotation)`. The stage fixed-chart gradient is
therefore `J_left(q_rotation)^T g_native_rotation`; translation, intrinsics
and point coordinates have identity transport. Relinearized LM2 uses these
same columns in Hcc and all cross blocks, not only in its gradient.

At each linearization H is coherent GN plus the native intrinsic solve
regularizer, evaluated with the same formula at that state. The regularizer
is excluded from the scored objective and from the gradient. D is never
recomputed. The two-LM control uses lambda_champion for both sequential
steps, relinearizing at its accepted first state in the fixed q chart.
It is a **fixed-chart coherent LM control**, not a native Eta2 rollout.

ROS2 uses gamma=1+1/sqrt(2), h=1/lambda_champion and
`K=H0+(lambda_champion/gamma)D`. Solve `K k1=b1=-g0`; evaluate the un-clipped
stage `qstage=k1/gamma`; then solve
`K k2=b2=-gstage-2(lambda_champion/gamma)D k1`.
The raw final direction and its right-hand side are

```
dROS=(3 k1+k2)/(2 gamma)
bROS=(3 b1+b2)/(2 gamma), so K dROS=bROS.
```

For the separately reported radius-feasible ROS proposal, scale only its
camera combination by `alpha=min(1,R/||E_saved^-1 dROS_camera||)`, then
complete its points from **the combined RHS**:

```
dpoint=V_stage^-1 (bROS_point-W^T dcamera_clipped).
```

This reproduces the raw linear combination when clipping is inactive. When
clipping is active it retains the ROS point forcing; using `-g0_point`
instead would silently substitute an LM point proposal. The internal stage
is not clipped. A non-finite stage is an invalid/rejected method, not an
invitation to change coefficients or silently move the stage.

LM1 and each LM2 increment use the same saved E-radius, with point completion
from that step's own RHS and point factor. The second LM increment is added
to q1, not composed as a new native camera tangent. Each step is accepted
only when the full original objective decreases, its full undamped GN
prediction is positive and rho>0.1. Rejected steps keep the prior q. There
is no retry, radius update, damping update, or line search in this witness
diagnostic. Raw proposals remain visible independently of acceptance.

The small camera Schur systems use FP64 dense Cholesky and per-point
augmented-Jacobian QR. Factor reuse is confined to ROS2's fixed two-RHS
operator. No Krylov vectors exist in this reference. Each full solve must
pass explicitly recomputed D-whitened full-normal residual <=1e-10, allowing
at most five fixed-factor residual corrections. Every such correction is
charged. A failed certificate stays invalid, without a changed damping or
an unreported approximate-solve substitution. No shared setup is omitted
from a timed arm and no matrix arrays are persisted to disk.

Coefficient source independently checked:
[KPP ROS-2 documentation](https://kpp.readthedocs.io/en/stable/num_methods/rosenbrock-methods.html).
Second-order consistency and arbitrary approximate-Jacobian cancellation
are tested on toy flows before any witness evaluation. The order of a flow
integrator is not a theorem of faster optimization.
