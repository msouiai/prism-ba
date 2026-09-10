#!/usr/bin/env python3
"""Generate predeclared bounded repaired-step damping plans."""
import argparse,pathlib,json
p=argparse.ArgumentParser();p.add_argument('stage',choices=['audit','medium']);a=p.parse_args();r=pathlib.Path('/workspace/prism-repair-damping');jobs=[]
def add(scene,arm,ps,rd,rep=1,cap=3,target=None,iters=100000):
 j=dict(scene=scene,name=f'{scene}-{arm}-{rep}',arm=arm,point=ps,controller=rd,rep=rep,cap=cap,iters=iters,trace=True,flags=dict(OCA_NSHIFTS='5',OCA_DEMAND_MENU='2',OCA_POINT_SAFEGUARD=str(ps),OCA_REPAIR_DAMPING=str(rd)))
 if target is not None:j['target']=target
 jobs.append(j)
if a.stage=='audit':
 for scene in ['dubrovnik-356','ladybug-1197']:add(scene,'audit',1,1,cap=3)
else:
 scenes=[('ladybug-1197',366600,6),('dubrovnik-356',754100,8)]
 arms=[('plain',0,0),('frozen',1,0),('relax',1,2),('symmetric',1,3),('no-point-relax',0,2)]
 for rep in [1,2]:
  for scene,target,cap in scenes if rep==1 else reversed(scenes):
   for arm,ps,rd in arms if rep==1 else reversed(arms):add(scene,arm,ps,rd,rep,cap,target)
plan=dict(root=str(r),stage=a.stage,binary=str(r/'prism-v1'),jobs=jobs);out=r/(a.stage+'-plan.json');assert not out.exists();out.write_text(json.dumps(plan,indent=2)+'\n');print(out)
