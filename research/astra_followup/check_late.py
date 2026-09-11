import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,importlib.util
import numpy as np
from paths import ROOT,GEOMETRY,COLLECTIVE,load_packed,write_json
from lm_checkpoints import solve
from reference_ba import valid_cost
from collective import clustered
from experiment import alignment_error

resume=[];positive=[]
for case in json.loads((GEOMETRY/'t4_real_targets.json').read_text()):
    initial,obs=load_packed(GEOMETRY/case['input']);ref=case['reference']['cost'];f0=valid_cost(initial,obs)
    for tau in [1e-3,1e-5]:
        target=ref+tau*(f0-ref);final,result,parents=solve(initial,obs,target,capture=[2,4,8])
        for k,p in parents.items():
            endpoint,tail,_=solve(p['state'],obs,target,lam=p['lambda'],known_cost=p['cost'])
            assert result['cost']==tail['cost'] and result['lambda']==tail['lambda']
            for name in ['R','t','X','intr']:assert np.array_equal(getattr(endpoint,name),getattr(final,name))
            resume.append({'scene':case['scene'],'tau':tau,'k':k,'full_state_and_lambda_exact':True})
spec=importlib.util.spec_from_file_location('bridge_late_check',COLLECTIVE/'bridge_coarse.py')
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
for seed in [220,221]:
    truth,s,obs,cg,pg,_,_=clustered(seed,bridges=4)
    before=s.copy();f0=valid_cost(s,obs)
    final,result=bridge.solve_bridge(s,obs,cg,pg,steps=8)
    assert result['cost']<f0 and np.isfinite(valid_cost(final,obs))
    for name in ['R','t','X','intr']:assert np.array_equal(getattr(s,name),getattr(before,name))
    positive.append({'seed':seed,'known_partition':True,'initial_cost':f0,'result':result,
        'initial_geometry':alignment_error(s,truth),'final_geometry':alignment_error(final,truth)})
write_json(ROOT/'late_checks.json',{'passed':True,'resume_checks':resume,'positive_controls':positive,
    'scope':'correctness controls; no new timing or late-trigger performance claim'})
print('late full-state resume and positive coarse controls: PASS')
