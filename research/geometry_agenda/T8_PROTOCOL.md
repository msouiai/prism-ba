# T8 registration: computation allocation

Registered after T7's negative gate, before collecting T8 outcomes. No native
solver changes. Same six-DOF CPU reference, original L2 objective, explicit
seven-coordinate gauge, finite and signed-depth checks throughout.

Each decision first creates one ordinary LM linearization, factorization,
step and true-cost evaluation. This immutable cache defines the following
alternatives: commit the ordinary step and relinearize next; one more OCA
recursion; a new lambda/3 factorization; safeguarded geodesic acceleration;
one point-polishing step on the ordinary trial; eight nonlinear coarse steps
using automatic confidence-weighted partitioning. All alternatives retain
the ordinary trial as a fallback. The lowest valid decreasing eligible full
state wins; coarse and polishing proposals pass strict true-cost descent,
while model-based proposals also require positive GN prediction and rho>.1.
This explicit distinction applies identically to all schedules.

Factors and Jacobians are private to their parent. Point polishing and coarse
transforms produce independent whole states; choosing one invalidates the
old numerical cache. A failed extra action leaves the ordinary fallback
available. A true-cost evaluation is mandatory, not a skippable learned action.

Replay initial and three-attempt LM snapshots, N=3 timing, from depth and
clustered (four bridges) development seeds0–9. Save each state, lambda,
parent hash, cache contract, action/cost/timing/work outcome. No rotation or
BAL data enter training. Features are computed before the alternative action:
ordinary trial defect, fractional depth risk, base rho/validity, concentration
of residual energy, diagonal-scaled gradient split, point information ratio,
and current residual RMS. Charge feature extraction and inference.

Diagnostic local utility is decrease in log reference gap per elapsed second,
clamped at the fixed target. The reference is truth cost on synthetic data and
the existing frozen T4 reference on sampled BAL. It is used only in training
labels/evaluation, never as a deployment feature. This one-decision hindsight
oracle is an upper bound on that local utility, not on global time-to-target.
Time includes the common ordinary trial, features, and chosen action; replaying
all alternatives is offline data-collection work, reported separately.

Compare a fixed ordinary schedule, always-OCA, always-new-lambda, always-geo,
always-point, always-coarse, a predeclared deterministic rule, and a depth-two
cost-sensitive decision tree. Tree thresholds and leaf actions are selected
using development action rates, with minimum leaf size five. No large model.
Deterministic rule: concentrated residuals (top 10% supply >80% energy) with
RMS>1 and depth-risk p90<.1 -> coarse; otherwise rejected high-defect (>.25)
ordinary trial -> geo; otherwise valid trial and point gradient share>.8 ->
point; otherwise rho>.75 -> OCA; otherwise commit ordinary.

Closed-loop test: N=3, ten new seeds100–109 of depth and cluster families
(secondary seed transfer), ten rotation seeds100–109 (unseen generator family),
and the three frozen sampled BAL cases (unseen real families). Each arm has
80 decisions/2 seconds and the same previously defined target. Rotate arm order.
Record misses, full cost/time curves, geometry, counts and all overhead.

Promotion requires 1.10x over ordinary and the deterministic rule on both
synthetic family transfer and real samples, no additional target misses or
geometric failures. Always-action controls expose whether a policy merely
selects a generally superior computation. Only consider sequential RL if
closed-loop evidence shows that useful short-horizon choices damage longer
progress and a simple policy leaves transferable headroom. Negative transfer
or feature overhead closes the current learning branch without RL.

Implementation correction during held-out replay: rotation108 exposed a
singular automatic coarse metric. The uncaught Cholesky exception aborted
collection. Record this as a failed action and retain the already evaluated
ordinary fallback, charging the failed work; do not regularize the diagnostic
metric or remove the parent. The policy remains frozen from development.
The aborted log is preserved; held-out collection is restarted with the
same states and actions. An injected-failure test verifies the fallback.
