"""Frozen-parent defect audit; no policy selection or timing claims."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,numpy as np
from paths import ROOT,load_packed,write_json
from reference_ba import Linearization,valid_cost
from geometry import project,dot
from lm_checkpoints import solve
from joint_paths import candidate

rows=[]
for case in json.loads((ROOT/'cases.json').read_text()):
    if case['family']=='bal':continue
    initial,obs=load_packed(ROOT/case['input'])
    _,_,parents=solve(initial,obs,case['target'],capture=[2,4]);parents[0]={'state':initial,'lambda':.1}
    for k,p in sorted(parents.items()):
        s=p['state'];lam=p['lambda'];lin=Linearization(s,obs);dc,dp=lin.factor(lam).solve()
        for motion in ['joint','point_only']:
            camera=dc if motion=='joint' else np.zeros_like(dc)
            jd=lin.jd(camera,dp);pred=-dot(lin.r,jd)-.5*dot(jd,jd);f0=valid_cost(s,obs)
            baseline,_=candidate(s,lin,camera,dp,lam,'xyz')
            rt,qt,_,jp,_,_=project(baseline,obs,6,True)
            defect=rt-lin.r-jd
            # Fixed-trial-camera linear point subspace can explain only this part.
            jp[lin.pi==0]=0
            H=np.zeros((lin.np,3,3));g=np.zeros((lin.np,3))
            np.add.at(H,lin.pi,np.einsum('nki,nkj->nij',jp,jp))
            np.add.at(g,lin.pi,np.einsum('nki,nk->ni',jp,defect))
            delta=np.einsum('nij,nj->ni',np.linalg.pinv(H,hermitian=True,rcond=1e-10),g)
            proj=np.einsum('nki,ni->nk',jp,delta[lin.pi])
            explain=dot(proj,proj)/max(dot(defect,defect),1e-30)
            assert explain<1+1e-7
            for arm in ['xyz','anchored','moving_host','virtual_ray','observed_polish','virtual_ray_mu0']:
                trial,meta=candidate(s,lin,camera,dp,lam,'virtual_ray' if arm=='virtual_ray_mu0' else arm,oracle=arm=='virtual_ray_mu0')
                rr,qq=project(trial,obs,6)
                # Common original solved-tangent target for model fidelity, even
                # for observed-polish (which intentionally targets measured pixels).
                e=rr-lin.r-jd
                rows.append({'id':case['id'],'family':case['family'],'k':k,'motion':motion,'arm':arm,
                    'relative_defect':np.linalg.norm(e)/max(np.linalg.norm(jd),1e-30),
                    'valid':np.all(qq[:,2]<-1e-8) and np.isfinite(rr).all(),'cost':valid_cost(trial,obs),
                    'rho_against_original_tangent':(f0-valid_cost(trial,obs))/pred if pred>0 else None,
                    'baseline_defect_fraction_in_fixed_camera_point_space':explain,**meta})
summary=[]
for family in ['depth','joint','low_parallax']:
    for motion in ['joint','point_only']:
        for arm in ['xyz','anchored','moving_host','virtual_ray','observed_polish','virtual_ray_mu0']:
            a=[r for r in rows if r['family']==family and r['motion']==motion and r['arm']==arm]
            summary.append({'family':family,'motion':motion,'arm':arm,'parents':len(a),
                'median_defect':np.median([r['relative_defect'] for r in a]),'valid':sum(r['valid'] for r in a),
                'median_explainable_fraction':np.median([r['baseline_defect_fraction_in_fixed_camera_point_space'] for r in a]),
                'fallback_points':sum(r['fallback_points'] for r in a)})
write_json(ROOT/'ray_diagnostics.json',{'scope':'frozen-parent diagnostic, not additional tuning arms','rows':rows,'summary':summary})
print('ray diagnostics',len(rows),'candidate evaluations',flush=True)
