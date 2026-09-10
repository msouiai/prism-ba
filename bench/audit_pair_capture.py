#!/usr/bin/env python3
import pathlib,json,re,sys
import numpy as np
from cached_benchmark_input import load_input
from audit_prism_state import audit
from build_tr_candidate import sha
root=pathlib.Path('/workspace/prism-tr-safeguard/diagnostic');cap=root/'capture';out=root/'cpu-pair';out.mkdir();nc,np_,no=13682,4456117,28987644;dh,(dims,obs),initial=load_input(pathlib.Path('/workspace/bal/final-13682.txt'),'/workspace/prism-caspar-expanded/cpu-cache');rows=[]
for line in (root/'run.log').read_text().splitlines():
 if not line.startswith('PAIR_SAFE '):continue
 v={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)};prefix=cap/f'o{int(v["o"])}-sh{int(v["sh"])}'
 R=np.fromfile(str(prefix)+'.R',dtype='f8').reshape(nc,3,3);t=np.fromfile(str(prefix)+'.t',dtype='f8').reshape(nc,3);X=np.fromfile(str(prefix)+'.X',dtype='f8').reshape(np_,3);intr=np.fromfile(str(prefix)+'.intr',dtype='f8').reshape(3,nc)
 for kind in ['raw','safe']:
  step=np.fromfile(str(prefix)+'.'+kind,dtype='f8');dc=step[:9*nc].reshape(nc,9);dp=step[9*nc:].reshape(np_,3)
  w=dc[:,:3];theta=np.linalg.norm(w,axis=1);K=np.zeros((nc,3,3));K[:,0,1]=-w[:,2];K[:,0,2]=w[:,1];K[:,1,0]=w[:,2];K[:,1,2]=-w[:,0];K[:,2,0]=-w[:,1];K[:,2,1]=w[:,0]
  dR=np.eye(3)+np.sinc(theta/np.pi)[:,None,None]*K+(.5*np.sinc(theta/(2*np.pi))**2)[:,None,None]*(K@K)
  rr=dR@R;tt=t+dc[:,3:6];xx=X+dp;ii=intr+dc[:,6:9].T
  state=out/(prefix.name+'.'+kind+'.state')
  with state.open('wb') as f:
   f.write(b'PRISMS01');np.array([nc,np_,no],dtype='<u8').tofile(f)
   for a in [rr,tt,xx,ii]:np.ascontiguousarray(a,dtype='<f8').tofile(f)
  cost=audit(state,dims,obs);err=abs(cost-v[kind])/max(1,cost);assert err<1e-7
  row=dict(outer=int(v['o']),shift=int(v['sh']),kind=kind,cost=cost,gpu_cost=v[kind],relative_error=err,state_sha256=sha(state));rows.append(row);print(row,flush=True)
(out/'results.json').write_text(json.dumps(rows,indent=2))
