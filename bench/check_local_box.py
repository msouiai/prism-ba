#!/usr/bin/env python3
import numpy as np,json,pathlib
from local_curvature_model import box_minimum
rng=np.random.default_rng(940);maxerr=0;indef=0
for i in range(2000):
 g=rng.normal(size=2);H=rng.normal(size=(2,2));H=(H+H.T)/2
 if i%7==0:H[:]=0
 if i%11==0:H=np.outer(g,g)
 if np.linalg.eigvalsh(H)[0]<0:indef+=1
 h=10.**rng.uniform(-3,0);x=box_minimum(g,H,h);q=lambda z:z@g+.5*np.einsum('...i,ij,...j->...',z,H,z)
 axis=np.linspace(0,h,51);grid=np.stack(np.meshgrid(axis,axis),axis=-1).reshape(-1,2);err=q(x)-q(grid).min();assert err<1e-10
 # Necessary box KKT condition, plus independent complete dense-grid comparison.
 residual=np.max(np.abs(x-np.clip(x-(g+H@x),0,h)));maxerr=max(maxerr,residual);assert residual<1e-10
out=dict(cases=2000,indefinite_cases=indef,max_kkt_residual=maxerr,grid_points=2000*51*51,seed=940)
pathlib.Path('/workspace/prism-local-curvature/box-tests.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
