#!/usr/bin/env python3
import argparse,datetime,json,math,pathlib,statistics
import numpy as np
import rl_damping_pilot as p
import rl_damping_trajectory as t
ROOT=pathlib.Path('/tmp/prism-ba-accuracy');BIN=ROOT/'build/prism-tr'
PARENT=pathlib.Path('/tmp/prism-rl-actor/build/prism-tr')
p.ROOT=ROOT;p.NATIVE_CAP=600;t.ROOT=ROOT
ARMS={'original':{},'champion':{'OCA_RLA_FIXED_ETA':2},'constant':{'OCA_BAC':1},
 'reduced-ew2':{'OCA_BAC':3},'gradient-ew2':{'OCA_BAC':2},'model':{'OCA_BAC':4},'joint':{'OCA_BAC':5}}
def read(n):return json.loads((ROOT/n).read_text())
def put(n,v):p.put(ROOT/n,v)
def run(name,scene,arm,lam,target=None,cap=4,iters=600,binary=BIN,logging=False):
 flags=dict(ARMS[arm],OCA_MAX_SECONDS=cap)
 if target is not None:flags['OCA_TARGET_COST']=target
 return p.run(name,scene,extra=flags,binary=binary,initial_lambda=lam,logging=logging,iterations=iters,
              process_timeout=180 if scene==t.LARGE else 45)
def register():
 proto=dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),arms=ARMS,
  train=t.TRAIN,transfer=t.TRANSFER,large_target=t.LARGE_TARGET,binary_sha256=p.sha(BIN),
  parent_sha256=p.sha(PARENT),protocol_sha256=p.sha(pathlib.Path(__file__).parents[1]/'docs/ba_accuracy_protocol.md'),
  code_sha256=p.sha(__file__),input_sha256={s:p.sha(p.DATA/(s+'.txt')) for s in list(t.TRAIN)+list(t.TRANSFER)+[t.LARGE]})
 path=ROOT/'protocol.json'
 if not path.exists():put('protocol.json',proto)
 else:
  old=read('protocol.json');assert all(old[k]==proto[k] for k in ['binary_sha256','parent_sha256','protocol_sha256','code_sha256','input_sha256'])
def smoke():
 register();rs=[]
 for rep in range(3):
  for arm,binary,label in [('champion',PARENT,'parent'),('champion',BIN,'new-champion'),('original',PARENT,'parent-off'),('original',BIN,'new-off')]:
   rs.append((label,run(f'smoke-{label}-{rep}','ladybug-49',arm,.1,iters=8,binary=binary)))
 for rep in range(3):
  for offset in [0,2]:
   a,b=[r for label,r in rs[rep*4+offset:rep*4+offset+2]]
   assert (a['outers'],a['rejects'],a['matvecs'])==(b['outers'],b['rejects'],b['matvecs'])
   assert abs(a['audit_cost']-b['audit_cost'])/a['audit_cost']<1e-7
 # Full block residual identity and lambda dependence of reduced RHS.
 J=np.array([[2.,1.,0.],[0.,2.,1.],[1.,0.,3.],[2.,-1.,1.]])
 residual=np.array([1.,2.,-.5,1.]);H=J.T@J;g=J.T@residual;bs=[]
 for lam in [.1,10.]:
  A=H+lam*np.eye(3);W=A[:2,2:];V=A[2:,2:]
  b=g[:2]-W@np.linalg.solve(V,g[2:]);bs.append(b)
  d=np.array([.1,-.2]);dp=np.linalg.solve(V,g[2:]-W.T@d)
  full=A@np.r_[d,dp]-g;schur=(A[:2,:2]-W@np.linalg.solve(V,W.T))@d-b
  assert np.max(abs(full[:2]-schur))<1e-12 and abs(full[2])<1e-12
 assert np.linalg.norm(bs[0]-bs[1])>.1
 put('smoke.json',dict(passed=True,schur_rhs_change=float(np.linalg.norm(bs[0]-bs[1])),binary_sha256=p.sha(BIN)))
 print('SMOKE PASSED',flush=True)
