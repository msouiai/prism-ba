# Prism novelty audit and mathematical scope

Status: prior-art and mechanism analysis; experimental claims belong to the
new frozen study, not this derivation. No claim of being the first BA use of
multi-shift CG has been established by this search.

## Prior-art boundary

| Ingredient | Established work | Consequence for Prism's claim |
|---|---|---|
| Several scalar shifts from one Krylov space | [Jegerlehner, 1996](https://arxiv.org/abs/hep-lat/9612014) | The shifted-CG recurrence and matvec sharing are not new. |
| Avoiding repeated solves after a rejected BA step | [Lourakis and Argyros, ICCV 2005](https://users.ics.forth.gr/~lourakis/publ/2005_iccv.pdf) | Compare with Dogleg; “avoid retries” alone is not novelty. |
| Existing trust-region and line-search methods | [Ceres solver documentation](https://ceres-solver.readthedocs.io/latest/nnls_solving.html#dogleg) | Armijo decrease and Dogleg interpolation are established. Ceres Dogleg requires exact factorization; hardware costs must be labeled. |
| Efficient trust-region solves inside a Krylov space | [Gould, Lucidi, Roma and Toint, 1999](https://www.numerical.rl.ac.uk/media/people/nick-gould/GoulLuciRomaToin99_siopt.pdf) | Reusing a Krylov basis to control a trust-region step is also established. Explain why discrete nonlinear candidate scoring and BA block damping add value beyond reduced trust-region solves. |
| Efficient alternatives for the Schur solve | [Power Bundle Adjustment, CVPR 2023](https://arxiv.org/abs/2204.12834) | Position against alternative linear solvers, not just plain CG. |
| GPU nonlinear optimization and BA | [Caspar, ICRA 2026](https://arxiv.org/abs/2605.30583) | A CUDA implementation by itself is not sufficient novelty; compare precision and actual nonlinear quality. |

The closest identified precedent is **LM-RLSQR**, [Lin, O'Malley and
Vesselinov (2016), sections 3–4](https://agupubs.onlinelibrary.wiley.com/doi/10.1002/2016WR019028).
It reuses a Golub–Kahan/LSQR basis for multiple damping parameters and chooses
the candidate giving the lowest nonlinear objective. Thus the combined idea
of amortized damping candidates plus nonlinear selection already exists,
not merely its individual linear-algebra ingredients. Prism must establish
an additional BA-specific contribution, such as a demonstrably useful Schur
formulation and globalization policy. A GPU implementation alone does not
establish a new optimization principle.

[Scalable adaptive cubic regularization methods (2021)](https://arxiv.org/abs/2103.16659)
also considers concurrent shifted systems in nonlinear optimization. The
relationship to its regularization rule needs to be distinguished from LM's
discrete candidate scoring; changing the application does not erase this
prior-art boundary.

A plausible contribution is the combination of compatible block damping,
shared candidate search, and a full-step safeguard, with evidence identifying
when each part pays. Its distinctiveness is conditional on the controlled
ablations and a broader literature review. Negative search results do not
prove absence of prior work.

## Proposition 1: camera shifts cannot generally bound the point step

Let `H = [[A,W],[W^T,V]]`, gradient `g=(g_c,g_p)`, fixed point damping
`P=V+tau D_p` positive definite, and camera damping matrix `D_c` positive
definite. The damped equations are

```
(A + lambda D_c) d_c + W d_p = -g_c
W^T d_c + P d_p = -g_p.
```

Elimination gives

```
(S + lambda D_c) d_c = -g_c + W P^-1 g_p,
S = A - W P^-1 W^T,
d_p = -P^-1 g_p - P^-1 W^T d_c.
```

With the linearization, P and D_c fixed, `d_c=O(1/lambda)` as
`lambda -> infinity`; therefore `d_p -> -P^-1 g_p`, generally nonzero.
Thus increasing every camera shift cannot guarantee an arbitrarily small full
step. This is elementary block elimination, not claimed as a new theorem.
It identifies a failure mechanism particular to a camera-only shift menu.

A nonlinear counterexample uses residuals `r1(c,p)=c+p^2-1`, `r2(c,p)=c`
at `(c,p)=(0,epsilon)`. The Jacobian has full rank for epsilon nonzero, yet
with tau=0 the limiting point increment is `(1-epsilon^2)/(2 epsilon)`.
As epsilon approaches zero the full step is unbounded and its nonlinear cost
can become arbitrarily worse even as the camera increment approaches zero.
This toy example demonstrates the mechanism; it is not a statistical model
of BAL data.

## Proposition 2: the compatible family of shifts

For fixed S and positive definite D_c, put `d_c=D_c^-1/2 y` and left-multiply
by `D_c^-1/2`. Then

```
(D_c^-1/2 S D_c^-1/2 + lambda I) y
    = D_c^-1/2 (-g_c + W P^-1 g_p).
```

The operator before lambda, the right-hand side and the transformation must
all remain fixed across candidate shifts. With zero initial guesses this is
a standard shifted family. The identity
`K_m(K+sigma I,b)=K_m(K,b)` follows from the binomial expansion in both
directions. For CG, additionally require the relevant shifted operators to
be symmetric positive definite and account for finite-precision residual drift.

Changing point damping per candidate changes both S and the RHS:
`S(tau2)-S(tau1)=W(P(tau1)^-1-P(tau2)^-1)W^T`, which is generally not a
scalar identity shift. A different RHS also generally destroys initial
residual collinearity. Exceptions exist (e.g. special W or g_p); there is no
generic license to reuse the scalar-shift recurrence for joint damping.
A general preconditioner can also break the required structure; the actual
congruence and corresponding damping metric must be stated, not just labeled
“preconditioned multi-shift CG.”

## Proposition 3: what the safeguard guarantees, conditionally

Let `phi(alpha)=F(Retract_x(alpha d))`, with differentiable retraction and
`phi'(0)=g^T d<0`. Suppose on a neighborhood of zero

`phi(alpha) <= phi(0) + alpha g^T d + (L/2) alpha^2 ||d||^2`.

For Armijo coefficient `c1 in (0,1)`, every positive alpha in that neighborhood
satisfying

`alpha <= 2(1-c1)(-g^T d)/(L ||d||^2)`

passes Armijo. An unbounded geometric backtracking sequence therefore finds
an acceptable step under these assumptions. Prism only tries
`1/2, ..., 1/256`, so acceptance is guaranteed only if its tested range
contains such a step. A descent direction alone does not guarantee rescue
within eight trials. On failure, Prism returns to its existing damping retry.

For an exact solution of a positive-definite damped full system B,
`Bd=-g`, descent follows from `g^T d=-d^T B d<0`. For an approximate solution
with residual `e=Bd+g`,
`g^T d=-d^T B d+d^T e`; a sufficient condition is
`||e|| < lambda_min(B)||d||`. The implementation checks the actual directional
derivative, rather than assuming this condition from a camera-only residual.

These statements do not establish convergence of the whole deployed method.
A full convergence proof would additionally need uniform sufficient descent,
control of accepted step sizes, appropriate treatment of gauge freedoms,
conditions on the damping update and inexact solves, and an unbounded
iteration process. The fixed 600-outer budget, early-iteration guard and
bounded line search do not provide those premises automatically.

## Falsifiable experimental claims

1. A/B/C/D distinguish one versus five shifts and safeguard off versus on.
   If B matches D, multi-shift selection has not earned its cost.
2. A fixed-operator shared/independent CG audit isolates linear amortization.
   Speed is only meaningful when both meet the true residual target.
3. External fp32 costs are reevaluated in fp64 using original observations.
   Native float cost is not a quality oracle.
4. Held-out evaluation and perturbed initializations test whether early guards
   encode development-specific basin choices. Failure is retained as evidence.
5. Ceres joint-damping LM/Dogleg determine whether simpler globalization
   methods reproduce the benefit. Their CPU implementation is not presented
   as an equal-GPU execution control.
