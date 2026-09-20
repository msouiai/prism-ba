#!/usr/bin/env python3
"""Diagnostic true projected Hessian via analytic-gradient central differences."""
import json,pathlib,numpy as np,time
from audit_prism_state import observations
from local_curvature_model import FixedDirection,box_minimum
root=pathlib.Path('/workspace/prism-local-curvature');obs={};out=[]
for p in sorted((root/'measurements').glob('*.json')):
 start=time.monotonic();x=json.loads(p.read_text());scene=x['scene'];m=x['capture'];print('HESSIAN',p.stem,flush=True)
 if scene not in obs:obs[scene]=observations(pathlib.Path('/workspace/bal')/(scene+'.txt'))[1]
 d=FixedDirection(root/'captures'/p.stem,obs[scene]);g=np.array([m['gc'],m['gp']]);GN=np.array([[m['cc'],m['cp']],[m['cp'],m['pp']]])
 def gradient(a,b):
  res,_=d.residual(a,b);u,v=d.jacobian_directions(a,b)
  return np.array([np.sum(res*u,dtype=np.longdouble),np.sum(res*v,dtype=np.longdouble)],dtype=float)
 hs=[]
 for eps in [1e-4,1e-5]:hs.append(np.column_stack(((gradient(eps,0)-gradient(-eps,0))/(2*eps),(gradient(0,eps)-gradient(0,-eps))/(2*eps))))
 scale=max(1,np.linalg.norm(hs[-1]));change=float(np.linalg.norm(hs[-1]-hs[0])/scale);asym=float(np.linalg.norm(hs[-1]-hs[-1].T)/scale)
 assert change<1e-4 and asym<1e-4,(p.stem,change,asym)
 H=(hs[-1]+hs[-1].T)/2;primary=next(z for z in x['models'] if z['radius']==.125);F=x['base']['cost'];err=[]
 for v in primary['validation']:
  z=np.array([v['a'],v['b']]);pred=float(g@z+.5*z@H@z);err.append(abs(pred-v['actual'])/max(1,abs(float(g@z))))
 candidate=box_minimum(g,H,.125);c=d.evaluate(*candidate)['cost']
 r0,_=d.residual(0,0);rf,_=d.residual(1,1);u,v=d.jacobian_directions();per=.5*np.sum(rf*rf-(r0+u+v)**2,axis=1);positive=np.maximum(per,0);top=np.partition(positive,-10)[-10:];share=float(np.sum(top,dtype=np.longdouble)/np.sum(positive,dtype=np.longdouble))
 row=dict(capture=p.stem,H_reference=H.tolist(),relative_epsilon_change=change,relative_asymmetry=asym,gn_hessian_error=float(np.linalg.norm(GN-H)/scale),secant_hessian_error=float(np.linalg.norm(np.array(primary['H_secant'])-H)/scale),median_reference_prediction_error=float(np.median(err)),min_eigenvalue=float(np.linalg.eigvalsh(H)[0]),reference_candidate=dict(a=float(candidate[0]),b=float(candidate[1]),cost=c,gain=F-c),full_positive_model_error_top10_share=share,seconds=time.monotonic()-start)
 out.append(row);(root/'hessian-reference.json').write_text(json.dumps(out,indent=2)+'\n');print('DONE',p.stem,'change',change,'top10',share,flush=True)
