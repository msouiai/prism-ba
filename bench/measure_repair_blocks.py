#!/usr/bin/env python3
"""Independent camera/point/interaction diagnostics on accepted repaired steps."""
import pathlib,json,numpy as np,time
from audit_prism_state import observations
from local_curvature_model import FixedDirection
root=pathlib.Path('/workspace/prism-block-error');cache={};rows=[];out=root/'measurements';out.mkdir(exist_ok=True)
for p in sorted((root/'captures').glob('*.json')):
 result=out/p.name
 if result.exists():rows.append(json.loads(result.read_text()));continue
 start=time.monotonic();m=json.loads(p.read_text());scene=p.stem.rsplit('-',2)[0]
 if scene not in cache:cache[scene]=observations(pathlib.Path('/workspace/bal')/(scene+'.txt'))[1]
 d=FixedDirection(p.with_suffix(''),cache[scene]);res,_=d.residual(0,0);jc,jp=d.jacobian_directions()
 cpu=dict(gc=float(np.sum(res*jc,dtype=np.longdouble)),gp=float(np.sum(res*jp,dtype=np.longdouble)),cc=float(np.sum(jc*jc,dtype=np.longdouble)),cp=float(np.sum(jc*jp,dtype=np.longdouble)),pp=float(np.sum(jp*jp,dtype=np.longdouble)))
 coeff_errors={k:abs(cpu[k]-m[k])/max(1,abs(cpu[k])) for k in cpu};assert max(coeff_errors.values())<1e-7,(p,coeff_errors)
 values={f'{a}{b}':d.evaluate(a,b) for a,b in [(0,0),(1,0),(0,1),(1,1)]};F={k:v['cost'] for k,v in values.items()}
 state_errors={k:abs(F[k]-m[field])/max(1,abs(F[k])) for k,field in [('00','cost'),('10','camera_cost'),('01','point_cost'),('11','full_cost')]};assert max(state_errors.values())<1e-7,(p,state_errors)
 q_c=m['gc']+.5*m['cc'];q_p=m['gp']+.5*m['pp'];q_cross=m['cp'];q=q_c+q_p+q_cross
 E_c=F['10']-F['00']-q_c;E_p=F['01']-F['00']-q_p;E_cross=F['11']-F['10']-F['01']+F['00']-q_cross;E=F['11']-F['00']-q
 assert abs(E_c+E_p+E_cross-E)<1e-8*max(1,abs(E),abs(E_c),abs(E_p),abs(E_cross))
 ratios={}
 for name,actual,pred in [('camera',F['00']-F['10'],-q_c),('point',F['00']-F['01'],-q_p),('combined',F['00']-F['11'],-q),('camera_conditional',F['01']-F['11'],-q_c-q_cross),('point_conditional',F['10']-F['11'],-q_p-q_cross)]:
  ratios[name]=dict(actual=actual,prediction=pred,rho=actual/pred if pred>64*np.finfo(float).eps*max(1,F['00']) else None)
 scale=max(1,abs(q));row=dict(capture=p.stem,scene=scene,mode=m['mode'],outer=m['outer'],lambda_=m['lambda'],tau=m['tau'],coefficients=m,cpu_coefficient_errors=coeff_errors,cpu_state_errors=state_errors,costs=values,errors=dict(camera=E_c,point=E_p,interaction=E_cross,combined=E),normalized_errors=dict(camera=E_c/scale,point=E_p/scale,interaction=E_cross/scale,combined=E/scale),ratios=ratios,model_cancellation=(abs(q_c)+abs(q_p)+abs(q_cross))/scale,seconds=time.monotonic()-start)
 result.write_text(json.dumps(row,indent=2)+'\n');rows.append(row);print(p.stem,'errors/P',row['normalized_errors'],'rho',{k:v['rho'] for k,v in ratios.items()},flush=True)
(root/'measurements.json').write_text(json.dumps(rows,indent=2)+'\n')
