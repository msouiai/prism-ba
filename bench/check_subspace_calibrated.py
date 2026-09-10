#!/usr/bin/env python3
"""Independent subgradient KKT verification of calibrated piecewise quadratic."""
import json,pathlib,subprocess,numpy as np
root=pathlib.Path('/workspace/prism-subspace-rescue');rng=np.random.default_rng(932);cases=[]
for i in range(2000):
 J=rng.normal(size=(8,2));r=rng.normal(size=8)*3
 if i%7==0:J[:,1]=J[:,0]*(1 if i%2 else -1)
 if i%11==0:J[:,0]=0
 if i%13==0:J[:,1]=0
 H=J.T@J;g=J.T@r;E=10.**rng.uniform(-5,5);scale=10.**rng.uniform(-100,100);cases.append((g*scale,H*scale,E*scale))
cases += [(np.array([-1.,-2.]),np.zeros((2,2)),1.),(np.zeros(2),np.zeros((2,2)),1.)]
s=''.join(' '.join(map(str,[g[0],g[1],H[0,0],H[0,1],H[1,1],E]))+'\n' for g,H,E in cases)
lines=subprocess.check_output([str(root/'test_calibrated')],input=s,text=True).splitlines();worst=0;wins=0
for (g,H,E),line in zip(cases,lines):
 a,b,p,valid,t,u,sp,sv=map(float,line.split());x=np.array([a,b]);scale=max(np.max(np.abs(g)),np.max(np.abs(H)),E,1e-300);g=g/scale;H=H/scale;E=E/scale
 grad=g+H@x;v=2*E*max(x)
 if abs(a-b)<=1e-12 and v>0:theta=[0,1,np.clip(-grad[0]/v,0,1),np.clip(1+grad[1]/v,0,1)]
 else:theta=[1 if a>b else 0]
 res=min(np.max(np.abs(x-np.clip(x-grad-v*np.array([z,1-z]),0,1))) for z in theta)
 worst=max(worst,res);assert res<1e-8,(x,grad,res)
 q=lambda z:g@z+.5*z@H@z+E*max(z)**2
 assert q(x)<=q(np.array([t,u]))+1e-10
 if q(x)<q(np.array([t,u]))-1e-5:wins+=1
 for z in rng.uniform(size=(20,2)):assert q(x)<=q(z)+1e-10
 assert not valid or (p>0 and g@x<0)
assert len(lines)==len(cases)
# Nonlinear counterexample: exact GN box minimizer fails; smaller step succeeds.
f=lambda a,b:.5*((1-a+10*a*a)**2+(1-b)**2)
assert f(1,1)>f(0,0) and f(.125,.125)<f(0,0)
out=dict(cases=len(cases),max_projected_subgradient_kkt_residual=worst,coupled_strict_model_wins=wins,random_feasible_checks=20*len(cases),nonlinear_counterexample='pass',seed=932)
(root/'calibrated-tests.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
