#!/usr/bin/env python3
"""CPU-audited report for the frozen five-instance large BAL screen."""
import argparse,hashlib,json,pathlib,re
from five_large_screen import SCENES

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,default=pathlib.Path('/workspace/prism-five-large'));p.add_argument('--partial',action='store_true');a=p.parse_args();root=a.root
 rows=[json.loads(p.read_text()) for p in sorted((root/'budgets').glob('*.result.json'))]
 by={(r['scene'],r['arm']):r for r in rows};assert len(by)==len(rows)
 peaks={}
 for line in (root/'gpu-samples.jsonl').read_text().splitlines():
  try:sample=json.loads(line)
  except json.JSONDecodeError:continue # the live sampler may be writing the last line
  for q in sample['processes']:
   scene=next((s for s in SCENES if s+'.txt' in q['command']),None)
   if not scene:continue
   if q['name']==str(root/'prism-frozen'):arm='selected' if '-selected-' in q['command'] else 'single'
   elif q['name']=='/workspace/prism-validation/caspar-frozen':arm='caspar32'
   else:continue
   peaks[scene,arm]=max(peaks.get((scene,arm),0),q['MiB'])
 for r in rows:
  scene,arm=r['scene'],r['arm'];stem=root/'budgets'/f'{scene}-{arm}-30s-1';log=stem.with_suffix('.log').read_text()
  r['sampled_peak_MiB']=peaks.get((scene,arm))
  if r['status']!='ok':continue
  if arm=='caspar32':
   acc=list(map(int,re.findall(r'TRACE .*?accepted=(\d+)',log)));r['accepts']=sum(acc);r['rejects']=len(acc)-sum(acc)
   r['stop']='budget' if r['budget_guard_fired'] else {0:'iteration cap',1:'score threshold',2:'damping limit'}[r['exit_reason']]
  else:
   r['stop']='budget' if r['budget_guard_fired'] else 'relative improvement' if 'converged (OCA_FTOL' in log else 'solver stop'
   if not a.partial:
    assert hashlib.sha256(stem.with_suffix('.state').read_bytes()).hexdigest()==r['state_sha256']
 for scene in SCENES:
  rr=[by.get((scene,arm)) for arm in ['selected','single','caspar32']]
  if all(r and r['status']=='ok' for r in rr):
   print(scene,[(r['arm'],round(r['cost'],3),round(r['seconds'],3),r['rejects'],r['stop']) for r in rr],flush=True)
 print('completed',len(rows),'of 15; successful',sum(r['status']=='ok' for r in rows),flush=True)
 if a.partial:return
 assert len(rows)==15,'study incomplete'
 report='''# Five additional large BAL instances — 2026-09-07

Frozen compact FP64 mode 2, unchanged selected rearm-only multi-shift policy,
guarded single-shift, and frozen Caspar FP32 defaults. Five cases selected
before results; N=1 per method, 30-second native solve budget, 180-second
process timeout. No parameter retuning or added repeats. Method order was
multi, single, Caspar, not randomized. The two Venice instances are related
snapshots; five BA instances do not represent five independent landmarks.

Sources: [Final](https://grail.cs.washington.edu/projects/bal/final.html),
[Venice](https://grail.cs.washington.edu/projects/bal/venice.html), and
[Dubrovnik](https://grail.cs.washington.edu/projects/bal/dubrovnik.html).
All five were absent from the earlier local dataset collection.

| Instance | Cameras | Points | Observations |
|---|---:|---:|---:|
'''
 for scene in SCENES:
  with (pathlib.Path('/workspace/bal')/(scene+'.txt')).open() as f:nc,np,no=map(int,f.readline().split())
  report+=f'| {scene} | {nc:,} | {np:,} | {no:,} |\n'
 report+='''
## Endpoints and native runtimes

CPU raw-z FP64 final cost, lower is better. Actual native solve runtimes may
exceed 30 seconds: late candidates are discarded, but unfinished attempts
are allowed to finish. Methods may stop early under their own stopping rules.
Times are not common time-to-quality crossings or equal end-to-end latency.

| Instance | Multi cost | Single cost | Caspar cost | Multi s | Single s | Caspar s |
|---|---:|---:|---:|---:|---:|---:|
'''
 comparisons=[]
 for scene in SCENES:
  rr=[by[scene,arm] for arm in ['selected','single','caspar32']]
  if all(r['status']=='ok' for r in rr):
   report+='| '+scene+' | '+' | '.join(f"{r['cost']:,.3f}" for r in rr)+' | '+' | '.join(f"{r['seconds']:.3f}" for r in rr)+' |\n'
   m,s,c=rr;comparisons.append(dict(scene=scene,multi_vs_caspar_pct=100*(m['cost']/c['cost']-1),single_vs_caspar_pct=100*(s['cost']/c['cost']-1),multi_vs_single_pct=100*(m['cost']/s['cost']-1)))
  else:report+='| '+scene+' | incomplete: '+', '.join(r['arm']+'='+r['status'] for r in rr)+' | | | | | |\n'
 report+='\n| Instance | Multi vs Caspar cost | Single vs Caspar cost | Multi vs single cost |\n|---|---:|---:|---:|\n'
 for c in comparisons:report+=f"| {c['scene']} | {c['multi_vs_caspar_pct']:+.3f}% | {c['single_vs_caspar_pct']:+.3f}% | {c['multi_vs_single_pct']:+.3f}% |\n"
 report+='''
Negative cost differences favor the numerator. Small differences are not
statistical wins: each cell has one run, and atomic-order variation can
change trajectories and stopping. Do not divide unequal-quality runtimes
and call the ratio an algorithm speedup.

## Work, memory, and stopping

| Instance | Method | Accepted | Rejected | Matvecs | Scored | Rearms | GPU MiB sampled | Overshoot s | Stop |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
'''
 for scene in SCENES:
  for arm in ['selected','single','caspar32']:
   r=by[scene,arm]
   if r['status']!='ok':report+=f'| {scene} | {arm} | failed | | | | | | | |\n';continue
   report+=f"| {scene} | {arm} | {r['accepts']} | {r['rejects']} | {r.get('matvecs','—')} | {r.get('total_scored','—')} | {r.get('rearms','—')} | {r['sampled_peak_MiB']} | {r['overshoot_seconds']:.3f} | {r['stop']} |\n"
 report+='''
Work counts include unfinished overbudget work; GPU memory is sampled process
usage, not an allocator-certified peak. Caspar rejection counts are native
trace rejected iterations; PRISM reports its rejected attempts. Damping-limit
exit is a solver stopping decision, not a certificate of optimality. If rearm
never activates, do not attribute a result to that safeguard.

## Numerical checks and interpretation

PRISM preserves FP64 arithmetic and raw-z projection; Caspar FP32 uses its
native epsilon-guarded projection. The common CPU endpoint scorer uses raw-z.
Initialization is also affected by Caspar's float conversion. Thus this is a
practical implementation screen, not a matched-precision algorithm ablation.
Setup boundaries remain as in [fixed-policy validation](fixed_policy_validation.md).

| Instance | Multi CPU/GPU relative error | Single CPU/GPU relative error | Caspar native/CPU final gap | Caspar initial quantization gap |
|---|---:|---:|---:|---:|
'''
 for scene in SCENES:
  rr=[by[scene,arm] for arm in ['selected','single','caspar32']]
  if all(r['status']=='ok' for r in rr):
   m,s,c=rr;report+=f"| {scene} | {m['audit_relerr']:.3g} | {s['audit_relerr']:.3g} | {100*c['native_final_relerr']:.6f}% | {100*c['initial_quantization_relerr']:.6f}% |\n"
 report+='''
All successful PRISM endpoints pass the independent CPU audit at 1e-7
relative tolerance. Exact exported state hashes are verified. Frozen binary,
input hashes, commands, flags, logs, stderr, protocol, and sampler output are
retained at `/workspace/prism-five-large/`. Original results remain separate
from earlier cohorts. Reproduce with `python3 bench/five_large_screen.py`
after preparing the frozen artifacts and downloading the five scenes.
The downloader now accepts three additional public cases without changing
its default REPRODUCE dataset list. Python compilation and diff checks pass.
The broader queue stays paused; solver defaults are unchanged; nothing pushed.
'''
 pathlib.Path('/workspace/prism-ba/docs/five_large_results.md').write_text(report)
 summary=dict(rows=rows,comparisons=comparisons,runs=len(rows),failures=sum(r['status']!='ok' for r in rows),native_solve_seconds=sum(r.get('seconds',0) for r in rows))
 (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(root/'completion.json').write_text(json.dumps({k:v for k,v in summary.items() if k not in ['rows','comparisons']}|{'status':'complete'},indent=2)+'\n')
if __name__=='__main__':main()
