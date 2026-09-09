# Re-triangulation repair — implementation brief for another agent

Self-contained: everything needed to reimplement the pass, plus the measured
behaviour you must know before deploying it. Reference implementation in this
repo: `gpu/oca_cuda.cu` — `KernelRetriangulate` (~line 2840) and the call
site gated by `OCA_RETRI=<k>` (~line 10904). All numbers below are N=3
medians vs converged f64 baselines unless stated.

## 1. What it is

Periodically, inside the LM loop, reset every 3D point to its closed-form
triangulation from the CURRENT cameras, keeping each reset only if that
point's own reprojection cost improves. It discards the point's optimization
history and replaces it with a memoryless geometric estimate.

This is standard SfM retriangulation (COLMAP does it between BA rounds)
moved *inside* the solver loop. Do NOT claim the pass itself as novel; the
novel part is the measured result that it substitutes for damping tuning
(§4) and the failure analysis (§5).

## 2. The math (per point p, observations i = 1..m, need m >= 2)

1. Unproject each measured pixel to a normalized ray. Approximate
   undistortion, one fixed-point step is enough:
   `x_n = u/f;  y_n = v/f;  s = 1 + k1*r^2 + k2*r^4;  x_n /= s;  y_n /= s`
   (guard s > 1e-12). BAL convention projects `p = -X/Z`, so the camera-frame
   direction is `d_cam = (-x_n, -y_n, 1)`; rotate to world `d_i = R^T d_cam`,
   normalize (skip the ray if its norm <= 1e-12). Camera center
   `c_i = -R^T t`.
2. Midpoint / DLT normal equations — the point nearest all rays:
   `[ sum_i (I - d_i d_i^T) ] X = sum_i (I - d_i d_i^T) c_i`
   One 3x3 SPD solve per point (Cholesky). Bail out if any pivot <= 1e-12
   (near-parallel rays) or the solution is non-finite.
3. PER-POINT ACCEPTANCE GATE: evaluate that point's summed reprojection cost
   at the old and the new position over ITS OWN observations only; commit the
   reset only if `cost_new < cost_old`. While projecting, skip/reject on
   |Z| <= 1e-12 at any camera (reject the reset if the NEW position hits it).
4. GLOBAL GUARD (belt-and-braces; per-point gating already implies it, but
   guard anyway): recompute the full objective after the pass; keep the pass
   only if the objective did not rise. Mark the assembly/Jacobian STALE — the
   state moved.

## 3. Scheduling and cost

- Fire every k ACCEPTED outer iterations, and once at the end. k = 5 is the
  validated setting.
- Cost: one O(nobs) kernel + one full cost evaluation per firing; ~1% of
  wall. Embarrassingly parallel — one thread per point; the only shared
  write is an atomic counter of accepted resets (worth logging).

## 4. Measured behaviour — where it is strong

- Run ALONE (no damping tuning at all) on 7 BAL scenes it matched or beat a
  four-flag tuned damping stack on 6, at 3-4x less wall on three:
  venice-52 -7.2% vs plain / -5.2% vs the tuned stack; dubrovnik-135 -5.2% /
  -1.4%; ladybug-1197 -2.5% / +0.1%. One parameter, nothing per-scene.
- It composes with damping schedules on most scenes (it is part of this
  repo's Config R and Config S).
- Why it works: the damping machinery PREVENTS fragile points from being
  flung out; this REPAIRS the ones that already were. Thin-track points
  displaced along near-null directions are exactly what a closed-form
  re-triangulation snaps back.

## 5. Measured behaviour — the failure mode you must respect

- On storm-class scenes it is destructive DESPITE the per-point gate.
  final-4585 (9.1M obs): the first firing reset 461,707 of 1,324,582 points
  (35% of the cloud) for a -36.8% one-shot cost drop — that is
  RE-INITIALIZATION, not repair. It discards a point configuration
  co-adapted with the camera trajectory; the run ends +4.5% WORSE even
  though every firing locally improved. (Also: repair+damping stacked was
  worse than damping alone there — do not stack blindly.)
- A drop-size refusal threshold does NOT separate the cases cleanly: a 13.9%
  one-shot drop was BENEFICIAL on final-3068 while 36.8% was harmful on
  final-4585 (factor 2.6 apart, not orders of magnitude). We built and then
  withdrew such a gate (`OCA_RETRI_MAXDROP` remains as a diagnostic only).
- Diagnostic signature of the bad case: a firing that resets a LARGE cloud
  fraction with a LARGE one-shot drop EARLY — inside the first ~8 outers,
  which is the measured basin-commitment window. Late firings touching 1-2
  points are always safe (the cloud is at its triangulation fixed point).
- Practical guidance: log (outer index, points reset, cost drop) per firing.
  If the first firing resets >10% of the cloud, treat the run as
  re-initialized and expect basin-quality consequences; on such scenes
  prefer damping-only configurations.

## 6. Gotchas from our implementation history

- The reset is a deterministic function of the cameras: two runs that fire
  identically become ~1e5x more run-to-run reproducible — useful tell that
  the pass dominates the trajectory.
- Evaluate the A/B fairly: arms must not stop at different outer counts
  (a stopping-rule confound inflated this pass's measured harm 3x, +15.1%
  reported vs +4.5% real), and remember an extra cudaMalloc alone can move
  endpoints on basin-sensitive scenes — allocate in BOTH arms.
- Intrinsics: use the CURRENT f, k1(, k2) per camera in both unprojection
  and the gate's projections, not the initial ones.
