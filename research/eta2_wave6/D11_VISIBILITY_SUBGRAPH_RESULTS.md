# D11 result: the subgraph is an excellent linear approximation with no production-time solver

## Verdict

The q=3 generalized visibility-subgraph preconditioner is the strongest fixed
linear-algebra signal found in this campaign: on Muell outer 12 it reduces the
same-residual solve from 42 matrix-free products to 2.  A CPU sparse LDLT with
reused symbolic ordering takes 111.59 ms to factor and 7.77 ms to solve, for
119.36 ms versus the frozen GPU Hcc path's 131.19 ms.  Thus the deliberately
narrow fixed-system gate passes.

It is **not** promoted.  Forming the numeric q=3 matrix in the serial reference
takes another 301.38 ms, leaving only 11.83 ms of theoretical budget for a
production formation path.  More decisively, neither available GPU sparse
Cholesky backend is usable: the deprecated cuSolver low-level path failed to
finish Ladybug analysis/factorization in 90 seconds, and NVIDIA cuDSS 0.8.0.10
spent more than 60 seconds in symbolic analysis on the same control.  The
universal arm is also catastrophic on easy systems: Ladybug retains three
products but factor-plus-solve grows from 1.85 ms to 605.47 ms.  A hard-event
dispatch would avoid that row, yet on Muell its entire measured margin is only
11.83 ms before numeric formation.  No native Eta2 change is justified.

## Fixed results

All rows use the unchanged captured operator, RHS, damping, scaling, eta=0.5,
and true-residual verification.  Timings are medians of three warm repetitions.

| Scene / arm | Products | True relative residual | Numeric factor | Solve | Factor + solve |
|---|---:|---:|---:|---:|---:|
| Muell frozen GPU Hcc | 42 | 0.497297 | 0.11 ms setup | 131.09 ms | 131.19 ms |
| Muell host calibration q=0 | 42 | 0.497297 | 0.19 ms | 133.73 ms | 133.92 ms |
| Muell GSP q=2 | 129, cap miss | 0.77120 | 82.70 ms | 582.38 ms | 665.08 ms |
| Muell GSP q=3 | **2** | 0.496552 | 111.59 ms | 7.77 ms | **119.36 ms** |
| Ladybug frozen GPU Hcc | 3 | 0.467380 | 0.10 ms setup | 1.74 ms | 1.85 ms |
| Ladybug GSP q=3 | 3 | 0.445175 | 594.83 ms | 10.64 ms | 605.47 ms |

Muell q=3 retains 915,496 binary cross factors and produces 9,956 camera
off-diagonal blocks.  Its LDLT factor has 1,122,668 scalar entries, 5.70% of a
dense 4,437 by 4,437 matrix.  It removes 95.24% of the matrix-free products.
The q=2 discontinuity is real: retaining less information creates a much worse
preconditioner and reaches the 128-iteration cap.  Subgraph size is therefore
not a monotone cost-quality knob in this system.

Ladybug q=3 has 9,795 camera edges and 2,739,880 factor entries.  The stronger
preconditioner does not save one product.  Final1936's q=3 topology has 178,084
camera edges; its numeric reference path was terminated after 60 seconds.  Its
frozen Hcc solve already needs the theoretical minimum of one iteration plus
one verification product (16.35 ms), so a direct preconditioner cannot win
there.

## Mathematical interpretation

Retaining at most three cross factors per landmark while keeping every unary
factor gives a positive-semidefinite full Hessian by construction; eliminating
the points preserves that property.  This is why the experiment uses the GSP
factor representation rather than scalar effective-resistance sampling of
signed 9x9 Schur blocks.  The latter has no direct Spielman--Srivastava
spectral guarantee.

The Muell row establishes that visibility-selected landmark factors can encode
nearly all RHS-relevant long-range coupling.  It does not establish a faster BA
solver: sparse factorization and numeric formation are the dominant operations,
and stronger finite-eta directions have already changed Eta2's nonlinear
trajectory adversely in the Schur-Jacobi study.  The reusable asset is the q=3
matrix as a diagnostic/reference operator.  A future backend with millisecond
refactorization could reopen it; the present GPU stack does not supply one.

## Reproduction and provenance

The protocol is `D11_VISIBILITY_SUBGRAPH_PROTOCOL.md`.  Source, build command,
binary and cuDSS hashes are in `d11_visibility_subgraph/evidence/`; parsed rows,
gates and source hashes are in `d11-visibility-subgraph-results.json`.  The
cuDSS wheel was installed only in temporary storage and is not a repository
dependency.  The frozen champion and optimized candidate are unchanged.
