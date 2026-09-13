# D11 protocol: visibility-subgraph preconditioning

Registered before constructing a subgraph or running a new fixed-system solve.

## Question

Can a sparse direct preconditioner that retains selected camera--point cross
factors reduce Eta2's *total* linear-solve time on the hard Muell capture, not
merely its PCG iteration count?

This is a necessary-condition screen before any nonlinear solver change.  The
frozen operator, right-hand side, damping, scaling, forcing tolerance, and PCG
stopping rule remain unchanged.

## Construction

Use the existing frozen captures:

- primary: `muell-gba146`, outer 12, where Hcc PCG needs 41 iterations at
  `eta=0.5`;
- controls: `ladybug-598`, outer 8 (two Hcc iterations), and `final-1936`,
  outer 0 (one Hcc iteration).

Build the integer camera covisibility graph from the captured incidence.  Edge
weight is the number of shared landmarks.  Construct one deterministic
maximum-visibility spanning tree (descending weight, camera-id tie break), and
use edge length `1 / weight` for tree distance.

For every landmark, rank its observing cameras by mean tree distance to all
other cameras on that track, with camera id as the deterministic tie break.
The two registered GSP arms retain at most `q=2` and `q=3` cross factors per
landmark.  They retain **all** camera and landmark unary Hessian factors and LM
damping.  Dropped binary camera--point factors are replaced by their two unary
factors.  The resulting full Hessian, and therefore its camera Schur
complement, is positive semidefinite by construction.  This follows the
factor-level construction of Jian, Balcan and Dellaert (ICCV 2011); limiting
each landmark to q retained cross factors bounds each landmark-induced camera
clique.

Numerically factor the scaled reduced preconditioner with sparse LDLT and use
it in ordinary left-preconditioned CG on the unchanged GPU matrix-free Schur
operator.  `q=0` is a calibration arm: the same host sparse-factor and
host/device-transport path applied to Eta2's Hcc block diagonal.  It must
reproduce the Hcc iteration count and final true residual.  Any arm with a
failed/non-positive factorization is a miss, with no diagonal repair.

The topology is reusable for the whole nonlinear run.  Report separately:

1. one-time incidence/graph/tree/selection time;
2. per-attempt numerical assembly and factorization time;
3. preconditioner-application and host/device-transfer time;
4. matrix-free products and total solve time;
5. sparse nonzeros and factor nonzeros.

The serial CPU prototype's numerical assembly is reported but is not treated
as a production GPU timing.  The decisive implementation-independent quantity
is products saved.  Factor/apply/transfer timing decides whether a native GPU
implementation has enough remaining ceiling.

## Gates

A nonlinear GPU prototype is justified only if all conditions hold:

1. calibration matches Hcc within one PCG iteration and `1e-10` relative true
   residual;
2. on Muell, one of q=2 or q=3 reduces products by at least 30% at eta=0.5;
3. on Muell, its measured factor + solve time excluding serial prototype
   assembly is below the frozen Hcc total of 131 ms;
4. the same fixed q rule does not increase products on either control (a
   one-iteration control cannot improve, so equality passes);
5. sparse-factor fill stays below 20% of a dense camera matrix.

If multiple arms pass, choose the smaller q unless q=3 is at least 20% faster
after factorization.  If the gate fails, stop without altering Eta2.  If it
passes, the first native test is Muell plus the two controls; a practical-panel
or tail test is allowed only after that test wins total time and preserves the
registered nonlinear target.

## Prior-art boundary

- Jian, Balcan and Dellaert, *Generalized Subgraph Preconditioners for
  Large-Scale Bundle Adjustment*, ICCV 2011, select Hessian factors so a sparse
  subproblem can be factored directly.  This experiment is an implementation
  and transfer test, not a novel preconditioner.
- Kushal and Agarwal, *Visibility Based Preconditioning for Bundle
  Adjustment*, CVPR 2012, use shared-point visibility to construct cluster
  Jacobi and cluster-tridiagonal preconditioners.
- Spielman and Srivastava's scalar effective-resistance sparsifier theorem does
  not directly apply to Eta2's signed 9x9 block Schur couplings.  We therefore
  do not label scalar visibility sampling a spectral sparsifier of the BA
  operator.

Primary sources:

- https://dellaert.github.io/files/Jian11iccv.pdf
- https://grail.cs.washington.edu/wp-content/uploads/2015/08/kushal2012vbp.pdf
- https://doi.org/10.1137/080734029
