# B6v6 protocol: deterministic camera-major reduced RHS

Registered before building or scoring B6v6.

## Question

B6v4 obtains its large-scene preparation gain by omitting the Schur diagonal
that classical LM immediately discards.  Its observation-major reduced-RHS
kernel still uses global atomics, and deleting the diagonal arithmetic changes
their arrival timing.  Final3068 is basin-sensitive enough that the resulting
N=30 reliability comparison remains uncertain.  Can a camera-owned reduction
keep the dead-work saving while making this part of the trajectory deterministic?

## Fixed intervention

Use the existing camera-major compact fragments and launch one 256-thread block
per camera.  Each block accumulates `W V_tau^-1 b_p` for its camera in FP64 and
writes the nine RHS values once.  The block uses a fixed binary-tree reduction,
has no global atomics, and receives a null diagonal pointer, so the discarded
Schur diagonal is not computed.  All other B6v4 fusions and B6v2 dot batching
remain active.  The scored objective, forcing rule, controller, candidates and
stopping rules are unchanged.

The three same-binary arms are:

- `dots`: B6v2 dot batching only;
- `dots-atomic`: B6v2 plus B6v4 observation-major preparation pruning;
- `dots-camera`: B6v2 plus B6v4 preparation pruning with the deterministic
  camera-major RHS reduction.

No parameter sweep is allowed.  `OCA_COMPACT_FRAGMENTS=2` and the other frozen
Eta2 flags are verified at runtime.

## Gates

1. Disabled-mode compatibility: N=3 against the frozen champion, relative
   median endpoint difference below 0.15%.
2. Nine-cell practical panel: N=3, fixed targets.  Proceed only if
   `dots-camera` is no slower than `dots` geometrically and has no cell with a
   disjoint slowdown.  Products, outers and rejects must match on stable cells.
3. Muell: N=3.  The camera arm must retain a measurable preparation saving and
   must not be slower than dots with disjoint ranges.
4. If both gates pass, Final3068 and Venice52 at N=10.  This is a screening
   cohort, not an equivalence proof.  A larger registered cohort is permitted
   only if the camera arm retains the speed signal and does not show a resolved
   tail loss.

Report both directions for time and cost.  Misses remain in the denominator.
The frozen champion is never overwritten or relabelled by this experiment.
