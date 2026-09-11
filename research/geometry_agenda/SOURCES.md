# Primary-method source ledger

Methods, equations and implementation contracts were inspected, rather than
relying on abstracts. Reading date: 2026-09-11. Preprints remain preprints;
the tests here establish neither publication priority nor universal superiority.

| Source | Inspected material | Consequence for this agenda |
|---|---|---|
| [ParallaxBA (2018)](https://arxiv.org/html/1807.03556) | III-A–D, equations 9–10 | Ray-direction objective differs from pixel reprojection; not an identical-objective control. |
| [Square Root BA (2021)](https://arxiv.org/html/2103.01843) | 4.1–4.4 | QR elimination and augmented damping are algebraic alternatives, not nonlinear model repairs. |
| [Geodesic acceleration (2012)](https://arxiv.org/html/1207.4999) | Equations 9–15, acceleration safeguard | Direct ordinary-LM geodesic comparator required; curvature acceleration is established. |
| [RNC-LM (2026-07-08)](https://arxiv.org/html/2607.07623) | Algorithm 1, fixed factor and higher directional derivatives | New RHSs with reused LM factors are already explicit prior art. |
| [Ceres inner iterations](https://raw.githubusercontent.com/ceres-solver/ceres-solver/master/docs/source/nnls_solving.rst) | Inner Iterations and `use_inner_iterations` | Post-acceptance nonlinear point optimization is a necessary simpler control. |
| [PoVar (2024)](https://arxiv.org/html/2405.05079) | 3.2 and 4.1–4.2 | Its projective/object-space reduction is not identical to unconverged pixel-space point polishing. |
| [Multigrid for BA (2020)](https://arxiv.org/html/2007.01941) | 3.1–3.6, approximate modes and aggregate QR | Setup and coarse-space quality must be charged; linear collective modes are established. |
| [Ni, Steedly, Dellaert (2007)](https://dellaert.github.io/files/Ni07iccv.pdf) | 3.1–3.4, local base frames/separators | Close prior art: finite submap transforms alone are not novel. |
| [FAS-RASPEN (2016)](https://arxiv.org/html/1605.04419) | Section 3, equations 20–22 | Nonlinear coarse correction is established; its convergence claims do not transfer to our restricted manifold. |
| [Graduated filter methods (2020)](https://arxiv.org/html/2003.09080) | Sections 4–5, equations 5 and 8 | Adaptive residual scaling already exists; incremental observability information must earn its cost. |
| [Triangulation-Free BA/GNC (2026-08-26)](https://arxiv.org/html/2608.21008) | 3.3–3.5 | Ray-time variables, pose priors and loss continuation change the comparison contract. |
| [ProBA v2 (2026-04-07)](https://arxiv.org/html/2505.20858) | 3.1–3.4 | Probabilistic landmarks use a different likelihood; T6 returns to the original loss. |
| [PowerBA (2022)](https://arxiv.org/pdf/2204.12834) | 4.1–4.3, equations 11–34 | Fixed-Schur inverse expansion differs from changing the OCA response filter. |
| [OCA v2 (2025-04-01)](https://arxiv.org/html/2411.06343) | 3.1–3.2, equations 13–20 | Optimal-control recursion and orthographic imaging example; not a new control-theory derivation here. |
| [A Game of Bundle Adjustment (2023)](https://arxiv.org/html/2308.13270) | Section 3, state/action/reward and SAC policy | Learns damping; reward includes elapsed iteration time and terminal bonus. T8 changes actions, not the fact of learning. |
| [SciPy 1.16.2 `cho_solve`](https://docs.scipy.org/doc/scipy-1.16.2/reference/generated/scipy.linalg.cho_solve.html) | Input factor contract | A fixed Cholesky factor accepts a new RHS; changed matrices require refactorization. |

The source papers motivate controls and limitations. Every speed, failure and
geometry number in the accompanying results comes from the saved experiments,
not from extrapolating a paper's benchmark. Track reports state the narrower
inferences supported by those experiments.
