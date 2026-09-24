#!/usr/bin/env python3
"""Frozen local-census extension; symmetric calibration, then held-out timing runs.

No solver tuning. Failures are retained; an arm failing calibration is marked
unavailable for that scene rather than silently removed from denominators.
"""
import hashlib,json,pathlib,random,subprocess,sys,time
ROOT=pathlib.Path('/workspace/prism-caspar-expanded')
PRISM=pathlib.Path('/workspace/prism-early-restart/prism-v7')
CASPAR=pathlib.Path('/workspace/prism-caspar-current/caspar64')
SCENES=['ladybug-49','trafalgar-126','dubrovnik-88','dubrovnik-356','final-871','final-3068','venice-951','venice-1672','venice-1778','final-1936','final-4585','final-13682']
def write(p,v):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(v,indent=2)+'\n');t.replace(p)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def run(j,phase):
 dest=ROOT/phase/j['name'];dest.mkdir(parents=True,exist_ok=True);rp=dest/'record.json'
 if rp.exists():return json.loads(rp.read_text())
 if (dest/'results.json').exists():
  row=json.loads((dest/'results.json').read_text())[0];row.update(status='ok',artifact_dir=str(dest),orchestration_wall=None,recovered_completed_result=True);write(rp,row);return row
 (dest/'prism').mkdir(exist_ok=True)
 if not (dest/'caspar64').exists():(dest/'caspar64').symlink_to(CASPAR)
 write(dest/'plan.json',dict(root=str(dest),prism_binary=str(PRISM),jobs=[j]))
 print('RUN',phase,j['name'],flush=True);start=time.monotonic()
 with (dest/'orchestrator.log').open('a') as f:
  q=subprocess.run([sys.executable,str(pathlib.Path(__file__).with_name('current_caspar_comparison.py')),str(dest/'plan.json')],stdout=f,stderr=subprocess.STDOUT)
 if q.returncode==0:
  row=json.loads((dest/'results.json').read_text())[0];row.update(status='ok',artifact_dir=str(dest))
 else:row=dict(j,status='failed',hit=False,crossing=None,artifact_dir=str(dest),returncode=q.returncode,error_tail=(dest/'orchestrator.log').read_text()[-2500:])
 row['orchestration_wall']=time.monotonic()-start;write(rp,row)
 print('DONE',phase,j['name'],row['status'],'hit',row['hit'],'cost',row.get('cost'),'cross',row.get('crossing'),flush=True)
 return row

def main():
 ROOT.mkdir(exist_ok=True);scenes=[]
 for s in SCENES:
  p=pathlib.Path('/workspace/bal')/(s+'.txt')
  with p.open() as f:nc,np_,no=map(int,f.readline().split())
  cap=4 if no<1000000 else 8 if no<3000000 else 12 if no<6000000 else 20
  scenes.append(dict(scene=s,cameras=nc,points=np_,observations=no,cap=cap,data_sha256=sha(p)))
 protocol=dict(scenes=scenes,prism_sha256=sha(PRISM),caspar_sha256=sha(CASPAR),repeats=3,levels={'loose':1.02,'medium':1.005,'tight':1.0},seed=20260908,process_timeout=180,calibration_target=1e-100,reference='minimum independently audited endpoint of equal-native-budget calibration arms',calibration_excluded=True)
 if (ROOT/'protocol.json').exists():assert json.loads((ROOT/'protocol.json').read_text())==protocol
 else:write(ROOT/'protocol.json',protocol)
 calibration=[]
 for i,s in enumerate(scenes):
  for arm in (['restart','caspar64'] if i%2==0 else ['caspar64','restart']):
   j=dict(scene=s['scene'],arm=arm,level='calibration',target=1e-100,cap=s['cap'],rep=0,process_timeout=180,name=s['scene']+'-'+arm+'-calibration')
   calibration.append(run(j,'calibration'));write(ROOT/'calibration.json',calibration)
 anchors={};unavailable=[]
 for s in SCENES:
  ok=[x for x in calibration if x['scene']==s and x['status']=='ok']
  if ok:anchors[s]=min(x['cost'] for x in ok)
  unavailable.extend((x['scene'],x['arm']) for x in calibration if x['scene']==s and x['status']!='ok')
 jobs=[];rng=random.Random(protocol['seed'])
 for rep in range(1,4):
  order=scenes.copy();rng.shuffle(order)
  for i,s in enumerate(order):
   levels=list(protocol['levels'].items());rng.shuffle(levels)
   for k,(level,mult) in enumerate(levels):
    for arm in (['restart','caspar64'] if (rep+i+k)%2 else ['caspar64','restart']):
     jobs.append(dict(scene=s['scene'],arm=arm,level=level,target=anchors.get(s['scene'],0)*mult,anchor=anchors.get(s['scene']),cpu_cache=str(ROOT/'cpu-cache'),cap=s['cap'],rep=rep,process_timeout=180,name=f"{s['scene']}-{level}-{arm}-{rep}"))
 p=dict(jobs=jobs,anchors=anchors,unavailable=unavailable)
 if (ROOT/'measurement-plan.json').exists():assert json.loads((ROOT/'measurement-plan.json').read_text())==json.loads(json.dumps(p))
 else:write(ROOT/'measurement-plan.json',p)
 print('CALIBRATION COMPLETE; FROZEN',len(jobs),'measurement jobs',flush=True)
 rows=[]
 for j in jobs:
  assert sha(PRISM)==protocol['prism_sha256'] and sha(CASPAR)==protocol['caspar_sha256']
  if (j['scene'],j['arm']) in unavailable or j['anchor'] is None:
   row=dict(j,status='unavailable_after_calibration',hit=False,crossing=None)
  else:row=run(j,'measurements')
  rows.append(row);write(ROOT/'partial-results.json',rows)
 write(ROOT/'results.json',rows)
 print('COMPLETE',len(rows),flush=True)
if __name__=='__main__':main()
