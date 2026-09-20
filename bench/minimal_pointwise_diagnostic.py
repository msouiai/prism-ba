#!/usr/bin/env python3
import pathlib,json,time,numpy as np
from audit_prism_state import observations
from local_curvature_model import FixedDirection
root=pathlib.Path('/workspace/prism-local-curvature');obs={};rows=[]
for p in sorted((root/'measurements').glob('*.json')):
 x=json.loads(p.read_text());scene=x['scene'];start=time.monotonic()
 if scene not in obs:obs[scene]=observations(pathlib.Path('/workspace/bal')/(scene+'.txt'))[1]
 d=FixedDirection(root/'captures'/p.stem,obs[scene]);m=x['capture'];F=x['base']['cost'];baseline=x['original_rescue']['cost'];r0,_=d.residual(0,0);u,v=d.jacobian_directions();pg=np.bincount(d.pi,weights=np.sum(r0*v,axis=1),minlength=d.np);costs={}
 for b in [0.,.5,1.]:
  res,_=d.residual(1,b);costs[b]=np.bincount(d.pi,weights=.5*np.sum(res*res,axis=1),minlength=d.np)
 result=[]
 for menu in [[0.,1.],[0.,.5,1.]]:
  a=np.array([costs[b] for b in menu]);scales=np.array(menu)[np.argmin(a,axis=0)];raw=float(np.sum(np.min(a,axis=0),dtype=np.longdouble));slope=float(m['gc']+pg@scales);valid=bool(raw<F and slope<0 and raw<=F+1e-4*slope)
  res,_=d.residual(1,scales);checked=float(.5*np.sum(res*res,dtype=np.longdouble));error=abs(raw-checked)/max(1,abs(checked));assert error<1e-9
  chosen=valid and checked<baseline;final=checked if chosen else baseline
  result.append(dict(menu=menu,raw_cost=checked,armijo=valid,chosen=chosen,gain=F-final,gain_ratio=(F-final)/(F-baseline),points_below_full=int(np.sum(scales<1)),reconstruction_error=error))
 rows.append(dict(capture=p.stem,variants=result,seconds=time.monotonic()-start));(root/'minimal-pointwise-results.json').write_text(json.dumps(rows,indent=2)+'\n');print(p.stem,[(v['gain_ratio'],v['chosen']) for v in result],flush=True)
