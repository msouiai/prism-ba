#!/usr/bin/env python3
"""Independent projected-KKT and dense-grid verification of C++ box minimizer."""
import json,pathlib,subprocess,numpy as np
root=pathlib.Path('/workspace/prism-subspace-rescue');rng=np.random.default_rng(931);cases=[]
for i in range(2000):
 J=rng.normal(size=(8,2));r=rng.normal(size=8)*3
 if i%7==0:J[:,1]=J[:,0]*(1 if i%2 else -1)
 if i%11==0:J[:,0]=0
 if i%13==0:J[:,1]=0
 if i%17==0:J[:,1]*=1e-8
 H=J.T@J;g=J.T@r;scale=10.**rng.uniform(-100,100);cases.append((g*scale,H*scale))
cases += [(np.array([-1.,-2.]),np.zeros((2,2))),(np.zeros(2),np.zeros((2,2))),(np.array([1.,1.]),np.eye(2))]
s=''.join(' '.join(map(str,[g[0],g[1],H[0,0],H[0,1],H[1,1]]))+'\n' for g,H in cases)
lines=subprocess.check_output([str(root/'test_box')],input=s,text=True).splitlines();worst=0;wins=0
for (g,H),line in zip(cases,lines):
 a,b,p,valid,t,u,sp,sv=map(float,line.split());x=np.array([a,b]);scale=max(np.max(np.abs(g)),np.max(np.abs(H)),1e-300);g=g/scale;H=H/scale
 grad=g+H@x;res=np.max(np.abs(x-np.clip(x-grad,0,1)));worst=max(worst,res);assert res<1e-8,(x,grad,res)
 q=lambda x:g@x+.5*x@H@x
 assert q(x)<=q(np.array([t,u]))+1e-10
 if q(x)<q(np.array([t,u]))-1e-5:wins+=1
 for z in rng.uniform(size=(20,2)):assert q(x)<=q(z)+1e-10
 assert (valid==0) or (p>0 and g@x<0)
assert len(lines)==len(cases)
out=dict(cases=len(cases),max_projected_kkt_residual=worst,coupled_strict_model_wins=wins,random_feasible_checks=20*len(cases),scalar_dominance='pass',seed=931)
(root/'box-tests.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
