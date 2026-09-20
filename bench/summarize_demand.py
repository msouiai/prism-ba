#!/usr/bin/env python3
"""Report all frozen demand-menu ablations and diagnostic activation checks."""
import pathlib,json,statistics,hashlib
from demand_screen import SCENES,ARMS
root=pathlib.Path('/workspace/prism-demand')
rows=[json.loads(p.read_text()) for p in (root/'screen').glob('*.result.json')]
assert len(rows)==24 and all(r['status']=='ok' for r in rows)
med={};ranges={}
for scene in SCENES:
 med[scene]={};ranges[scene]={}
 for arm in ARMS:
  rr=[r for r in rows if r['scene']==scene and r['arm']==arm];assert len(rr)==2
  med[scene][arm]={k:statistics.median(r[k] for r in rr) for k in ['cost','seconds','iters','rejects','matvecs','scored','expansions','narrow_accepts','fallback_wins','joint_rebuilds']}
  ranges[scene][arm]={k:[min(r[k] for r in rr),max(r[k] for r in rr)] for k in ['cost','seconds']}
  for r in rr:
   p=root/'screen'/f"{scene}-{arm}-{r['rep']}.state"
   assert hashlib.sha256(p.read_bytes()).hexdigest()==r['state_sha256']
report='''# Demand-driven multi-shift prototype — 2026-09-07

Implemented opt-in scheduling and paired damping. The short screen shows
improvements on Ladybug and Venice, but repeated unproductive expansion makes
Dubrovnik worse. This is a tested prototype, not a replacement default.

## Implementation

`OCA_DEMAND_MENU=1` runs a real single-shift CG attempt first, rather than
carrying five shifts and only pruning their scores. If the best safeguarded
step fails to improve or its relative gain is below
`max(10*ftol, 0.25*previous_accepted_relative_gain)`, expand to five shifts.
The same state, assembly, point factors, and Schur RHS are reused. CG restarts
at the new least-damped seed; the prior Krylov basis is not recycled. Expansion
is search work, not a rejected optimization step, and is separately counted.
An improving narrow step is retained as a fallback and beats any worse wide
proposal. Wide expansion explicitly scores all shifts, bypassing the old model
flatness gate. Full-menu, unrescued convergence confirmation is preserved.

`OCA_DEMAND_MENU=2` adds a successful damping-pair anchor. Useful unrescued
accepts (>1e-4 relative improvement) relax both the winning camera lambda and
used point tau by 0.5, with lower bounds. Small gains/rescues retain the pair;
rescues anchor camera lambda at the attempt center because full-step shrinkage
is not evidence for larger camera damping. Failed expanded menus escalate both
by 10, bounded at 1e8. Tau changes explicitly invalidate the point-factor/RHS
cache; shifted recurrences are never reused across different tau. This is
history-based warm-starting with bounded relaxation, not indefinite exact
retention of cold-start damping. The existing alpha grid and Armijo guard stay.

Mode 0/unset is unchanged. The prototype requires five allocated slots, FP64,
unshared pinhole dof9, diagonal equilibration and full scoring; competing menu
policies and unsupported combinations are rejected. It reserves one extra full
step buffer for the fallback and frees all five shift slots even when the last
attempt used only one. The compact FP64 layout remains enabled in this study.

Budget handling: late expanded candidates are discarded. A saved proposal
fully evaluated before the earlier deadline check remains eligible and may
commit after expansion overruns. This changes fallback handling relative to
the earlier guard; it does not credit late candidate computation. Runtime can
overshoot, so this is not a hard return-time guarantee.

## Frozen screen

24 successful timed runs, N=2 per cell, rotated/reversed method order, no
retuning after results. Budgets: 3s Ladybug1197, 3s Venice52, 8s Dubrovnik356.
Same fresh binary and existing policy flags across arms, including compact
mode2, backtracking and rearm; single changes width to one. CPU-audited raw-z
FP64 endpoints, finite monotone traces, hash-verified exact exported states.
The source and binaries are frozen under `/workspace/prism-demand/`.

| Scene | Budget | Guarded single cost | Fixed multi cost | Demand scheduling cost | Full paired-controller cost |
|---|---:|---:|---:|---:|---:|
'''
for scene,budget in SCENES.items():report+='| '+scene+f' | {budget}s | '+' | '.join(f"{med[scene][a]['cost']:,.3f}" for a in ARMS)+' |\n'
report+='\nMedian CPU costs, lower is better. Two repeats are a screen, not formal statistical evidence.\n\n| Scene | Full vs fixed multi cost | Full vs single cost | Scheduling vs fixed multi cost |\n|---|---:|---:|---:|\n'
for scene in SCENES:
 m=med[scene];report+=f"| {scene} | {100*(m['pair']['cost']/m['multi']['cost']-1):+.3f}% | {100*(m['pair']['cost']/m['single']['cost']-1):+.3f}% | {100*(m['demand']['cost']/m['multi']['cost']-1):+.3f}% |\n"
