"""Post-screen explanation; these diagnostics do not select a new policy."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import numpy as np
from paths import ROOT,write_json
from reference_ba import synthetic,valid_cost,Linearization
from depth_smoothing import parallax_case
from geometry import exp_so3,project,retract
from experiment import alignment_error
from lm_checkpoints import solve
from projective_paths import chart_vectors,projective_retract

truth,initial,obs=synthetic(200,'depth')
Q=exp_so3(np.array([[.1,.2,-.1]]))[0];u=np.array([1.,2.,3.]);scale=.7
s=truth.copy();s.X=scale*s.X@Q.T+u;s.R=s.R@Q.T;s.t=scale*s.t-np.einsum('nij,j->ni',s.R,u)
checks={'truth_identity':alignment_error(truth,truth),'global_similarity':alignment_error(s,truth),
    'projection_difference':float(np.max(np.abs(project(s,obs)[0]-project(truth,obs)[0]))),
    'initial_geometry':alignment_error(initial,truth)}
assert checks['global_similarity']['camera_nrmse']<1e-12
assert checks['global_similarity']['point_nrmse']<1e-12
write_json(ROOT/'geometry_alignment_checks.json',checks)

rows=[]
for family in ['low_parallax','moderate_parallax','rotation']:
    for seed in [200,205]:
        truth,initial,obs=synthetic(seed,'rotation') if family=='rotation' else parallax_case(seed,.08 if family=='low_parallax' else 1.)
        _,_,parents=solve(initial,obs,-1,capture=[2,4],max_attempts=12)
        parents[0]={'state':initial,'lambda':.1}
        for k,p in sorted(parents.items()):
            s=p['state'];lin=Linearization(s,obs);dc,dp=lin.factor(p['lambda']).solve()
            for arm in ['xyz','anchored','mean_view']:
                v=None if arm=='xyz' else chart_vectors(s,lin,arm)
                for motion in ['points_only','joint']:
                    dcam=dc if motion=='joint' else np.zeros_like(dc)
                    if arm=='xyz': trial=retract(s,dcam,dp);count=0
                    else:trial,count=projective_retract(s,dcam,dp,v)
                    jd=lin.jd(dcam,dp);rt,qt=project(trial,obs,6)
                    defect=np.linalg.norm(rt-lin.r-jd)/max(np.linalg.norm(jd),1e-30)
                    rows.append({'family':family,'seed':seed,'k':k,'lambda':p['lambda'],'arm':arm,
                        'motion':motion,'relative_defect':defect,'valid':np.all(qt[:,2]<-1e-8),
                        'fallback_points':count,'parent_cost':valid_cost(s,obs),'trial_cost':valid_cost(trial,obs)})
write_json(ROOT/'chart_defects.json',{'posthoc_diagnostic':True,'rows':rows})
for family in ['low_parallax','moderate_parallax','rotation']:
    for motion in ['points_only','joint']:
        print(family,motion,{a:float(np.median([r['relative_defect'] for r in rows if r['family']==family and r['motion']==motion and r['arm']==a])) for a in ['xyz','anchored','mean_view']})
