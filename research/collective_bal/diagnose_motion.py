"""Post-result first-step mechanism audit; does not change timing rows."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'; os.environ['OMP_NUM_THREADS']='1'
import json
import numpy as np
from paths import ROOT
from geometry import State, project, retract, dot
from collective import coarse_linearization, transform
from bridge_coarse import masks

results=json.loads((ROOT/'results.json').read_text())['rows']; rows=[]
for case in json.loads((ROOT/'frozen_cases.json').read_text())['cases']:
    a=np.load(ROOT/case['path']); s=State(*[a[k].copy() for k in ['R','t','X','intr']]); obs=a['observations']
    partition=np.load(ROOT/'evidence'/f"partition-{case['scene']}-{case['seed']}.npz");cg=partition['cg'];pg=partition['pg']
    r,_,K,bc,bp=coarse_linearization(s,obs,cg,pg); H=K.T@K;g=K.T@r.ravel()
    D=np.maximum(np.diag(H),max(1e-12,np.trace(H)/len(H)*1e-3));u=np.linalg.solve(H+1e-3*np.diag(D),-g)
    nonlinear=transform(s,cg,pg,u);linear=retract(s,(bc@u).reshape(len(s.R),6),(bp@u).reshape(len(s.X),3))
    rn,_=project(nonlinear,obs,6);rl,_=project(linear,obs,6);bridge=masks(obs,cg,pg)
    F=.5*dot(r,r);radius=np.sqrt(np.mean(np.sum((s.X-s.X.mean(0))**2,axis=1)))
    C=-np.einsum('nji,nj->ni',s.R,s.t); Cn=-np.einsum('nji,nj->ni',nonlinear.R,nonlinear.t)
    base=[x for x in results if x['scene']==case['scene'] and x['seed']==case['seed'] and x['arm']=='fine'][0]
    coarse=[x for x in results if x['scene']==case['scene'] and x['seed']==case['seed'] and x['arm']=='bridge8'][0]
    rows.append({'scene':case['scene'],'seed':case['seed'],
        'max_first_rotation_degrees':float(np.max(np.linalg.norm(u.reshape(-1,7)[:,:3],axis=1))*180/np.pi),
        'max_first_abs_log_scale':float(np.max(np.abs(u[6::7]))),
        'max_camera_motion_over_radius':float(np.max(np.linalg.norm(Cn-C,axis=1))/radius),
        'linear_vs_nonlinear_cost_difference_over_initial':float((.5*dot(rl,rl)-.5*dot(rn,rn))/F),
        'linear_internal_residual_change_norm':float(np.linalg.norm((rl-r)[~bridge])),
        'initial_internal_rms':float(np.sqrt(np.mean(r[~bridge]**2))),
        'ordinary_first_step_cost_reduction_fraction':float((F-base['fine']['trace'][1]['cost'])/F),
        'eight_coarse_steps_cost_reduction_fraction':float((F-coarse['coarse']['cost'])/F),
        'ordinary_fine_accepted':base['fine']['accepted'],'coarse_then_fine_accepted':coarse['fine']['accepted'],
        'first_fine_cost_with_coarse_over_without':float(coarse['fine']['trace'][1]['cost']/base['fine']['trace'][1]['cost'])})
(ROOT/'motion_diagnostics.json').write_text(json.dumps({'scope':'Post-result first-step diagnostic only; no selection or new timing.', 'rows':rows},indent=2,allow_nan=False)+'\n')
print(json.dumps(rows,indent=2))
