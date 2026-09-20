#!/usr/bin/env python3
"""Generate bounded, predeclared point safeguard plans; run with backtrack_investigation.py."""
import argparse,json,pathlib
p=argparse.ArgumentParser();p.add_argument('stage',choices=['sanity','medium','prospective']);a=p.parse_args()
r=pathlib.Path('/workspace/prism-point-safeguard');jobs=[]
def add(scene,arm,on,rep=1,cap=3,iters=80,target=None,binary=None):
 flags=dict(OCA_NSHIFTS='1' if arm=='single' else '5',OCA_DEMAND_MENU='2' if arm=='paired' else '0',OCA_POINT_SAFEGUARD=str(on))
 j=dict(scene=scene,name=f'{scene}-{arm}-{on}-{rep}',arm=arm,safeguard=on,rep=rep,cap=cap,iters=iters,flags=flags,trace=True)
 if target is not None:j['target']=target
 if binary:j['binary']=binary
 jobs.append(j)
if a.stage=='sanity':
 for scene in ['venice-52','dubrovnik-88']:
  add(scene,'paired',0,iters=40);add(scene,'paired',1,iters=40)
 add('venice-52','paired',0,rep=2,iters=40,binary='/workspace/prism-local-curvature/prism-v1')
elif a.stage=='medium':
 scenes=[('ladybug-1197',366600,6),('dubrovnik-356',754100,8)]
 for rep in [1,2]:
  for scene,target,cap in scenes if rep==1 else reversed(scenes):
   for arm in ['single','multi','paired'] if rep==1 else ['paired','multi','single']:
    for on in [0,1] if rep==1 else [1,0]:add(scene,arm,on,rep=rep,cap=cap,target=target,iters=100000)
else:
 for on in [0,1]:add('trafalgar-126','paired',on)
plan=dict(root=str(r),stage=a.stage,binary=str(r/'prism-v1'),jobs=jobs)
f=r/(a.stage+'-plan.json');assert not f.exists();f.write_text(json.dumps(plan,indent=2)+'\n');print(f)
