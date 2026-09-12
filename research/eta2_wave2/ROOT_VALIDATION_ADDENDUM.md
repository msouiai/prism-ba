# Independent-arithmetic gate, before validation and native grid

Native witness solves certify the coherent GPU reduced residual at1e-10. As
wave1 already measured, an independent CPU full-normal calculation need not
match that threshold (published discrepancies reached3.28e-6). The additional
gate is fixed here **before the root-direction CPU checks**: full scaled normal
relative residual<1e-5, CPU/native final-cost difference<1e-8 relative, plus
the unchanged native reduced certificate. This permits known independent
arithmetic sensitivity and is not an exact-full-GN claim. No threshold will
be increased after these new checks. The ensuing native solver remains inexact
Eta2, so this gate validates the witness mechanism, not a production1e-10 solve.

W5 independently recomputed finite-difference RHS discrepancies are a separate
issue: observed full-normal ratios span6.54e-8 to8.09e-3. Nonlinear gains agree,
but those second solves are not certified independent full-normal1e-10 steps.
Their native extension stays pending the derivative/transport audit, rather
than silently borrowing this root-direction validation tolerance.
