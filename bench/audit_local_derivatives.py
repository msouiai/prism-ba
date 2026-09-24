#!/usr/bin/env python3
import pathlib,json,numpy as np
from audit_prism_state import observations
from local_curvature_model import FixedDirection
root=pathlib.Path('/workspace/prism-local-curvature');cached={};rows=[]
for p in sorted((root/'measurements').glob('*.json')):
 x=json.loads(p.read_text());scene=x['scene'];stem=root/'captures'/p.stem
 if scene not in cached:cached[scene]=observations(pathlib.Path('/workspace/bal')/(scene+'.txt'))[1]
 d=FixedDirection(stem,cached[scene]);r,_=d.residual(0,0);u,v=d.jacobian_directions()
 values=np.array([np.sum(r*u,dtype=np.longdouble),np.sum(r*v,dtype=np.longdouble),np.sum(u*u,dtype=np.longdouble),np.sum(u*v,dtype=np.longdouble),np.sum(v*v,dtype=np.longdouble)],dtype=float);m=x['capture'];ref=np.array([m[k] for k in ['gc','gp','cc','cp','pp']]);errors=np.abs(values-ref)/np.maximum(1,np.abs(ref));assert max(errors)<1e-7
 rows.append(dict(capture=p.stem,max_analytic_error=float(max(errors)),coefficient_errors=errors.tolist(),finite_differences=x['finite_differences']))
(root/'derivative-audits.json').write_text(json.dumps(rows,indent=2)+'\n');print('captures',len(rows),'max analytic error',max(x['max_analytic_error'] for x in rows))
