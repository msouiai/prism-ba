#!/usr/bin/env python3
import argparse,datetime,json,math,pathlib,re,statistics
import numpy as np
import rl_damping_pilot as p
import rl_damping_trajectory as t
ROOT=pathlib.Path('/tmp/prism-reference-forcing');BIN=ROOT/'build-v2/prism-tr'
PARENT=pathlib.Path('/tmp/prism-ba-accuracy/build/prism-tr')
p.ROOT=ROOT;p.NATIVE_CAP=600;t.ROOT=ROOT
ARMS={'champion':{'OCA_RLA_FIXED_ETA':2},'probe':{'OCA_RRF':1},'reference':{'OCA_RRF':2},
 'reference-safe':{'OCA_RRF':3},'reduced-ew2':{'OCA_BAC':3}}
def read(n):return json.loads((ROOT/n).read_text())
def put(n,v):p.put(ROOT/n,v)
def run(name,scene,arm,lam=.1,target=None,cap=4,iters=600,binary=BIN,verify=False):
 flags=dict(ARMS[arm],OCA_MAX_SECONDS=cap)
 if target is not None:flags['OCA_TARGET_COST']=target
 if verify:flags['OCA_RRF_VERIFY']=1
 r=p.run(name,scene,extra=flags,binary=binary,initial_lambda=lam,logging=False,iterations=iters,
  process_timeout=180 if scene==t.LARGE else 45)
 text=(ROOT/'runs'/name/'stdout.log').read_text()
 m=re.search(r'REFERENCE_SUMMARY (.*)',text)
 if m:r['reference_summary']={k:float(v) for k,v in re.findall(r'(\w+)=(\S+)',m[1])}
 return r
def row(r,scene,lam,arm,rep,target,cap,quality='primary'):
 rr=t.row(r,scene,lam,arm,rep,target,cap);rr['quality']=quality;rr['reference_summary']=r.get('reference_summary',{})
 return rr
def register():
 proto=dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),arms=ARMS,train=t.TRAIN,transfer=t.TRANSFER,
  binary_sha256=p.sha(BIN),parent_sha256=p.sha(PARENT),code_sha256=p.sha(__file__),
  protocol_sha256=p.sha(pathlib.Path(__file__).parents[1]/'docs/reference_forcing_protocol.md'),
  input_sha256={s:p.sha(p.DATA/(s+'.txt')) for s in list(t.TRAIN)+list(t.TRANSFER)+[t.LARGE]})
 if not (ROOT/'protocol.json').exists():put('protocol.json',proto)
 else:
  old=read('protocol.json');assert all(old[k]==proto[k] for k in ['binary_sha256','parent_sha256','code_sha256','protocol_sha256','input_sha256'])
def smoke():
 register();rows=[]
 for rep in range(3):
  rs=[]
  for arm,binary,verify,label in [('champion',PARENT,False,'parent'),('champion',BIN,False,'off'),('probe',BIN,False,'probe'),('probe',BIN,True,'verify')]:
   r=run(f'smoke-{label}-{rep}','ladybug-49',arm,iters=8,binary=binary,verify=verify);rs.append(r);rows.append(r)
  assert len({(r['outers'],r['rejects'],r['matvecs']) for r in rs})==1
  costs=[r['audit_cost'] for r in rs];assert (max(costs)-min(costs))/min(costs)<1e-7
  assert rs[-1]['reference_summary']['verifications']>=8
  assert rs[-1]['reference_summary']['identity_error']<1e-7
 J=np.array([[2.,1.,0.],[0.,2.,1.],[1.,0.,3.],[2.,-1.,1.]])
 residual=np.array([1.,2.,-.5,1.]);H=J.T@J;g=J.T@residual;E=1/np.sqrt(np.diag(H)[:2])
 def b(H,g,lam):return g[:2]-H[:2,2:]@np.linalg.solve(H[2:,2:]+lam*np.diag(np.diag(H)[2:]),g[2:])
 old=np.linalg.norm(E*b(H,g,.1));naive=np.linalg.norm(E*b(H,g,10))/old
 assert abs(naive-1)>.05
 for actual in [.01,.1,10]:
  fixed=np.linalg.norm(E*b(H,g,.1))/old;assert abs(fixed-1)<1e-14
 # New geometry evaluated with the old metric/damping, independently of actual lambda.
 Hnew=(J*1.1).T@(J*1.1);gnew=(J*1.1).T@residual
 q=np.linalg.norm(E*b(Hnew,gnew,.1))/old;assert abs(q-1.1)<1e-12
 put('smoke.json',dict(passed=True,binary_sha256=p.sha(BIN),naive_fixed_geometry_ratio=naive,reference_fixed_geometry_ratio=1,
  reference_changed_geometry_ratio=q,maximum_gpu_identity_error=max(r.get('reference_summary',{}).get('identity_error',0) for r in rows)))
 print('SMOKE PASSED',read('smoke.json'),flush=True)
