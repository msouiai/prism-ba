#!/usr/bin/env python3
"""Independent exhaustive separability and mixed-direction derivative checks."""
import itertools,json,pathlib,numpy as np
from local_curvature_model import FixedDirection
from audit_prism_state import observations
rng=np.random.default_rng(741);maxerr=0
for case in range(500):
 n=int(rng.integers(1,10));cost=rng.uniform(0,100,(2,n));exact=min(sum(cost[b,j] for j,b in enumerate(bits)) for bits in itertools.product([0,1],repeat=n));separable=np.min(cost,axis=0).sum();maxerr=max(maxerr,abs(exact-separable));assert abs(exact-separable)<1e-10
root=pathlib.Path('/workspace/prism-point-safeguard');capture=pathlib.Path('/workspace/prism-local-curvature/captures/venice-52-1');d=FixedDirection(capture,observations('/workspace/bal/venice-52.txt')[1]);r0,_=d.residual(0,0);jc,jp=d.jacobian_directions();track=[]
for b in [0,1]:
 r,_=d.residual(1,b);track.append(np.bincount(d.pi,weights=.5*np.sum(r*r,axis=1),minlength=d.np))
mask=(track[1]<=track[0]).astype(float);slope=float(np.sum(r0*(jc+jp*mask[d.pi,None])));checks=[]
for h in [1e-5,1e-6]:
 rp,_=d.residual(h,h*mask);rm,_=d.residual(-h,-h*mask);fd=float((np.sum(rp*rp,dtype=np.longdouble)-np.sum(rm*rm,dtype=np.longdouble))/(4*h));error=abs(fd-slope)/abs(slope);assert error<1e-6;checks.append(dict(h=h,slope=slope,fd=fd,error=error))
result=dict(exhaustive_cases=500,max_absolute_error=maxerr,mixed_derivatives=checks);(root/'math-tests.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
