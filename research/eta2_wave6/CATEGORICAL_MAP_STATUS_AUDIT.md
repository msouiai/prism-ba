# Categorical-map status audit against the completed campaigns

The supplied categorical map was written before all wave-5 and wave-6 results
were available.  This audit prevents apparently untried cells from being run a
second time under a different label.

## Highest-ranked cells

| Map cell | Current evidence | Status after audit |
|---|---|---|
| Deterministic reductions and paired comparisons | D0/D1 built the deterministic instrument, paired inputs, and SPRT tooling. | Completed as measurement infrastructure. |
| Opening FTLE | D2/D2b/D2c/D2d show a finite FP32-fragment jump; FP64 restores perturbation-scale behavior. | Completed; no scale-consistent positive FTLE established. |
| Effective resistance and k-core | C1 finds Final3068 camera 550, but observation count gives the same decision and the CPU graph pass costs about 6 s. | Diagnostic only; no prior arm earned. |
| Exact per-track algebra | Wave-5 A1 repairs the E4 witness almost exactly, but native Final3068 is unchanged and Venice worsens 4.15%. | Closed as an always-on policy. |
| Schur-Jacobi | Wave-5 B3 is 1.6% slower on the panel, 21.3% slower on Muell, and drops Final3068 from 4/5 to 1/5. | Closed. |
| Banded preconditioning | D5 finds a strong fixed-system spectrum change, but the structural gate requires camera half-bands 138--215 rather than the registered 16. | Closed for the sequence dispatch tested. |
| Nyström | D12's BA-sign-correct ranks 4/8/16 add their sketch products and save no post-switch products on the hard Muell system. | Closed. |
| Mixed-precision iterative refinement | Wave-5 B2 passes the FP64 residual gate but changes products by 1.07--4.40x and endpoints by up to 0.519%. | Closed. |
| Dense Schur Cholesky | Wave-5 B4 is 1.49--2.77x slower on Trafalgar; Venice spends 56.7 s in formation and 0.84 s in factor/solve. | Closed. |
| Square-root/nullspace products | Wave-5 B5 passes action and curvature audits, then loses both tails and is slower. | Retained only as an audit operator. |
| Soft/filter acceptance | D4's 60-pair result is unresolved and 1.077x slower; D10 finds no discriminating track-damage signal. | No production candidate. |

## Remaining speed cell selected next

Communication-avoiding PCG is materially distinct from the failed solver
changes above: it targets the two host-visible reduction phases in each
otherwise unchanged Hcc-PCG iteration.  Wave-5 B6v2 batches independent dot
returns but still has two reduction dependencies per iteration.  D14 first
tests the one-reduction Chronopoulos--Gear recurrence on frozen captured
systems.  It advances natively only if the synchronization saving exceeds its
one-product pipeline fill/drain cost on a hard system.

This is established Krylov algebra, not an Eta2 novelty claim.  Its purpose is
to decide whether the remaining synchronization ceiling on this single GPU is
large enough to exploit.

The completed D14 screen finds no crossover.  Reduction phases fall from 259
to 130 on the capped Muell system with a `1.0001x` time ratio; the converged
Muell system is `1.023x` slower because of its one extra product.  The native
gate fails, so this cell is now closed for the measured single-GPU path.
