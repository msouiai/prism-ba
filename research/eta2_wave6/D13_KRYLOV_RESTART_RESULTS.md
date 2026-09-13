# D13 result: residual-minimising Krylov dominates PCG restart on fixed systems

## Verdict

The fixed-system experiment selects low-memory right-preconditioned GMRES(8)
for native testing.  It reaches Eta2's unchanged Euclidean relative-residual
gate on both hard Muell systems in two Arnoldi iterations plus one explicit
verification product.  The N=3 warm medians are 9.46 and 9.43 ms.  Periodic
PCG restart at depth 8, the best restart policy, needs 22 and 15 products and
68.21 and 46.58 ms.  Uninterrupted Hcc-PCG needs 128 products without reaching
the gate on outer 11 and 42 products / 130.67 ms on outer 12.

Across the two hard systems, GMRES uses 6 products and 18.88 ms, versus 37 and
114.79 ms for periodic restart: 6.17x less warm wall and 6.17x fewer operator
products.  This is a fixed-linear-system result, not yet an end-to-end BA speed
claim.

The memory gate passes.  GMRES stores only the nine residual-basis vectors for
an eight-vector cycle.  It recomputes `M^-1 v_j` while applying the small
backsolve coefficients and stores no preconditioned basis.  This adds cheap
9x9 block solves but no Schur products.  The explicit residual agrees with the
Arnoldi/Givens estimate to at worst `1.8e-15` on the hard systems, and maximum
measured basis nonorthogonality is `3.4e-17`.

## Fixed-system evidence

All rows use the frozen matrix, right-hand side, damping, Hcc block-Jacobi
preconditioner, and `eta=0.5`.  Products include exact residual replacement or
verification products.  Wall values are N=3 warm medians.

| System | Arm | Iterations | Products | Relative residual | Wall |
|---|---|---:|---:|---:|---:|
| Muell outer 11 | Hcc-PCG | 128 | 128 | 1.09826, miss | 399.41 ms |
|  | one restart at 8 | 52 | 54 | 0.47626 | 167.76 ms |
|  | periodic restart at 8 | 19 | 22 | 0.49212 | 68.21 ms |
|  | **GMRES(8)** | **2** | **3** | **0.44777** | **9.46 ms** |
| Muell outer 12 | Hcc-PCG | 41 | 42 | 0.49730 | 130.67 ms |
|  | one restart at 8 | 13 | 15 | 0.47889 | 46.61 ms |
|  | periodic restart at 8 | 13 | 15 | 0.47889 | 46.58 ms |
|  | **GMRES(8)** | **2** | **3** | **0.43872** | **9.43 ms** |
| Ladybug598 outer 8 | Hcc-PCG | 2 | 3 | 0.46733 | 1.73 ms |
|  | GMRES(8) | 2 | 3 | 0.41794 | 1.90 ms |
| Final1936 outer 0 | Hcc-PCG | 1 | 2 | 0.16686 | 16.05 ms |
|  | GMRES(8) | 1 | 2 | 0.16622 | 16.29 ms |

The shallow controls pay the same number of Schur products.  Their linear
solutions need not be bit-identical because GMRES and PCG optimise different
norms, but each satisfies the same gate with the same Krylov depth.

## Restart-depth diagnosis

Restart timing is highly state dependent.  On Muell outer 11, one-shot depths
4 and 16 still miss at 128, depth 8 needs 54 products, and depth 32 needs 44.
On outer 12, depth 4 is best at seven products, while depths 8, 16 and 32 need
15, 29 and 38.  Periodic-8 is the only restart rule that handles both, but the
large variation makes a fixed restart depth a brittle production policy.

GMRES directly minimises the norm Eta2 uses for its inexact-LM forcing rule.
PCG instead minimises the energy norm of the error, so its residual polynomial
can spend many Schur products improving a quantity the outer rule never tests.
The hard-system result confirms that this mismatch, rather than a missing
low-rank eigenspace, caused D12's restart signal.

## Next gate and claim boundary

The next arm is an opt-in GMRES(8) overlay on the checksum-pinned Eta2 source.
It must pass the registered practical time-to-target panel, Muell, and
Final1936 before any tail cohort.  The frozen champion remains unchanged.

GMRES, restarted GMRES, PCG and residual replacement are standard methods.
There is no novelty claim for the linear solver itself.  The research claim
available only if the native gate passes is the measured objective mismatch
between Hcc-PCG and a loose Euclidean inexact-LM forcing rule, together with a
GPU BA crossover where a residual-minimising nonsymmetric Krylov process is
faster end to end despite its extra reductions.

Exact rows, source, scripts, hashes and manifests are in `d13_krylov/` and
`d13-krylov-results.json`.
