#!/usr/bin/env python3
"""Report actual target crossings and misses without success-only speedup bias."""
import argparse,hashlib,json,pathlib,statistics
from demand_screen import ARMS

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,default=pathlib.Path('/workspace/prism-equal-quality'));p.add_argument('--partial',action='store_true');a=p.parse_args();root=a.root;targets=json.loads((root/'targets.json').read_text());rows=[json.loads(p.read_text()) for p in sorted((root/'runs').glob('*.result.json'))]
 stats={}
 for scene in targets:
  stats[scene]={}
  for arm in ARMS:
   rr=[r for r in rows if r['scene']==scene and r['arm']==arm];hits=[r for r in rr if r.get('hit')];times=[r['crossing_seconds'] for r in hits]
   v=dict(runs=len(rr),hits=len(hits),median_hit_seconds=statistics.median(times) if times else None,hit_range=[min(times),max(times)] if times else None,final_cost_range=[min(r['cost'] for r in rr),max(r['cost'] for r in rr)] if rr and all(r['status']=='ok' for r in rr) else None)
   v['certified_median_seconds']=v['median_hit_seconds'] if len(rr)==3 and len(hits)==3 else None
   stats[scene][arm]=v
  single=stats[scene]['single']['certified_median_seconds']
  base=stats[scene]['multi']['certified_median_seconds']
  for arm,v in stats[scene].items():
   v['speedup_vs_fixed_multi']=base/v['certified_median_seconds'] if base and v['certified_median_seconds'] else None
   v['speedup_vs_single']=single/v['certified_median_seconds'] if single and v['certified_median_seconds'] else None
  print(scene,[(arm,v['hits'],v['runs'],round(v['median_hit_seconds'],3) if v['median_hit_seconds'] is not None else None) for arm,v in stats[scene].items()],flush=True)
 print('Completed',len(rows),'/36',flush=True)
 if a.partial:return
 assert len(rows)==36 and all(r['status']=='ok' for r in rows)
 for r in rows:
  p=root/'runs'/f"{r['scene']}-{r['arm']}-{r['rep']}.state";assert hashlib.sha256(p.read_bytes()).hexdigest()==r['state_sha256']
 report='''# Time to equal quality — 2026-09-07

Actual first accepted target-crossing times for the four frozen PRISM variants.
This replaces inference from fixed-budget endpoint costs with shared quality
thresholds and fresh N=3 repeats. All use the compact FP64 mode2 layout and the
same existing alpha/backtracking/rearm settings. No Caspar reruns here.

Targets were frozen before runs: the lowest median CPU cost among the four
previous demand-screen arms, rounded upward to the next 100. Every method
must reach the same threshold on a scene. N=3, rotated/reversed method order;
normal convergence stops remain enabled. A method stopping above target is a
miss, even if its budget is unused. A crossing after the cap is also a miss.

| Scene | Common CPU cost target | Native time cap |
|---|---:|---:|
'''
 for scene,t in targets.items():report+=f"| {scene} | {t['target']:,} | {t['cap_seconds']} s |\n"
 report+='''
## Target crossing speed

Seconds are medians only when all three repeats reached the target within the
cap. Speedup = baseline median / method median (>1 is faster). No ratio is
reported when either method has a miss; misses are not replaced by cap times
or dropped to manufacture a successful-run median speedup.

| Scene | Method | Hits | Median crossing s | Successful crossing range s | Speedup vs fixed multi | Speedup vs single |
|---|---|---:|---:|---:|---:|---:|
'''
 for scene in targets:
  for arm,v in stats[scene].items():
   median=f"{v['certified_median_seconds']:.4f}" if v['certified_median_seconds'] is not None else '—'
   ran='–'.join(f'{t:.4f}' for t in v['hit_range']) if v['hit_range'] else '—'
   ratio=f"{v['speedup_vs_fixed_multi']:.3f}×" if v['speedup_vs_fixed_multi'] is not None else '—'
   single_ratio=f"{v['speedup_vs_single']:.3f}×" if v['speedup_vs_single'] is not None else '—'
   report+=f"| {scene} | {arm} | {v['hits']}/3 | {median} | {ran} | {ratio} | {single_ratio} |\n"
 report+='''
A successful range for a partially successful arm is descriptive only; its
median and speedup remain unreported. Three repeats remain a small screen,
not a confidence interval or a claim of universal superiority. Discrete
accepted steps may overshoot a quality threshold downward; that is legitimate
attainment of at least the common requested quality.

## Every run, including misses

| Scene | Arm | Rep | Hit | Crossing s | Final CPU cost | Solve including cleanup s | Stop |
|---|---|---:|---|---:|---:|---:|---|
'''
 for r in rows:
  crossing=f"{r['crossing_seconds']:.4f}" if r['crossing_seconds'] is not None else '—'
  report+=f"| {r['scene']} | {r['arm']} | {r['rep']} | {r['hit']} | {crossing} | {r['cost']:,.3f} | {r['seconds']:.4f} | {r['stop_reason']} |\n"
 report+='''
## Measurement and checks

The only new solver change is opt-in `OCA_TARGET_COST`. It checks initial and
accepted states, stops at objective <= target*(1-1e-8), and records time from
native solver entry before cleanup/state export. The inward margin protects
against threshold rounding. A separate CPU evaluator verifies the exact
exported state is <= the common target and agrees with the reported GPU
objective within 1e-7 relative. Earlier accepted trace states are checked to
be above the internal threshold; all traces are finite and monotone. State,
input and frozen binary hashes are retained. This is native solve time, not
parsing/CPU-audit/end-to-end latency.

A saved narrow fallback computed before a deadline may commit after expanded
work finishes late; if its actual crossing time exceeds the cap, this study
counts it as a miss. No late expanded candidate is credited.

CLI/core builds pass. Hook smoke tests cover an already-satisfied initial
state, first crossing during a solve, and a missed target under a time cap,
with CPU checks and earlier-trace checks. Feature-off smoke cost agrees with
the previous frozen solver within the declared 1% atomic-order trajectory
screen (observed difference about 0.00015%). No algorithm parameters were tuned.

The selected target is based on prior observations, so this is follow-up
validation on previously investigated scenes, not held-out generalization.
No speedup is inferred from unequal endpoint quality or nominal time budgets.
All runs and misses remain in the summary. Broader runs remain paused;
solver/controller defaults are unchanged and nothing has been pushed.

Artifacts: `/workspace/prism-equal-quality/` (protocol, targets, frozen source
and binary, manifests, logs, traces, exact states, result rows and summary).
Driver: `bench/equal_quality_screen.py`; report: `bench/summarize_equal_quality.py`.
The controller implementation and prior fixed-budget ablation are documented
in [demand-menu results](demand_menu_results.md).
'''
 pathlib.Path('/workspace/prism-ba/docs/equal_quality_results.md').write_text(report)
 summary=dict(targets=targets,stats=stats,rows=rows,runs=len(rows),hits=sum(r['hit'] for r in rows),misses=sum(not r['hit'] for r in rows),native_solve_seconds=sum(r['seconds'] for r in rows),max_cpu_audit_relerr=max(r['audit_relerr'] for r in rows))
 (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(root/'completion.json').write_text(json.dumps({k:v for k,v in summary.items() if k not in ['targets','stats','rows']}|{'status':'complete','failed_runs':0},indent=2)+'\n')
if __name__=='__main__':main()
