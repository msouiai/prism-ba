#!/usr/bin/env python3
"""Full-objective fixed-direction measurements; no online policy fitting."""
import argparse,json,pathlib,time,numpy as np
from audit_prism_state import observations
from local_curvature_model import FixedDirection,box_minimum
p=argparse.ArgumentParser();p.add_argument('root',type=pathlib.Path);p.add_argument('--scene');args=p.parse_args();root=args.root;out=root/'measurements';out.mkdir(exist_ok=True);cached={}
for meta in sorted((root/'captures').glob('*.json')):
 scene=meta.stem.rsplit('-',1)[0]
 if args.scene and scene!=args.scene:continue
 dest=out/meta.name
 if dest.exists():continue
 start=time.monotonic();print('MEASURE',meta.stem,flush=True);m=json.loads(meta.read_text())
 if scene not in cached:cached[scene]=observations(pathlib.Path('/workspace/bal')/(scene+'.txt'))[1]
 d=FixedDirection(meta.with_suffix(''),cached[scene]);base=d.evaluate(0,0);full=d.evaluate(1,1);F=base['cost']
 audits=dict(state=abs(F-m['cost'])/max(1,abs(F)),full=abs(full['cost']-m['full_cost'])/max(1,abs(full['cost'])))
 assert audits['state']<1e-7 and audits['full']<1e-6,audits
 g=np.array([m['gc'],m['gp']]);H=np.array([[m['cc'],m['cp']],[m['cp'],m['pp']]])
 r,_=d.residual(0,0);fd=[]
 for eps in [1e-6,1e-7]:
  u=(d.residual(eps,0)[0]-d.residual(-eps,0)[0])/(2*eps);v=(d.residual(0,eps)[0]-d.residual(0,-eps)[0])/(2*eps)
  values=np.array([np.sum(r*u,dtype=np.longdouble),np.sum(r*v,dtype=np.longdouble),np.sum(u*u,dtype=np.longdouble),np.sum(u*v,dtype=np.longdouble),np.sum(v*v,dtype=np.longdouble)],dtype=float)
  reference=np.array([m[k] for k in ['gc','gp','cc','cp','pp']]);error=np.max(np.abs(values-reference)/np.maximum(1,np.abs(reference)));fd.append(dict(epsilon=eps,max_error=float(error)))
 u,v=d.jacobian_directions()
 values=np.array([np.sum(r*u,dtype=np.longdouble),np.sum(r*v,dtype=np.longdouble),np.sum(u*u,dtype=np.longdouble),np.sum(u*v,dtype=np.longdouble),np.sum(v*v,dtype=np.longdouble)],dtype=float)
 analytic_error=float(np.max(np.abs(values-reference)/np.maximum(1,np.abs(reference))))
 assert analytic_error<1e-7,analytic_error
 del r,u,v
 uniform=[d.evaluate(2.**(-i),2.**(-i)) for i in range(1,11)]
 armijo=lambda z,c:bool(np.isfinite(c) and g@z<0 and c<F and c<=F+1e-4*(g@z))
 original=next((x for x in uniform[:8] if armijo(np.array([x['a'],x['b']]),x['cost'])),None)
 rows=[]
 for h in [.5,.125,.03125]:
  fa=d.evaluate(h,0)['cost'];fb=d.evaluate(0,h)['cost'];fab=d.evaluate(h,h)['cost']
  A=2*(fa-F-h*g[0])/h**2;C=2*(fb-F-h*g[1])/h**2;B=(fab-fa-fb+F)/h**2;sec=np.array([[A,B],[B,C]])
  z=box_minimum(g,sec,h);cost=d.evaluate(*z)['cost'];gs=float(g.sum());curv=float(sec.sum());t=float(np.clip(-gs/curv,0,h)) if curv>0 else (h if gs*h+.5*curv*h*h<0 else 0);zs=np.array([t,t]);cs=d.evaluate(t,t)['cost']
  zg=box_minimum(g,H,h);cg=d.evaluate(*zg)['cost'];validations=[]
  for uv in [(.25,.75),(.75,.25),(.25,.25),(.75,.75)]:
   x=h*np.array(uv);actual=d.evaluate(*x)['cost']-F;gn=float(g@x+.5*x@H@x);pred=float(g@x+.5*x@sec@x);den=max(1,abs(float(g@x)))
   validations.append(dict(a=float(x[0]),b=float(x[1]),actual=actual,gn=gn,secant=pred,gn_error=abs(gn-actual)/den,secant_error=abs(pred-actual)/den))
  E=max(0,full['cost']-F-float(g.sum()+.5*H.sum()));full_t=float(np.clip(-gs/(float(H.sum())+2*E),0,1)) if H.sum()+2*E>0 else 0
  scalar_full_cost=d.evaluate(full_t,full_t)['cost']
  rows.append(dict(radius=h,H_secant=sec.tolist(),min_eigenvalue=float(np.linalg.eigvalsh(sec)[0]),coupled=dict(a=float(z[0]),b=float(z[1]),cost=cost,gain=F-cost,armijo=armijo(z,cost)),scalar=dict(a=t,b=t,cost=cs,gain=F-cs,armijo=armijo(zs,cs)),gn=dict(a=float(zg[0]),b=float(zg[1]),cost=cg,gain=F-cg,armijo=armijo(zg,cg)),full_interpolation=dict(a=full_t,cost=scalar_full_cost,gain=F-scalar_full_cost),validation=validations))
 dz=d.RdX[:,2]
 with np.errstate(divide='ignore',invalid='ignore'):poles=-d.z0/dz
 poles=poles[(poles>0)&np.isfinite(poles)]
 result=dict(scene=scene,capture=m,cpu_audits=audits,finite_differences=fd,analytic_error=analytic_error,base=base,full=full,point_only_poles=dict(min_positive=float(poles.min()) if len(poles) else None,within_unit=int(np.sum(poles<=1))),original_rescue=original,models=rows,measurements=list(d.cache.values()),objective_evaluations=d.evals,seconds=time.monotonic()-start)
 dest.write_text(json.dumps(result,indent=2)+'\n');print('DONE',meta.stem,'evals',d.evals,'seconds',result['seconds'],'full_share',full['top10_cost_share'],flush=True)
