#!/usr/bin/env python3
"""Report retained novelty-study measurements; no partial-cell verdicts."""
import argparse,collections,json,math,pathlib,re,statistics

def load(root):
 rows=[]
 for mp in sorted(root.glob('*/preregistered.json')):
  folder=mp.parent
  for p in sorted(folder.glob('*.json')):
   try:r=json.loads(p.read_text())
   except json.JSONDecodeError:continue # Writer may still be finishing a newly completed run.
   if not isinstance(r,dict) or not {'scene','arm','rep'}<=r.keys():continue
   r['experiment']=folder.name;r['record_path']=str(p)
   if r.get('status','ok')=='ok' and r['arm'] in ['A-single','B-single-guarded','C-multi','D-multi-guarded']:
    diagnostics=re.search(r'median_reproj_err_px (\S+) -> (\S+) \| cheirality_violations\(obs\) (\d+) -> (\d+)',p.with_suffix('.log').read_text())
    if diagnostics:r['median_reproj_px']=float(diagnostics[2]);r['cheirality_violations_obs']=int(diagnostics[4])

   if r.get('status','ok')=='ok' and r['arm'].startswith('ceres-'):
    log=p.with_suffix('.log').read_text()
    r['trace']=[dict(iter=int(i),cost=float(c),wall_s=float(t)) for i,c,t,accepted in re.findall(r'TRACE iter=(\d+) cost=(\S+) seconds=(\S+) accepted=(\d+)',log) if int(i)==0 or int(accepted)]
   rows.append(r)
 return rows

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args();rows=load(a.root)
 status_path=a.root/'study-status.json';complete=status_path.exists() and json.loads(status_path.read_text()).get('local_nonlinear_complete',False)
 lines=['# Prism novelty study: retained measurements','',
 'Local nonlinear protocol complete; retained failures are not successes. Second-GPU replication remains pending.' if complete else 'LOCAL STUDY IN PROGRESS: comparisons are preliminary.',
 'Three repeats are required for a cell-level comparison. Incomplete experiments remain visible; this file is a progress report until all declared cells finish.',
 'All costs use the original double-observation SIMPLE_RADIAL objective. Prism reports GPU-fp64 costs with an independent initial-cost check; its endpoints are not separately CPU-audited. Caspar-fp32 and Ceres endpoints are CPU-fp64 evaluations of returned states. Caspar native float traces do not certify crossings.',
 'Ceres is CPU (8 threads); Prism and Caspar use the GPU. Do not interpret Ceres timings as an equal-GPU kernel comparison. GPU/CPU runs share the benchmark lock.',
 'Development, evaluation and perturbed instances are separate experiments. Different perturbation seeds are different instances, not extra timing repeats.','',
 '| Experiment | Scene | Arm | Completed / failed / planned | Cost median [range] | Solver seconds median [range] | Rejects / matvecs / scored medians |',
 '|---|---|---|---|---:|---:|---|']
 def interval(rr,key):
  x=[r[key] for r in rr];return f'{statistics.median(x):,.6g} [{min(x):,.6g}, {max(x):,.6g}]' if x else '—'
 groups=collections.defaultdict(list)
 for r in rows:groups[r['experiment'],r['scene'],r['arm']].append(r)
 for mp in sorted(a.root.glob('*/preregistered.json')):
  m=json.loads(mp.read_text());experiment=mp.parent.name
  if 'arms' in m:arms=list(m['arms'])
  elif 'kind' in m:arms=[f"{m['kind']}-{pr}-{b}" for pr in m['profiles'] for b in m['budgets']]
  else:continue
  for scene in m['scenes']:
   for arm in arms:
    rr=groups[experiment,scene,arm];ok=[r for r in rr if r.get('status','ok')=='ok'];bad=len(rr)-len(ok)
    work=' / '.join(f"{statistics.median(r[k] for r in ok):g}" if ok and all(k in r for r in ok) else '—' for k in ['rejects','matvecs','total_scored'])
    lines.append(f"| {experiment} | {scene} | {arm} | {len(ok)} / {bad} / {m['reps']} | {interval(ok,'cost')} | {interval(ok,'seconds')} | {work} |")
 lines+=['','## Does multi-shift help beyond the same safeguard?','',
 'D versus B: negative cost/time changes favor five shifts with safeguard. A resolved cost difference needs three successful repeats per arm, a median gap >0.15%, and disjoint observed ranges. Ranges are not tail bounds.',
 '', '| Experiment | Scene | D/B cost change | D/B wall change | Cost evidence |','|---|---|---:|---:|---|']
 for experiment,scene,arm in sorted(groups):
  if arm!='D-multi-guarded':continue
  dd=[r for r in groups[experiment,scene,arm] if r.get('status','ok')=='ok'];bb=[r for r in groups[experiment,scene,'B-single-guarded'] if r.get('status','ok')=='ok']
  if min(len(dd),len(bb))<3:lines.append(f'| {experiment} | {scene} | — | — | incomplete |');continue
  dc=100*(statistics.median(r['cost'] for r in dd)/statistics.median(r['cost'] for r in bb)-1);dt=100*(statistics.median(r['seconds'] for r in dd)/statistics.median(r['seconds'] for r in bb)-1)
  disjoint=max(r['cost'] for r in dd)<min(r['cost'] for r in bb) or max(r['cost'] for r in bb)<min(r['cost'] for r in dd)
  lines.append(f"| {experiment} | {scene} | {dc:+.4f}% | {dt:+.2f}% | {'resolved' if abs(dc)>.15 and disjoint else 'not resolved'} |")
 lines+=['','## Fixed quality targets','',
 'For each input instance, Fbest is the lowest reported fp64 endpoint among the frozen measured arms. It is an empirical reference, not an optimum. Targets are Fbest*(1+epsilon), epsilon=1%,0.1%,0.01%.',
 'Prism/Ceres crossings charge all untraced solver time before the accepted-state crossing. For Caspar-fp32, only its checked endpoint certifies attainment; the bound is full solver runtime, not a claimed first crossing. Setup-inclusive bounds are additional columns. Missing means no certified attainment in that run.',
 'The machine-readable crossing table retains every repeat: `novelty-crossings.json`.','']
 best={}
 for r in rows:
  if r.get('status','ok')=='ok':best[r['scene']]=min(best.get(r['scene'],math.inf),r['cost'])
 crosses=[]
 for r in rows:
  if r.get('status','ok')!='ok':continue
  for eps in [.01,.001,.0001]:
   target=best[r['scene']]*(1+eps);hit=None
   if 'trace' in r:
    trace=r['trace'];over=max(0,r['seconds']-float(trace[-1]['wall_s']))
    hit=next((float(t['wall_s'])+over+.000101 for t in trace if float(t['cost'])<=target),None)
   elif r['cost']<=target:hit=r['seconds']+.000001
   crosses.append(dict(experiment=r['experiment'],scene=r['scene'],arm=r['arm'],rep=r['rep'],epsilon=eps,target=target,solver_upper=hit,setup_inclusive_upper=None if hit is None else hit+r.get('setup_seconds',0),certification='checked endpoint only' if 'trace' not in r else 'accepted fp64 trace'))
 a.out.write_text('\n'.join(lines)+'\n');(a.root/'novelty-crossings.json').write_text(json.dumps(crosses,indent=2)+'\n');(a.root/'novelty-results.json').write_text(json.dumps(rows,indent=2)+'\n')
 print('Retained completed/failed records:',len(rows))
if __name__=='__main__':main()
