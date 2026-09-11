# Convergence figures

Each figure has a PNG preview and an exportable PDF in this directory.
`plotted_traces.csv` contains all displayed points. Regenerate with
`python3 research/geometry_agenda/plot_results.py` from the repository root.

| Figure | PNG | PDF |
|---|---|---|
| T2 curved steps | [Preview](t2_mechanism.png) | [PDF](t2_mechanism.pdf) |
| T3 point relaxation | [Preview](t3_mechanism.png) | [PDF](t3_mechanism.pdf) |
| T4 controlled and real transfer | [Preview](t4_controlled_and_real.png) | [PDF](t4_controlled_and_real.pdf) |
| T5 robust continuation | [Preview](t5_robust_continuation.png) | [PDF](t5_robust_continuation.pdf) |
| T6 depth smoothing | [Preview](t6_depth_smoothing.png) | [PDF](t6_depth_smoothing.pdf) |
| T7 spectral menus | [Preview](t7_mechanism.png) | [PDF](t7_mechanism.pdf) |
| T8 complete policy runs | [Preview](t8_closed_loop.png) | [PDF](t8_closed_loop.pdf) |

Synthetic examples use the first held-out seed by index, not the best outcome:
100, or 300 for separately registered T4 v2. All three repetitions are shown;
the median-time repetition is bold. Lines are steps between evaluations,
not interpolation of unmeasured objective values. The horizontal dashed line
is the fixed target. Curves describe CPU mechanism prototypes with fixed
intrinsics; they are not native GPU/Caspar comparisons. Complete cohort
statistics and geometry failures are in the corresponding track reports.

T5 plots the final robust objective even during intermediate continuation
stages. T6 plots original point cost even while smoothing. These values may
rise during continuation, and early crossings do not count as final-stage
target hits. Low reprojection cost is not a geometry-success certificate.
