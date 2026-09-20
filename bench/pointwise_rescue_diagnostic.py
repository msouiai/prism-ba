#!/usr/bin/env python3
"""Exact track-cost menu minimization at fixed cameras; original step retained."""
import pathlib,json,numpy as np,time
from audit_prism_state import observations
from local_curvature_model import FixedDirection
root=pathlib.Path('/workspace/prism-local-curvature');out=root/'pointwise';out.mkdir(exist_ok=True);obs={};results=[]
for p in sorted((root/'measurements').glob('*.json')):
 x=json.loads(p.read_text());scene=x['scene'];start=time.monotonic()
 if not x['original_rescue']:continue
 print('POINTWISE',p.stem,flush=True)
 if scene not in obs:obs[scene]=observations(pathlib.Path('/workspace/bal')/(scene+'.txt'))[1]
 d=FixedDirection(root/'captures'/p.stem,obs[scene]);alpha=x['original_rescue']['a'];base=x['original_rescue']['cost'];F=x['base']['cost'];m=x['capture']
 r0,_=d.residual(0,0);u,v=d.jacobian_directions();pointg=np.bincount(d.pi,weights=np.sum(r0*v,axis=1),minlength=d.np);assert abs(pointg.sum()-m['gp'])/max(1,abs(m['gp']))<1e-7
 rf,_=d.residual(1,1);error=np.maximum(.5*np.sum(rf*rf-(r0+u+v)**2,axis=1),0);ids=np.argpartition(error,-10)[-10:];pointids=np.unique(d.pi[ids]);tracks=np.bincount(d.pi,minlength=d.np)
 menu=np.array(sorted(set([0.,alpha/2,alpha,.5,1.])));best=dict(camera=alpha,cost=base,gain=F-base,armijo=True,changed_points=0,source='original');bestscale=np.full(d.np,alpha);candidates=[]
 for a in sorted(set([alpha,1.])):
  trackcost=[]
  for b in menu:
   res,_=d.residual(a,b);per=.5*np.sum(res*res,axis=1);trackcost.append(np.bincount(d.pi,weights=per,minlength=d.np))
  trackcost=np.array(trackcost);choice=np.argmin(trackcost,axis=0);scales=menu[choice];cost=float(np.sum(trackcost[choice,np.arange(d.np)],dtype=np.longdouble));slope=float(a*m['gc']+pointg@scales);armijo=bool(cost<F and slope<0 and cost<=F+1e-4*slope)
  check,_=d.residual(a,scales);checked=float(.5*np.sum(check*check,dtype=np.longdouble));rel=abs(cost-checked)/max(1,abs(checked));assert rel<1e-9
  # Original uniform point scale belongs to the same-camera menu.
  uniform=d.evaluate(a,alpha)['cost'];assert cost<=uniform+1e-8*max(1,abs(uniform))
  c=dict(camera=a,cost=checked,gain=F-checked,armijo=armijo,slope=slope,changed_points=int(np.sum((scales!=alpha)&(tracks>0))),reconstruction_error=rel,source='pointwise');candidates.append(c)
  if armijo and checked<best['cost']:best=c;bestscale=scales.copy()
 assert best['cost']<=base+1e-8*max(1,base)
 np.save(out/(p.stem+'-scales.npy'),bestscale)
 row=dict(capture=p.stem,scene=scene,original_alpha=alpha,original_gain=F-base,point_menu=menu.tolist(),candidates=candidates,best=best,gain_ratio=best['gain']/(F-base),top10_error_distinct_points=len(pointids),top10_error_point_ids=pointids.tolist(),top10_error_track_lengths=tracks[pointids].tolist(),full_cost_passes=len(menu)*len(set([alpha,1.])),seconds=time.monotonic()-start)
 results.append(row);(root/'pointwise-results.json').write_text(json.dumps(results,indent=2)+'\n');print('DONE',p.stem,'gain ratio',row['gain_ratio'],'error points',len(pointids),flush=True)
