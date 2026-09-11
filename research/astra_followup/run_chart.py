import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import numpy as np
from paths import ROOT,write_json
from reference_ba import synthetic,valid_cost
from depth_smoothing import parallax_case
from experiment import alignment_error
from projective_paths import solve

ARMS=['xyz','anchored','mean_view'];cases=[]
for family in ['low_parallax','moderate_parallax','rotation']:
    for seed in range(200,210):
        truth,initial,obs=synthetic(seed,'rotation') if family=='rotation' else parallax_case(seed,.08 if family=='low_parallax' else 1.)
        F0=valid_cost(initial,obs);ref=valid_cost(truth,obs);target=ref+1e-4*(F0-ref)
        cases.append((family,seed,truth,initial,obs,F0,ref,target))
write_json(ROOT/'chart_targets.json',[{'family':f,'seed':s,'initial_cost':f0,'reference':ref,'target':t}
    for f,s,_,_,_,f0,ref,t in cases])
# A common warm-up is excluded from timed comparisons.
solve(cases[0][3],cases[0][4],-1,'xyz',max_attempts=2)
rows=[]
for family,seed,truth,initial,obs,F0,ref,target in cases:
    for rep in range(3):
        offset=(seed+rep)%3
        for arm in ARMS[offset:]+ARMS[:offset]:
            final,result=solve(initial,obs,target,arm)
            error=alignment_error(final,truth)
            failure=error['point_nrmse']>.2 or error['camera_nrmse']>.2 or error['rotation_median_deg']>5
            rows.append({'family':family,'seed':seed,'rep':rep,'arm':arm,'target':target,
                **result,**error,'geometry_failure':failure})
            if rep==0:
                np.savez_compressed(ROOT/'evidence'/f'chart-{family}-{seed}-{arm}.npz',
                    R=final.R,t=final.t,X=final.X,intr=final.intr)
    write_json(ROOT/'chart_results.json',{'rows':rows})
    print(family,seed,[(a,[(r['accepted'],r['rejected'],r['hit']) for r in rows if r['family']==family and r['seed']==seed and r['arm']==a][:1]) for a in ARMS],flush=True)
summary=[]
for family in ['low_parallax','moderate_parallax','rotation']:
    for arm in ARMS:
        group=[r for r in rows if r['family']==family and r['arm']==arm]
        speed=[];vs_anchor=[]
        for seed in range(200,210):
            a=[r for r in group if r['seed']==seed]
            for base,out in [('xyz',speed),('anchored',vs_anchor)]:
                b=[r for r in rows if r['family']==family and r['seed']==seed and r['arm']==base]
                if all(r['hit'] for r in a+b):out.append(np.median([r['seconds'] for r in b])/np.median([r['seconds'] for r in a]))
        summary.append({'family':family,'arm':arm,'runs':len(group),'hits':sum(r['hit'] for r in group),
            'geometry_failures':sum(r['geometry_failure'] for r in group),'paired_scenes':len(speed),
            'speedup_vs_xyz':np.median(speed) if speed else None,'speedup_vs_anchor':np.median(vs_anchor) if vs_anchor else None,
            **{k:np.median([r[k] for r in group]) for k in ['seconds','accepted','rejected','point_nrmse','camera_nrmse','rotation_median_deg','fallback_points','feature_seconds']}})
write_json(ROOT/'chart_summary.json',summary)
print(summary,flush=True)
