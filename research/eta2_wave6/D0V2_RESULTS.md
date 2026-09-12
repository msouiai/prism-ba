# D0v2 result: fixed BLAS reductions were still insufficient

D0v2 added fixed-tree replacements for every source-level cuBLAS dot product
and norm.  The disabled path again passed compatibility: its median final
cost differed from B6v7 by `1.62e-14` relative on the registered calm cell.

Exact repeatability still failed.  Venice-52 produced five endpoint costs in
`246347.38`--`247555.76`; Final3068 produced five in
`1736752.97`--`1818374.45`, with four target hits.  Every endpoint state,
accepted-cost trajectory and decision trace was distinct.

The first Venice difference remained in the outer-0 camera-step norm.  Code
path tracing found that the sub-128-camera preparation path still formed the
reduced RHS and Schur diagonal with the atomic `MFRhsDiagFused` kernel.  On
Final3068 the first camera solve was identical, but the accepted point step
was formed by the atomic `MFPass1` candidate-scoring path; the next outer then
started from a different state.  D0v3 replaces these two missed sites with
camera-owned and point-owned fixed reductions.  D0v2 rows are not pooled with
v3.

Machine-readable evidence is in `d0v2-registration.json`,
`d0v2-results.json`, and `d0v2-summary.json`.
