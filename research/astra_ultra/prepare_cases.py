import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,hashlib
import numpy as np
from paths import ROOT,GEOMETRY,load_packed,write_json
from cases import orbit_case
from lm_checkpoints import solve
from experiment import alignment_error
from reference_ba import valid_cost

rows=[];out=ROOT/'evidence';out.mkdir(exist_ok=True)
for family in ['depth','joint','low_parallax']:
    for seed in range(500,504):
        truth,initial,obs=orbit_case(seed,family)
        ref,stats,_=solve(truth,obs,-1,max_attempts=400,cap=3.)
        f0=valid_cost(initial,obs);fref=stats['cost']
        path=out/f'{family}-{seed}.npz'
        np.savez_compressed(path,R=initial.R,t=initial.t,X=initial.X,intr=initial.intr,observations=obs,
            truth_R=truth.R,truth_t=truth.t,truth_X=truth.X,ref_R=ref.R,ref_t=ref.t,ref_X=ref.X)
        rows.append({'id':f'{family}-{seed}','family':family,'seed':seed,'input':str(path.relative_to(ROOT)),
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'initial_cost':f0,'reference_cost':fref,
            'truth_cost':valid_cost(truth,obs),'target':1.01*fref,'deep_target':1.001*fref,
            'reference':stats,'reference_geometry':alignment_error(ref,truth),'initial_geometry':alignment_error(initial,truth)})
        print('reference',family,seed,'initial',f0,'reference',fref,'ref_steps',stats['accepted'],flush=True)
        write_json(ROOT/'cases.json',rows)
for old in json.loads((GEOMETRY/'t4_real_targets.json').read_text()):
    s,obs=load_packed(GEOMETRY/old['input']);f0=valid_cost(s,obs);fref=old['reference']['cost']
    path=GEOMETRY/old['input']
    rows.append({'id':old['scene'],'family':'bal','seed':None,'input':str(path.relative_to(ROOT.parent)),
        'input_from_research_root':True,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'initial_cost':f0,'reference_cost':fref,'target':fref+1e-3*(f0-fref),'deep_target':fref+1e-5*(f0-fref)})
write_json(ROOT/'cases.json',rows)
print('frozen',len(rows),'cases')