report+='\n| Scene | Arm | Median solve s | Median rejects | Median matvecs | Median scored | Expansions | Narrow accepts | Fallback wins | Joint rebuilds |\n|---|---|---:|---:|---:|---:|---:|---:|---:|---:|\n'
for scene in SCENES:
 for arm in ARMS:
  m=med[scene][arm];report+=f"| {scene} | {arm} | {m['seconds']:.3f} | "+' | '.join(f"{m[k]:g}" for k in ['rejects','matvecs','scored','expansions','narrow_accepts','fallback_wins','joint_rebuilds'])+' |\n'
report+='''
On Ladybug, scheduling alone removes fixed-multi retries and uses fewer scored
candidates; the full pair is not necessary to explain that improvement.
On Venice, scheduling alone loses quality while full pair improves it, so
saving menu work alone does not explain the benefit. Pair mode bundles camera
history/decay and point history/decay; this screen does not isolate them.

On Dubrovnik, full pair makes about 61 expansions and 26 fallback wins per run,
scoring 1504 candidates versus 743 for fixed multi, with 4.18% higher median
cost. The issue is repeated searches yielding too little benefit for their
work, not merely a small single-digit quality regression. The trigger does not
yet learn that narrow probes or wide expansion are repeatedly unproductive.
A next design target is remembering expansion utility over recent iterations;
this has not been implemented or tested here. The previous adaptive-menu
utility policy is prior local work and must be considered before claiming
novelty. No blanket success or new publication claim follows from this screen.

All timed full-controller runs had zero joint-retry activations. Therefore
their improvements cannot be attributed to coordinated rejection recovery.
That branch was exercised separately on a known rejection-prone saved state.

## Validation and diagnostics

`bench/test_demand_menu.cc` tests trigger thresholds, retained/relaxed pair,
escalation, floors, and upper bounds. CLI and core build. Feature-off endpoint
on an eight-outer Ladybug49 smoke run differs from the previous frozen binary
by about 0.068%, within the declared 1% trajectory screen; atomic sums already
make trajectories nondeterministic. This is not bitwise equivalence proof.
Compute Sanitizer reports zero errors for both new modes on real Ladybug49
solves. Their early eight-outer costs are worse than fixed multi; these smoke
runs validate memory and CPU objective consistency, not performance.

A separate low-initial-damping original-scene probe did not exercise joint
retry. The targeted saved state `/workspace/prism-rejection/forks/state_it40.txt`
then exercised three joint retries: lambda/tau each rose through 1e-6, 1e-5,
1e-4. It accepted two outer steps, ending at CPU cost 366867.573890. Its log
shows five factor builds (two assemblies plus three tau-changing retries) and
two factor reuses (same-tau menu expansions). CPU/GPU relative error 3.61e-12.
This verifies branch behavior on a known case, not a general performance win.

Fallback selection fired in the timed screen. Three separate tiny-budget CPU
checks passed but did not hit the saved-predeadline-fallback branch; neither
did the timed screen. That particular deadline branch was code-reviewed but
not dynamically exercised. These diagnostics are separate from timed results.

N2 endpoint ranges and runtime ranges are retained in `summary.json`, together
with each original row. No Caspar reruns were included in this solver ablation.
No defaults changed, broad runs remain paused, and nothing has been pushed.
Implementation: `gpu/demand_menu.h`, `gpu/oca_cuda.cu`.
Runner/report: `bench/demand_screen.py`, `bench/summarize_demand.py`.
'''
pathlib.Path('/workspace/prism-ba/docs/demand_menu_results.md').write_text(report)
summary=dict(medians=med,ranges=ranges,rows=rows,runs=len(rows),native_solve_seconds=sum(r['seconds'] for r in rows),max_audit_relerr=max(r['audit_relerr'] for r in rows))
(root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
(root/'completion.json').write_text(json.dumps({'status':'complete','runs':len(rows),'failures':0,'native_solve_seconds':summary['native_solve_seconds'],'defaults_changed':False,'broad_queue':'paused'},indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ['medians','ranges','rows']},indent=2))
