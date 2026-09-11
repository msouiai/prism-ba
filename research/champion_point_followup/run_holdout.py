#!/usr/bin/env python3
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import pathlib,sys,json,hashlib,numpy as np
P=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(P.parent/'astra_ultra'))
from cases import orbit_case
from lm_checkpoints import solve as reference
from path_solver import solve
from paths import write_json,load_packed
from reference_ba import valid_cost
from geometry import State
from experiment import alignment_error

def main():
    out=P/'evidence/holdout';out.mkdir(parents=True,exist_ok=True)
    cases=[]
    for family in ['depth','joint','low_parallax']:
        for seed in range(510,516 if family=='low_parallax' else 513):
            truth,s,obs=orbit_case(seed,family);ref,stats,_=reference(truth,obs,-1,max_attempts=400,cap=3.)
            case=dict(id=f'{family}-{seed}',family=family,seed=seed,target=1.01*stats['cost'],initial_cost=valid_cost(s,obs),reference=stats)
            file=out/(case['id']+'.npz')
            np.savez_compressed(file,R=s.R,t=s.t,X=s.X,intr=s.intr,observations=obs,truth_R=truth.R,truth_t=truth.t,truth_X=truth.X)
            case.update(input=str(file.relative_to(P)),sha256=hashlib.sha256(file.read_bytes()).hexdigest());cases.append(case)
            print('frozen',case['id'],case['target'],flush=True)
    write_json(P/'holdout_cases.json',cases)
    rows=[];arms=['xyz','virtual_ray','observed_polish']
    for case in cases:
        file=P/case['input'];s,obs=load_packed(file);z=np.load(file);truth=State(z['truth_R'],z['truth_t'],z['truth_X'],s.intr)
        for rep in range(3):
            off=(case['seed']+rep)%3
            for arm in arms[off:]+arms[:off]:
                final,stats,_=solve(s,obs,case['target'],arm)
                rows.append(dict(id=case['id'],family=case['family'],rep=rep,arm=arm,target=case['target'],**stats,**alignment_error(final,truth)))
        write_json(P/'holdout_results.json',rows)
        print(case['id'],[(a,float(np.median([r['seconds'] for r in rows if r['id']==case['id'] and r['arm']==a])),sum(r['hit'] for r in rows if r['id']==case['id'] and r['arm']==a)) for a in arms],flush=True)
if __name__=='__main__':main()
