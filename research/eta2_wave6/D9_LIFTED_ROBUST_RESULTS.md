# D9 lifted robust opening: result

## Verdict

**Rejected as a production change.**  Jointly optimizing persistent confidence
weights strengthens the Final3068 opening signal, but it systematically commits
Venice52 to a worse plain-L2 basin.  It therefore does not solve the transfer
problem that prevented the earlier scheduled Cauchy opening from promotion.

The frozen Eta2 champion and the B6v7 optimized systems candidate remain
unchanged.

## What was tested

The active arm used Zach's smooth lifted residual for exactly three accepted
opening steps,

```
Phi(r,w) = 1/2 [w^2 ||r||^2 + (a2/2)(w^2-1)^2],
a2 = 4 median_initial(||r||^2),  w_initial = 1,
```

then handed the state and controller variables to ordinary L2 Eta2.  Unlike
IRLS, each observation's weight persisted as a state variable.  Its increment
was eliminated jointly with the camera/point step, and an accept committed the
matching candidate weights while a reject rolled them back.  Assembly,
candidate scoring, and the strict-rho full-step model used the same eliminated
metric.  Lambda-changing retries rebuilt it.  All reported curves, targets,
and independent endpoint audits used the original full L2 objective.

The first active preflight exposed an overly strict startup check: the CLI
passes a latent `use_alpha=true`, although the frozen strict-rho path disables
alpha search unless `OCA_ALPHA_RHO` is present.  It exited before solving.  The
versioned amendment changed only that guard; all valid evidence has the
`d9v2-*` prefix.

## Correctness evidence

- 5,000 random residual/Jacobian blocks agreed with explicit dense elimination
  to `5.31e-16` in the normal matrix and `5.69e-16` in the RHS.  The maximum
  scalar weight-normal-equation residual was `2.84e-14`.
- Flag-off compatibility on Ladybug539 was `-4.55e-15` in median endpoint L2
  relative to B6v7 (N=3 per binary).
- The active smoke committed exactly three lifted accepts, rebuilt twice after
  lambda changes, then entered L2.  Independent FP64 endpoint scoring agreed
  with the native score to `3.53e-16` relative.
- Every scored tail run completed the handoff.  The opening state and weight
  summary were repeatable across all five repetitions of each scene.

## Registered tail screen

| Scene | Arm | Hits | Median target time | Median endpoint L2 | Median outers | Median rejects | Median products |
|---|---:|---:|---:|---:|---:|---:|---:|
| Final3068 | control | 3/5 | 4.7146 s | 1,743,683.97 | 97 | 15 | 389 |
| Final3068 | lifted-3 | 4/5 | 1.9869 s | 1,743,935.79 | 30 | 4 | 291 |
| Venice52 | control | 0/5 | -- | 246,326.12 | 109 | 2 | 395 |
| Venice52 | lifted-3 | 0/5 | -- | 260,533.32 | 132 | 3 | 459 |

The Final target-time ranges overlap (`2.9158--6.0302` control versus
`1.7098--7.6234` lifted), and the hit gain is only one, below the registered
two-hit screen.  The apparent 0.421x median time ratio is therefore a useful
screening signal, not a speed claim.  Venice supplies the decisive failure:
both arms miss, while lifted-3 is **+5.768%** worse in median endpoint and uses
16.2% more Schur products.

At handoff, Final3068 had 68,215 of 1,653,812 observations (4.13%) below
`|w|=0.5`; Venice had 22,558 of 347,173 (6.50%).  Median weights were 0.989 and
0.971 respectively.  The lifted opening therefore made a sparse but material
selection in both scenes.  It did not merely approximate the L2 opening.

## Mechanism learned

The result separates two questions.  Robust influence control can reduce the
Final3068 reject/plateau pathology, and explicit joint weights preserve that
effect with only three accepted opening steps.  But the same locally coherent
objective change steers Venice into a different, worse L2 basin.  This repeats
the broader campaign law seen with projection homotopy, object-space opening,
and geodesic correction: better behavior under an intermediate model does not
predict a better final basin under the scored model.

No fixed schedule or adaptive exit can repair this particular failure, because
the harmful decision has already been made by the three-step handoff and is
identical across repetitions.  A scene-dependent gate would be post-hoc and is
not pursued.  The practical panel and N=10 confirmation were not earned.

## Evidence

- `D9_LIFTED_ROBUST_PROTOCOL.md`
- `D9_IMPLEMENTATION_AMENDMENT.md`
- `d9-lifted-build-manifest.json`
- `d9v2-lifted-registration.json`
- `d9v2-lifted-compatibility-summary.json`
- `d9v2-lifted-diagnostic-summary.json`
- `d9v2-lifted-tails-results.json`
- `d9v2-lifted-tails-summary.json`

