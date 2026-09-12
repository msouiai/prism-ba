# D0v1 result: fixed custom reductions were insufficient

D0v1 was the first preregistered repeatability gate for the wave-6
measurement substrate.  It replaced the solver's atomic camera/point
assembly, Schur point accumulation, nonlinear-cost reduction and strict
full-model reduction with fixed ownership and fixed reduction trees.  The
derived binary was numerically compatible when the feature was disabled:
on `ladybug-539-1.01`, the median final-cost difference from B6v7 was
`-2.44e-14` relative over three paired repetitions.

The deterministic arm nevertheless failed exact repeatability on both tail
scenes.  Five Venice-52 runs ended at five different costs
(`246158.96`--`247894.13`) and five Final3068 runs ended at five different
costs (`1743542.86`--`1932636.81`), with only one Final3068 target hit.  State,
accepted-cost-trajectory and decision hashes were unique in every repetition.

The earliest observable divergence was already present in the outer-0
camera-step norm on Venice at roughly `3e-15` relative.  On Final3068 the
first norm or trust-ratio difference appeared by outer 1--2.  This localised
the remaining uncontrolled reduction to source-level cuBLAS dot products and
norms, which feed CG recurrences, forcing decisions and radius clipping.
D0v2 therefore adds fixed-tree replacements for every source-level
`cublasDdot` and `cublasDnrm2` call.  The v1 rows remain negative localisation
evidence and are not pooled with v2.

Machine-readable evidence is in `d0v1-registration.json`,
`d0v1-results.json`, and `d0v1-summary.json`.
