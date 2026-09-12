# D10 result: the E4 track-damage separator does not generalise

## Verdict

The preregistered diagnostic gate failed, so no active filter was run.  The
two-threshold damage signal separates the one archived E4 hit/miss proposal
that motivated it, but it fires in every fresh Final3068 trajectory regardless
of endpoint.  Among the first ten accepted states, eventual hits and misses
contain exactly 20 concentrated-damage events each, and their event magnitudes
are nearly indistinguishable.  Rejecting those events would alter all ten
trajectories rather than selectively remove the losing branch.

This closes the measured *per-track damage filter*.  It does not refute filter
methods in general.  A classical objective/constraint filter still lacks a
second state function for unconstrained plain-L2 BA; reusing rho, cost history,
or immediate descent would duplicate the already-negative threshold,
nonmonotone, and soft-acceptance experiments.

## Registered measure

For every full-L2-decreasing joint candidate, before the existing rho gate,
the diagnostic computes whole-track costs at the old and proposed states:

```
delta_j = max(0, F_j(x+d) - F_j(x))
H       = sum_j delta_j
D       = max_j delta_j
q       = D/H
b       = D/(F(x)-F(x+d)).
```

A candidate is labelled concentrated-damage when both `q > 0.05` and
`b > 0.05`.  The thresholds were frozen from the archived E4 values before the
new cohort:

| Archived proposal | D/H | D/global gain | Label |
|---|---:|---:|---|
| Eventual hit | 0.0178 | 0.00891 | clear |
| Eventual miss | 0.1127 | 0.0660 | concentrated |

Both archived steps lower the global cost, and both lower the largest existing
track cost.  The signal is therefore specifically a newly damaged,
previously-well-fit track, not maximum track cost or a conventional feasibility
measure.

## Fresh diagnostic cohort

The untouched deterministic optimized Eta2 path ran on ten new Final3068
perturbations (`PCG64` seeds 660000--660009, field scale `1e-10`), three
unperturbed Venice52 runs, and three unperturbed Ladybug539 runs.  Endpoint
costs were independently rescored in FP64.  The instrumentation logs but never
changes a candidate, acceptance decision, controller value, or stop.

| Scene / endpoint class | Runs | Eligible early proposals | Concentrated events | Runs with event |
|---|---:|---:|---:|---:|
| Final3068 hits | 5 | 54 | 20 | 5/5 |
| Final3068 misses | 5 | 54 | 20 | 5/5 |
| Venice52 misses | 3 | 33 | 6 | 3/3 |
| Ladybug539 hits | 3 | 18 | 0 | 0/3 |

For Final3068, median event concentration was `0.69005` in hits and `0.68991`
in misses.  Median burden was `0.12946` in hits and `0.11582` in misses, so the
burden direction is slightly opposite the hypothesis.  Every Final run first
fires at accepted-state index 2.  The motivating point 250233 is the maximiser
in one hit event and three miss events, but most events are instead points
5316, 277864, and 277865.  Selecting a point identity would be a post-hoc,
scene-specific rule and is not permitted.

The healthy Ladybug locality condition passes, but the required endpoint
discrimination does not: event-run rates are 100% for both Final classes.  The
protocol therefore stops before the twenty-pair active screen and forbids a
threshold sweep.

## Correctness and cost

The derived-off binary produced byte-identical endpoint states and identical
cost traces to the deterministic parent in two compatibility pairs.  One warp
owns each point and sums its observations in fixed order.  The host audit
checks `q` and `b` from logged `D`, `H`, and global gain on every row.

The diagnostic implementation copies one `double2` per point to the host and
scans it, so it is deliberately an evidence path rather than a production
kernel.  Median diagnostic time was 0.936 s on Final3068, 0.321 s on Venice52,
and 0.0186 s on Ladybug539, roughly 10--13% of native wall.  A GPU reduction
would be required after a positive mechanism gate; the negative gate gives no
reason to build it.

## Evidence

- `D10_TRACK_DAMAGE_FILTER_PROTOCOL.md`
- `analyze_d10_witness.py`, `d10-witness-prescreen.json`
- `track_damage_filter.cuh`, `build_track_damage.py`, `run_d10.py`
- `d10-build-manifest.json`, `d10-registration.json`
- `d10-compatibility.json`
- `d10-diagnostic-results.json`, `d10-diagnostic-summary.json`
