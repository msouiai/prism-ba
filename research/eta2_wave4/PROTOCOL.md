# Wave 4 registration — orthogonal reformulations

Registered before wave-4 scores, on `research/eta2-wave4`, parent 3754978.
Reference remains the frozen Eta2 source/configuration. Verify source/header
and binary hashes in this session before comparisons. Do not change the original
algorithm or scored observations: plain L2, SIMPLE_RADIAL, unshared intrinsics,
k2=0. Staging objectives must be explicitly labeled; only the full original
objective may determine target hits. All opening, transfer, setup and detection
costs are charged. No per-scene flag selection after results.

Targets: Venice52 243740.27; Final3068 1744796.9841897595. Tails N=5 per cell,
native outer cap 600 and solve budget 60 s unless a separate registration gives
a different diagnostic limit before launch. Practical cells are the unchanged
nine tolerance cells on Ladybug539, Trafalgar138 and Final394, N=3. Alternate
arm order by repetition and serialize GPU work. No compaction or heavy CPU
forensics during scored timing. Native endpoint rescoring is independent FP64.
Initial score, accepted/rejected outers, retry fraction, PCG depth, lambda,
radius, raw/radius, eta and rho remain recorded. Both directions of timing
crossings and all failed target rows are retained. No pooling of fresh cohorts.

## First gates

Aside: derived off, rho_min=0.001, rho_min=0.01, nonmonotone window M=5.
Single monotone-threshold changes retain the existing radius/lambda updates.
For the nonmonotone arm, reference is max(current and last four accepted costs);
require finite candidate, positive current quadratic prediction and
reference-minus-candidate >0.001*prediction. Update radius/lambda from the
CURRENT-cost rho, so low/negative agreement still shrinks the radius. Export
the lowest full-L2 state visited (extra storage/copies/time counted), report
uphill accepts and both best/current costs. Best-state restoration is not a
restart or a new search. No source or target changes within the scored cohort.
Compatibility original/off N=3 Dubrovnik88, then both tails N=5 for all arms.
Only an observed tail gain without an opposite-tail loss earns nine-cell N=3.
No causal threshold explanation inferred merely from an endpoint win.

O3 first: replay preserved E4 hit/miss accept-6 and accept-7 states, original
three Final3068 stop witnesses, and calm Ladybug539 opening captures. Compute
quadratic, rational-geometry and true retracted per-observation predictions.
SIMPLE_RADIAL distortion is retained. Record all denominator-relative changes
and signed-depth transitions; BAL does not universally use positive depths.
Use |delta Z| <= kappa*|Z|, kappa=0.3,0.5. Attribution flag is relative rational
vs linear residual-model disagreement >0.5, normalized by the larger of the
observation's current squared residual and the scene median, with numerical
floor 1e-24. Also report rankings continuously, so a flag is not tuned to the
known point. Healthy flag fraction >0.001 kills a proposed always-on detector.
Constrained native solver requires a successful sparse witness active-set
test, verified feasibility/KKT and a small measured active set; rank-one
penalties are not silently substituted for exact active constraints.

O4: sensitivity trigger ||J_point||_F^2 / median >1e4, and report the plain
inverse-depth-squared alternative separately. Healthy trigger fraction >0.0001
kills that trigger before native implementation. At E4 perform the requested
ray-constrained replay and report the actual residual under the UPDATED camera,
not a falsely zero residual under a frozen anchor. The final full-L2 score
includes this observation. Cost-only substitution is labeled diagnostic; a
controller-branch or basin claim requires actual replay. No automatic claim
that a high Jacobian norm is a high statistical residual weight.

## Subsequent arms

O5 robust-to-L2: preregister one data-normalized Cauchy-scale schedule before
the first native score; robust stages use a consistent robust model, gradient
and actual robust acceptance. Full-L2 cost is logged throughout; all scored
targets and final stage are plain L2. Include stage transition overhead and
force a true L2 stage rather than reporting a favorable robust endpoint.

O1: read the specified primary papers and numerically audit the object-space
surrogate before building. Equality of costs at a state is not gradient
consistency or majorization. Resolve similarity collapse and signed-depth
constraints explicitly; do not label unconstrained all-zero geometry a convex
opening success. Frozen rotations/intrinsics/weights give a convex translation
and point subproblem, not global optimality of the full alternating method.
Requested k=3,5,10 openings each get N=5 tails after correctness gates; panel
only after a Final3068 hit-count improvement. Details registered before scores.

O2: audit and implement the fixed-depth projection schedule 0,.25,.5,.75,.9,1
with two accepted outers per stage (bounded attempts), ordinary storage and
unchanged Eta2 controller. At s=0 radial distortion still makes the residual
nonlinear in camera coordinates. Audit residual/Jacobian consistency and the
s=1 identity first. N=5 tails after compatibility; overhead includes the full
path and handover. Separate registration fixes attempt limits before scores.
The user explicitly permits a second agent on this independent O2 work.

O6 remains gated on O1 establishing that the translation/point subproblem
changes the basin. No expensive SOCP or structureless opening without that gate.
Negative pre-tests are reported as such, not as native performance refutations.

## Evidence and literature

Read the cited primary sources before the relevant implementation. Store a
mathematical/prior-art audit with direct links; claims of novelty remain
provisional. Residual rationality, signed depths, rotation/point cross terms,
surrogate gradient consistency and hard-constraint semantics are checked rather
than assumed. Keep endpoint exports durable and verified. RAM stages large
diagnostics only. Reserve sufficient disk space before a grid; no unique prior
evidence is disposable. Frozen sources and baseline defaults remain unchanged.
