# B6v6: deterministic camera-major reduced RHS

## Verdict

The camera-owned reduction is a clear throughput improvement and a mixed
nonlinear result.  It is **8.23% faster** than dots-only on the nine-cell panel
and **3.93% faster** on Muell, with identical products, outers and rejects in
every stable cell.  It also improves the B6v4 atomic pruning arm by 2.09% and
2.07%, respectively.  The always-on arm is nevertheless **not promoted**:
Venice52 remains 0/10 and its median endpoint is 0.253% higher than dots-only,
exceeding the preregistered 0.15% quality boundary.

Final3068 moves in the favourable direction in this N=10 screen, from 3/10 to
6/10 target hits, with a conditional median crossing of 2.614 s versus 4.152 s.
That cohort is too small and the control draw is too low relative to prior
cohorts to establish a reliability gain.  It is retained as motivation for a
separately registered camera-count dispatch, not counted as a win.

## Construction and compatibility

The active kernel reads the existing camera-major compact fragments.  One
256-thread block owns each camera, accumulates its nine components of
`W V_tau^-1 b_p` in FP64, performs a fixed binary-tree reduction and writes the
camera RHS once.  It receives a null diagonal pointer, so it avoids both the
discarded Schur-diagonal solves and the observation-major global atomics.

The derived flag-off/dots path matches the frozen champion to `5.0e-14`
relative at the compatibility gate.  The runtime guard requires the frozen
single-shift, unshared-intrinsics, classical-LM path and camera-major compact
fragment mode.

## Practical panel

All 81 rows reach their targets.  The camera arm is faster than dots-only with
disjoint ranges in all nine cells; it is faster than atomic pruning in five
cells and overlaps in four.  Median work counts are identical throughout.

| Comparison | Geometric-mean target-time ratio | Disjoint faster / overlap / slower |
|---|---:|---:|
| dots-atomic / dots | 0.9373 | 9 / 0 / 0 |
| dots-camera / dots | **0.9177** | 9 / 0 / 0 |
| dots-camera / dots-atomic | **0.9791** | 5 / 4 / 0 |

Endpoint movements remain far below 0.15% on all nine stable cells.

## Muell and profile

Every Muell arm reaches the fixed target in 3/3 runs with 980 products, 16
outers and no rejects:

| Arm | Median target time [range] | Relative to dots |
|---|---:|---:|
| dots | 4.2004 [4.1982, 4.2043] s | 1.0000 |
| dots-atomic | 4.1207 [4.1196, 4.1220] s | 0.9810 |
| dots-camera | 4.0354 [4.0306, 4.0423] s | **0.9607** |

The independent profile explains the gain.  On Muell, median point-factor plus
RHS time is 0.241 s for dots, 0.160 s for atomic pruning and **0.074 s** for the
camera reduction.  Assembly is 0.730--0.737 s, Krylov 3.036--3.037 s and
candidate time 0.044 s, so the saving is isolated to the intended phase.  On
Trafalgar138 the same bucket falls 0.013 to 0.007 s.

## Tail screen

| Scene | Dots | Dots-atomic | Dots-camera | Camera endpoint delta vs dots |
|---|---:|---:|---:|---:|
| Final3068 hits, N=10 | 3/10 | 4/10 | 6/10 | -2.85% |
| Final3068 conditional crossing | 4.152 s | 3.578 s | 2.614 s | — |
| Venice52 hits, N=10 | 0/10 | 0/10 | 0/10 | +0.253% |

The camera arm also uses fewer median products and rejects in both tail draws,
but those quantities follow from its changed trajectory and are not a pure
kernel-speed attribution.  Camera ownership fixes this RHS reduction's order;
it does not make the entire solver deterministic because assembly and other
observation reductions still use atomics.

## Decision

Always-on B6v6 fails the strict Venice quality gate.  The implementation result
is still useful: it proves that the discarded diagonal and contended RHS
atomics can be replaced by a substantially cheaper fixed camera reduction.
The next test is a camera-count dispatch fixed before new scoring.  Small
problems retain the frozen reduction; sufficiently large problems use B6v6,
which is the normal systems use of this kernel and avoids low-block-count
underfill.

Compact evidence: `B6V6_PROTOCOL.md`, `b6v6-registration.json`,
`b6v6-panel-summary.json`, `b6v6-muell-summary.json`,
`b6v6-profile-summary.json`, and `b6v6-tails-summary.json`.
