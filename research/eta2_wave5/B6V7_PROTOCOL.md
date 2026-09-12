# B6v7 protocol: occupancy-gated deterministic preparation

Registered before building or scoring B6v7.

## Hypothesis and fixed rule

B6v6's camera-owned RHS reduction is faster on every practical cell and on
Muell, but its always-on arithmetic moves the Venice52 median endpoint by
+0.253%.  The kernel launches one block per camera.  This GPU has 22 streaming
multiprocessors; 52 cameras expose only 2.36 blocks per SM, while 128 cameras
expose 5.82.  The prior performance investigation also found the camera-owned
kernel unattractive at low camera counts.

Register one ordinary systems dispatch: enable B6v6 preparation only when
`ncam >= 128`; otherwise execute the dots-only path.  The threshold is fixed
from GPU occupancy before the new cohort and is not tuned per scene.  The rule
uses no objective, residual, scene identity or future solver state.

The two same-binary arms are:

- `dots`: B6v2 dot batching only;
- `gated`: dots plus B6v6 deterministic camera-major preparation for
  `ncam >= 128`.

Thus Venice52 must be path-identical between arms, while all nine practical
cells, Muell and Final3068 take the active path.

## Gates

1. Disabled-mode compatibility: N=3 against the frozen champion, below 0.15%
   relative endpoint difference.
2. Practical panel, N=3: geometric-mean target time faster than dots, no
   disjoint slower cell, and identical median products, outers and rejects.
3. Muell, N=3: no product movement and no disjoint target-time loss.
4. Tails, N=10 per arm on Final3068 and Venice52.  Final3068's rows may be
   pooled with the preregistered B6v6 N=10 cohort because both arms execute the
   same arithmetic there; report the fresh N=10 and pooled N=20 separately.
   Do not pool Venice because B6v6 deliberately used the active kernel there.

Promotion requires no lower Final3068 hit count in the pooled screen, no
Venice endpoint movement beyond 0.15%, and the stable speed gates above.  This
screen does not establish formal reliability equivalence.  A larger cohort
requires a separate registration.  Misses remain in every denominator and all
clocks are charged.
