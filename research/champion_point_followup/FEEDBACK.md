# Feedback to the Astra research adviser

We implemented the point-path suggestions in the real Eta2 CUDA champion, not
only the CPU reference. The original solver remains frozen. All artifacts are
in `research/champion_point_followup` on `research/champion-point-combinations`.

Fresh held-out geometric cases reproduce the specialized low-parallax benefit:
point polish 1.369x, virtual rays 1.169x over CPU XYZ LM, N=3 on six new cases.
Neither improves the depth or joint-rotation families. Geometry is still weak.

The native GPU screen tested all-track polish, <=5-degree track-gated polish,
virtual rays, relaxed dynamic forcing cap (.5 -> .8), and all three point/forcing
combinations against the frozen champion. Three full BAL scenes, N=3, identical
pre-registered targets. Nothing improves general time to target. Dubrovnik polish
reduces 10 outers to 6 and 77 matvecs to 66, but costs .187 s vs .165 s after
charging the extra work. Ladybug regresses across all additions. Venice reaches
different basins and illustrates why monotone pointwise cost improvements do not
ensure faster global convergence. Native overlays recompute the model on the
actual corrected displacement; they are not the exact CPU tangent-scored path.

A follow-up uses the existing model-agreement rho <= .25 to trigger point repair
only on problematic attempts. Conditional polish is near neutral on Ladybug and
Dubrovnik. Venice N=10 reaches the tight target 10/10 vs 6/10 for its matched
champion, but takes 1.177 s vs .946 s conditional on success. Two-sided exact
Fisher p=.0867, exploratory. Original and generated binaries each independently
hit 7/10 on Venice, so baseline target variability is real. Do not mix cohorts.
At 1% target tolerance both hit 3/3 and Eta2 is faster: .402 vs .460 s. The user
values speed at essentially equal quality, so this does not replace Eta2.

The remaining useful hypothesis is rare nonlinear point repair as a target-
attainment aid, especially when model disagreement is point-dominated. To help
speed, it must avoid most of the additional projection/model/cost passes. A
per-track parallax threshold alone does not predict whether repair pays for
itself. Looser Schur stopping saved products on frozen CPU systems but failed
as a native nonlinear-controller change. Keep those two evidential claims
separate. No larger-scene promotion gate passed, and no new novelty is claimed.
