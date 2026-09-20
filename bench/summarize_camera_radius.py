#!/usr/bin/env python3
import pathlib,json,re,itertools
import numpy as np
from cached_benchmark_input import load_input
from audit_prism_state import audit
from profile_iterations import sha
ROOT=pathlib.Path('/workspace/prism-camera-radius')
def main():
 protocol=json.loads((ROOT/'protocol.json').read_text());assert sha(ROOT/'prism-radius')==protocol['binary_sha256'];assert sha(ROOT/'source-radius.cu')==protocol['source_sha256']
 for p,h in protocol['tooling_sha256'].items():assert sha(p)==h,p
 rows=[];errors=[];native=[];wall=[];audits=0
 def checked(path,expected,dims,obs):
  nonlocal audits
  value=audit(path,dims,obs);err=abs(value-expected)/max(1,abs(value));assert err<1e-7,(path,err);errors.append(err);audits+=1;return value
 def accepted(r):return r['base']>r['cost'] and r['prediction']>0 and r['rho']>=.1 and r['norm']<=r['radius']*(1+1e-8)
 for job in protocol['jobs']:
  scene=job['scene'];stem=ROOT/(scene+'-tr'+str(job['width']))
  dh,(dims,obs),initial=load_input(pathlib.Path('/workspace/bal')/(scene+'.txt'),'/workspace/prism-caspar-expanded/cpu-cache');assert dh==protocol['data_sha256'][scene]
  log=stem.with_suffix('.log').read_text();last=re.search(r'RESULT .*?final_cost=(\S+) solve_seconds=(\S+)',log);assert last
  checked(stem.with_suffix('.state'),float(last[1]),dims,obs);native.append(float(last[2]));wall.append(json.loads(stem.with_suffix('.process.json').read_text())['wall'])
  records=[{k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)} for line in log.splitlines() if line.startswith('RADIUS_CAPTURE')]
  for outer in protocol['captures']:
   r=sorted([v for v in records if v['o']==outer],key=lambda v:v['index']);assert len(r)==3
   prefix=str(stem)+'-o'+str(outer)
   base=checked(pathlib.Path(prefix+'-base.state'),r[0]['base'],dims,obs)
   with open(prefix+'-projected.txt') as f:
    m,bnorm=f.readline().split();m=int(m);bnorm=float(bnorm);H=np.loadtxt(f)
   rhs=np.zeros(m);rhs[0]=bnorm;eig=np.linalg.eigvalsh(H)
   zs=[]
   for i,v in enumerate(r):
    y=np.loadtxt(prefix+f'-r{i}-y.txt');z=np.loadtxt(prefix+f'-r{i}-z.txt');zs.append(z)
    v['audited_cost']=checked(pathlib.Path(prefix+f'-r{i}.state'),v['cost'],dims,obs)
    norm=np.linalg.norm(y);assert norm<=v['radius']*(1+1e-9)
    assert abs(np.linalg.norm(z)-v['norm'])<1e-8*max(1,v['norm'])
    assert np.linalg.norm(H@y+v['lambda']*y-rhs)/max(1,bnorm)<1e-8
    assert eig[0]+v['lambda']>=-1e-9*max(1,np.linalg.norm(H))
    assert abs(v['lambda']*(norm-v['radius']))<1e-8*max(1,bnorm*norm)
    assert v['gram']<1e-10 and v['kkt']<1e-8
    pred=rhs@y-.5*y@H@y
    assert abs(pred-v['reduced_prediction'])<1e-7*max(1,abs(pred))
    v['acceptable']=accepted(v);v['gain']=base-v['audited_cost']
   assert r[0]['reduced_prediction']<=r[1]['reduced_prediction']*(1+1e-9) and r[1]['reduced_prediction']<=r[2]['reduced_prediction']*(1+1e-9)
   considered=[1];selected=1 if accepted(r[1]) else None
   if selected is None:
    considered.append(0)
    if accepted(r[0]):selected=0
   elif r[1]['rho']>.75 and r[1]['norm']>=.8*r[1]['radius']:
    considered.append(2)
    if accepted(r[2]) and r[2]['cost']<r[1]['cost']:selected=2
   oracle=min((i for i in range(3) if accepted(r[i])),key=lambda i:r[i]['cost'],default=None)
   pairs=[]
   for i,j in itertools.combinations(range(3),2):
    pairs.append(dict(i=i,j=j,relative_distance=float(np.linalg.norm(zs[i]-zs[j])/max(np.linalg.norm(zs[i]),np.linalg.norm(zs[j]),1e-300)),cosine=float(np.dot(zs[i],zs[j])/max(np.linalg.norm(zs[i])*np.linalg.norm(zs[j]),1e-300))))
   baseline_gain=r[1]['gain'] if accepted(r[1]) else 0;gain=r[selected]['gain'] if selected is not None else 0
   work=lambda v:v['construct_seconds']+v['score_seconds']+v['model_seconds']
   rows.append(dict(scene=scene,width=job['width'],outer=outer,base=base,candidates=r,pairs=pairs,selected=selected,oracle=oracle,considered=considered,baseline_gain=baseline_gain,selective_gain=gain,extra_gain=gain-baseline_gain,estimated_current_seconds=r[1]['common_seconds']+work(r[1]),estimated_selective_seconds=r[1]['common_seconds']+sum(work(r[i]) for i in considered)))
 summary=dict(captures=len(rows),audits=audits,audit_max_relative_error=max(errors),instrumented_native_seconds=sum(native),instrumented_process_seconds=sum(wall),selected_counts={str(i):sum(r['selected']==i for r in rows) for i in [None,0,1,2]},extra_trials=sum(len(r['considered'])-1 for r in rows),current_rejected=sum(not r['candidates'][1]['acceptable'] for r in rows),oracle_counts={str(i):sum(r['oracle']==i for r in rows) for i in [None,0,1,2]},max_full_residual=max(v['full_residual'] for r in rows for v in r['candidates']),max_projected_kkt=max(v['kkt'] for r in rows for v in r['candidates']),rows=rows)
 (ROOT/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps({k:v for k,v in summary.items() if k!='rows'},indent=2))
 for r in rows:
  print(r['scene'],r['width'],r['outer'],'rhos',[round(v['rho'],3) for v in r['candidates']],'norm/R',[round(v['norm']/v['radius'],3) for v in r['candidates']],'gain',[round(v['gain'],2) for v in r['candidates']],'selected',r['selected'],'extra_gain',round(r['extra_gain'],2),'full_res',[round(v['full_residual'],5) for v in r['candidates']])
if __name__=='__main__':main()