def train():
 register();assert read('smoke.json')['passed'];rows=[]
 for rep in range(3):
  for si,(scene,(target,cap)) in enumerate(t.TRAIN.items()):
   for li,lam in enumerate([.1,10.]):
    names=list(ARMS);offset=(rep+si+li)%len(names);names=names[offset:]+names[:offset]
    for arm in names:
     r=run(f'train-{scene}-l{lam}-{arm}-{rep}',scene,arm,lam,target,cap)
     rows.append(t.row(r,scene,lam,arm,rep,target,cap));put('train-rows.json',rows)
    print('TRAIN',scene,lam,rep,flush=True)
   p.CACHE.clear()
 t.summarize(rows,'train-summary.json')
def select():
 rows=read('train-rows.json');assert len(rows)==126
 scores={};task_scores={}
 for a in ARMS:
  values={}
  for s in t.TRAIN:
   for lam in [.1,10.]:
    def score(arm):
     rr=[r for r in rows if r['scene']==s and r['lambda0']==lam and r['arm']==arm];assert len(rr)==3
     return statistics.median(r['target_seconds'] if r['hit'] else 4*r['cap'] for r in rr)
    values[f'{s}/{lam}']=math.log(score(a)/score('champion'))
  scores[a]=statistics.mean(values.values());task_scores[a]=values
 candidates=['gradient-ew2','model','joint'];best=min(candidates,key=scores.get)
 family={}
 for s in t.TRAIN:
  a=min(['champion']+candidates,key=lambda a:statistics.mean(v for k,v in task_scores[a].items() if not k.startswith(s+'/')))
  family[s]=dict(selected=a,held_log_loss=statistics.mean(v for k,v in task_scores[a].items() if k.startswith(s+'/')))
 put('selection.json',dict(selected=best,log_losses=scores,task_log_losses=task_scores,family_holdout=family,
  binary_sha256=p.sha(BIN),scope='training only; fixed mapping, no parameter fit'))
 print('SELECT',best,scores,flush=True)
def evaluate(large=False):
 register();sel=read('selection.json');assert sel['binary_sha256']==p.sha(BIN)
 if large:
  assert read('transfer-verdict.json')['extend'];tasks={t.LARGE:(t.LARGE_TARGET,20)}
 else:tasks=t.TRANSFER
 phase='large' if large else 'transfer';rows=[];names=['champion','reduced-ew2',sel['selected']]
 for si,(scene,(target,cap)) in enumerate(tasks.items()):
  for quality,q in [('primary',target),('tighter',target/1.01)]:
   for rep in range(3):
    off=(rep+si)%3
    for a in names[off:]+names[:off]:
     r=run(f'{phase}-{quality}-{scene}-{a}-{rep}',scene,a,.1,q,cap)
     rr=t.row(r,scene,.1,a,rep,q,cap);rr['quality']=quality;rows.append(rr);put(phase+'-rows.json',rows)
     print(phase,quality,scene,a,rep,rr['hit'],rr['target_seconds'],flush=True)
  p.CACHE.clear()
 ratios=[]
 for scene in tasks:
  for quality in ['primary','tighter']:
   cs={a:[r for r in rows if r['scene']==scene and r['quality']==quality and r['arm']==a] for a in names}
   ok=all(r['hit'] for a in ['champion',sel['selected']] for r in cs[a])
   ratio=statistics.median(r['target_seconds'] for r in cs['champion'])/statistics.median(r['target_seconds'] for r in cs[sel['selected']]) if ok else None
   ratios.append(ratio)
 geo=math.exp(statistics.mean(math.log(v) for v in ratios)) if all(v is not None for v in ratios) else None
 put(phase+'-verdict.json',dict(speedups=ratios,geometric_speedup=geo,extend=geo is not None and geo>=1.05 and min(ratios)>=1/1.1))
 print('VERDICT',phase,read(phase+'-verdict.json'),flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['smoke','train','select','transfer','large']);a=ap.parse_args()
 if a.phase=='transfer':evaluate()
 elif a.phase=='large':evaluate(True)
 else:globals()[a.phase]()
