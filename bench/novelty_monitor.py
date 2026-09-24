#!/usr/bin/env python3
"""Refresh retained reports and flag protocol completion without dropping failures."""
import argparse,json,pathlib,subprocess,sys,time,datetime
p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,required=True);p.add_argument('--repo',type=pathlib.Path,required=True);a=p.parse_args()
expected={'ablation-development','ablation-evaluation','ablation-perturbed','caspar32-development','caspar32-evaluation','caspar32-perturbed','ceres-tuning','ceres-evaluation','ceres-perturbed'}
def status():
 cells=[]
 for name in sorted(expected):
  folder=a.root/name;mp=folder/'preregistered.json'
  if not mp.exists():cells.append(dict(experiment=name,state='not yet launched'));continue
  m=json.loads(mp.read_text());arms=list(m['arms']) if 'arms' in m else [f"{m['kind']}-{pr}-{b}" for pr in m['profiles'] for b in m['budgets']]
  ok=bad=missing=0
  for scene in m['scenes']:
   for arm in arms:
    for rep in range(1,m['reps']+1):
     f=folder/f'{scene}-{arm}-{rep}.json'
     if not f.exists():missing+=1;continue
     try:r=json.loads(f.read_text())
     except json.JSONDecodeError:missing+=1;continue
     if r.get('status','ok')=='ok':ok+=1
     else:bad+=1
  cells.append(dict(experiment=name,state='complete' if missing==0 else 'running',successful=ok,failed=bad,missing=missing))
 done=all(c['state']=='complete' for c in cells)
 return dict(updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),local_nonlinear_complete=done,second_gpu='unavailable',experiments=cells)
while True:
 s=status();(a.root/'study-status.json').write_text(json.dumps(s,indent=2)+'\n')
 subprocess.run([sys.executable,str(a.repo/'bench/novelty_report.py'),'--root',str(a.root),'--out',str(a.repo/'docs/novelty_results.md')],check=True)
 print(json.dumps(s),flush=True)
 if s['local_nonlinear_complete']:
  subprocess.run([sys.executable,str(a.repo/'bench/plot_novelty.py'),'--root',str(a.root),'--out',str(a.root/'figures')],check=True)
  print('All declared local nonlinear cells retained. Failures remain failures; second GPU is pending.',flush=True)
  break
 time.sleep(60)
