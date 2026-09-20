#!/usr/bin/env python3
"""Check convex FW-gap bounds and retain an explicit indefinite counterexample."""
import numpy as np
from analyze_cg_capture import solve
rng=np.random.default_rng(109)
for _ in range(200):
 n=6;A=rng.normal(size=(n,n));H=A.T@A+.01*np.eye(n);b=rng.normal(size=n);R=float(rng.uniform(.1,3));x=rng.normal(size=n);x*=R*rng.uniform(0,1)/np.linalg.norm(x)
 y,_=solve(H,b,R);g=H@x-b;gap=g@x+R*np.linalg.norm(g);regret=.5*x@H@x-b@x-(.5*y@H@y-b@y)
 assert regret>=-1e-10 and regret<=gap+1e-10
H=np.diag([-1.,1.]);b=np.array([0.,1.]);x=np.array([0.,1.]);R=2.;g=H@x-b;gap=g@x+R*np.linalg.norm(g);y,_=solve(H,b,R)
regret=.5*x@H@x-b@x-(.5*y@H@y-b@y)
assert gap==0 and regret>1
print('200 convex bounds passed; indefinite counterexample retained:',dict(gap=gap,regret=regret))
