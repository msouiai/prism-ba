#!/usr/bin/env python3
import argparse,datetime,json,math,pathlib,re,statistics
import numpy as np
import rl_damping_pilot as p
import rl_damping_trajectory as t
ROOT=pathlib.Path('/tmp/prism-cg-value');BIN=ROOT/'build/prism-tr'
PARENT=pathlib.Path('/tmp/prism-reference-forcing/build-v2/prism-tr')
p.ROOT=ROOT;p.NATIVE_CAP=600;t.ROOT=ROOT
ARMS={'champion':{'OCA_RLA_FIXED_ETA':2},'passive':{'OCA_RLA_FIXED_ETA':2,'OCA_CGV':1},
 'rate':{'OCA_RLA_FIXED_ETA':2,'OCA_CGV':2},'conservative':{'OCA_RLA_FIXED_ETA':2,'OCA_CGV':3},
 'work-only':{'OCA_RLA_FIXED_ETA':2,'OCA_CGV':4}}
def read(n):return json.loads((ROOT/n).read_text())
def put(n,v):p.put(ROOT/n,v)
def run(name,scene,arm,lam=.1,target=None,cap=4,iters=600,binary=BIN,verify=False):
 flags=dict(ARMS[arm],OCA_MAX_SECONDS=cap)
 if target is not None:flags['OCA_TARGET_COST']=target
 if verify:flags['OCA_CGV_VERIFY']=1
 r=p.run(name,scene,extra=flags,binary=binary,initial_lambda=lam,logging=False,iterations=iters,
  process_timeout=180 if scene==t.LARGE else 45)
 text=(ROOT/'runs'/name/'stdout.log').read_text()
 m=re.search(r'CG_VALUE_SUMMARY (.*)',text)
 if m:r['value_summary']={k:float(v) for k,v in re.findall(r'(\w+)=(\S+)',m[1])}
 return r
def row(r,scene,lam,arm,rep,target,cap,quality='primary'):
 rr=t.row(r,scene,lam,arm,rep,target,cap);rr['quality']=quality;rr['value_summary']=r.get('value_summary',{})
 return rr
def register():
 proto=dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),arms=ARMS,train=t.TRAIN,transfer=t.TRANSFER,
  binary_sha256=p.sha(BIN),parent_sha256=p.sha(PARENT),code_sha256=p.sha(__file__),
  protocol_sha256=p.sha(pathlib.Path(__file__).parents[1]/'docs/cg_value_protocol.md'),
  input_sha256={s:p.sha(p.DATA/(s+'.txt')) for s in list(t.TRAIN)+list(t.TRANSFER)+[t.LARGE]})
 if not (ROOT/'protocol.json').exists():put('protocol.json',proto)
 else:
  old=read('protocol.json');assert all(old[k]==proto[k] for k in ['binary_sha256','parent_sha256','code_sha256','protocol_sha256','input_sha256'])
def smoke():
 register();rows=[]
 for rep in range(3):
  rs=[]
  for arm,binary,verify,label in [('champion',PARENT,False,'parent'),('champion',BIN,False,'off'),('passive',BIN,False,'passive'),('passive',BIN,True,'verify')]:
   r=run(f'smoke-{label}-{rep}','ladybug-49',arm,iters=8,binary=binary,verify=verify);rs.append(r);rows.append(r)
  assert len({(r['outers'],r['rejects'],r['matvecs']) for r in rs[:3]})==1
  costs=[r['audit_cost'] for r in rs];assert (max(costs)-min(costs))/min(costs)<1e-7
  assert rs[-1]['value_summary']['checks']>0
  assert rs[-1]['value_summary']['identity_error']<1e-6
 # Independent dense PCG: accumulated delta equals direct model decrease.
 rng=np.random.default_rng(412);B=rng.normal(size=(12,12));A=B.T@B+np.eye(12)*.5
 rhs=rng.normal(size=12);x=np.zeros(12);r=rhs.copy();M=np.diag(A);z=r/M;d=z.copy();rz=r@z;gain=0.;errors=[]
 for j in range(12):
  Ad=A@d;alpha=rz/(d@Ad);gain+=.5*alpha*rz;x+=alpha*d;r-=alpha*Ad
  direct=rhs@x-.5*x@A@x;errors.append(abs(direct-gain)/max(1.,abs(direct)))
  z=r/M;next_rz=r@z;d=z+(next_rz/rz)*d;rz=next_rz
 assert max(errors)<1e-12
 put('smoke.json',dict(passed=True,binary_sha256=p.sha(BIN),maximum_cpu_identity_error=max(errors),
  maximum_gpu_identity_error=max(r.get('value_summary',{}).get('identity_error',0) for r in rows)))
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
 best=min(['rate','conservative'],key=scores.get)
 put('selection.json',dict(selected=best,log_losses=scores,task_log_losses=task_scores,binary_sha256=p.sha(BIN),scope='nominal lambda0.1 development only; no stress/transfer selection'))
 print('SELECT',read('selection.json'),flush=True)
def evaluate(phase):
 register();sel=read('selection.json');assert sel['binary_sha256']==p.sha(BIN)
 if phase=='stress':tasks=[('dubrovnik-356',10.,'stress',*t.TRAIN['dubrovnik-356'])];names=['champion','passive',sel['selected']]
 else:
  base={t.LARGE:(t.LARGE_TARGET,20)} if phase=='large' else t.TRANSFER
  if phase=='large':assert read('transfer-verdict.json')['extend']
  tasks=[];names=['champion','passive','work-only',sel['selected']]
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
