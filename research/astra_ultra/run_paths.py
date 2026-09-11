import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,numpy as np
from paths import ROOT,load_packed,write_json
from geometry import State
from path_solver import solve
from experiment import alignment_error

ARMS=['xyz','anchored','moving_host','virtual_ray','observed_polish']
rows=[]
cases=[r for r in json.loads((ROOT/'cases.json').read_text()) if r['family']!='bal']
for case in cases:
    s,obs=load_packed(ROOT/case['input']);z=np.load(ROOT/case['input'])
    truth=State(z['truth_R'],z['truth_t'],z['truth_X'],s.intr)
    for rep in range(3):
        offset=(case['seed']+rep)%len(ARMS)
        for arm in ARMS[offset:]+ARMS[:offset]:
            final,result,_=solve(s,obs,case['target'],arm)
            rows.append({'id':case['id'],'family':case['family'],'seed':case['seed'],'arm':arm,'rep':rep,
                'target':case['target'],**result,**alignment_error(final,truth)})
            if rep==0:
                np.savez_compressed(ROOT/'evidence'/f"path-{case['id']}-{arm}.npz",R=final.R,t=final.t,X=final.X,intr=final.intr)
    write_json(ROOT/'path_results.json',{'rows':rows})
    print(case['id'],[(a,[(r['hit'],r['accepted'],r['rejected']) for r in rows if r['id']==case['id'] and r['arm']==a][0]) for a in ARMS],flush=True)
summary=[]
for family in ['depth','joint','low_parallax']:
    for arm in ARMS:
        group=[r for r in rows if r['family']==family and r['arm']==arm];ratios={}
        for base in ARMS:
            pairs=[]
            for case in [c for c in cases if c['family']==family]:
                a=[r for r in group if r['id']==case['id']];b=[r for r in rows if r['id']==case['id'] and r['arm']==base]
                if all(r['hit'] for r in a+b):pairs.append(np.median([r['seconds'] for r in b])/np.median([r['seconds'] for r in a]))
            ratios[base]={'paired_cases':len(pairs),'median_speedup':np.median(pairs) if pairs else None}
        summary.append({'family':family,'arm':arm,'runs':len(group),'hits':sum(r['hit'] for r in group),'comparisons':ratios,
            **{k:np.median([r[k] for r in group]) for k in ['seconds','accepted','rejected','path_seconds','point_nrmse','camera_nrmse','rotation_median_deg','fallback_points']}})
write_json(ROOT/'path_summary.json',summary);print(summary,flush=True)