def train():
 register();assert read('smoke.json')['passed'];rows=[]
 for rep in range(3):
  for si,(scene,(target,cap)) in enumerate(t.TRAIN.items()):
   names=list(ARMS);off=(rep+si)%len(names)
   for a in names[off:]+names[:off]:
    r=run(f'train-{scene}-{a}-{rep}',scene,a,target=target,cap=cap)
    rows.append(row(r,scene,.1,a,rep,target,cap));put('train-rows.json',rows)
   p.CACHE.clear();print('TRAIN',scene,rep,flush=True)
def select():
 rs=read('train-rows.json');assert len(rs)==45;scores={};task_scores={}
 for a in ARMS:
  values={}
  for s in t.TRAIN:
   def score(arm):
    rr=[r for r in rs if r['scene']==s and r['arm']==arm];assert len(rr)==3
    return statistics.median(r['target_seconds'] if r['hit'] else 4*r['cap'] for r in rr)
   values[s]=math.log(score(a)/score('champion'))
  task_scores[a]=values;scores[a]=statistics.mean(values.values())
 best=min(['reference','reference-safe'],key=scores.get)
 put('selection.json',dict(selected=best,log_losses=scores,task_log_losses=task_scores,binary_sha256=p.sha(BIN),scope='nominal lambda0.1 development only; no stress/transfer selection'))
 print('SELECT',read('selection.json'),flush=True)
def evaluate(phase):
 register();sel=read('selection.json');assert sel['binary_sha256']==p.sha(BIN)
 if phase=='stress':tasks=[('dubrovnik-356',10.,'stress',*t.TRAIN['dubrovnik-356'])];names=['champion','probe',sel['selected']]
 else:
  base={t.LARGE:(t.LARGE_TARGET,20)} if phase=='large' else t.TRANSFER
  if phase=='large':assert read('transfer-verdict.json')['extend']
  tasks=[];names=['champion','probe','reduced-ew2',sel['selected']]
  for s,(q,cap) in base.items():
   tasks.append((s,.1,'primary',q,cap))
   if s!='muell-gba146':tasks.append((s,.1,'tighter',q/1.01,cap))
 rows=[]
 for si,(s,lam,quality,q,cap) in enumerate(tasks):
  for rep in range(3):
   off=(si+rep)%len(names)
   for a in names[off:]+names[:off]:
    r=run(f'{phase}-{quality}-{s}-{a}-{rep}',s,a,lam,target=q,cap=cap)
    rr=row(r,s,lam,a,rep,q,cap,quality);rows.append(rr);put(phase+'-rows.json',rows)
    print(phase,quality,s,a,rep,rr['hit'],rr['target_seconds'],flush=True)
  p.CACHE.clear()
 ratios={}
 for s,lam,quality,q,cap in tasks:
  cs={a:[r for r in rows if r['scene']==s and r['quality']==quality and r['arm']==a] for a in names}
  ok=all(r['hit'] for a in ['champion',sel['selected']] for r in cs[a])
  ratios[f'{s}/{quality}']=statistics.median(r['target_seconds'] for r in cs['champion'])/statistics.median(r['target_seconds'] for r in cs[sel['selected']]) if ok else None
 geo=math.exp(statistics.mean(math.log(v) for v in ratios.values())) if all(v is not None for v in ratios.values()) else None
 put(phase+'-verdict.json',dict(speedups=ratios,geometric_speedup=geo,extend=geo is not None and geo>=1.05 and min(ratios.values())>=1/1.1))
 print('VERDICT',phase,read(phase+'-verdict.json'),flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['smoke','train','select','stress','transfer','large']);a=ap.parse_args()
 if a.phase in ['stress','transfer','large']:evaluate(a.phase)
 else:globals()[a.phase]()
