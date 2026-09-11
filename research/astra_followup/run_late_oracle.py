import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,time,importlib.util
import numpy as np
from paths import ROOT,GEOMETRY,COLLECTIVE,write_json,load_packed
from lm_checkpoints import solve
from partition import automatic_partition
from collective import coarse_solve
from reference_ba import valid_cost

spec=importlib.util.spec_from_file_location('bridge_late',COLLECTIVE/'bridge_coarse.py')
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
ARMS=['continue','linear1','linear2','nonlinear1','nonlinear2']
rows=[];baselines=[]
for case in json.loads((GEOMETRY/'t4_real_targets.json').read_text()):
    initial,obs=load_packed(GEOMETRY/case['input']);F0=valid_cost(initial,obs);ref=case['reference']['cost']
    for tau in [1e-3,1e-5]:
        target=ref+tau*(F0-ref)
        _,baseline,checkpoints=solve(initial,obs,target,capture=[2,4,8])
        baselines.append({'scene':case['scene'],'tau':tau,'target':target,**baseline})
        print('baseline',case['scene'],tau,baseline['accepted'],baseline['hit'],flush=True)
        for k,c in checkpoints.items():
            if c['cost']<=target:continue
            np.savez_compressed(ROOT/'evidence'/f"late-{case['scene']}-{tau}-{k}.npz",R=c['state'].R,t=c['state'].t,
                X=c['state'].X,intr=c['state'].intr,observations=obs,lam=c['lambda'],parent_cost=c['cost'],
                prefix_seconds=c['prefix_seconds'],prefix_accepted=c['accepted'],prefix_rejected=c['rejected'])
            for rep in range(3):
                offset=(k+rep)%len(ARMS)
                for arm in ARMS[offset:]+ARMS[:offset]:
                    start=time.perf_counter();state=c['state'].copy();F=c['cost'];coarse=None;failure=None
                    partition_seconds=0.
                    if arm!='continue':
                        try:
                            ts=time.perf_counter();cg,pg=automatic_partition(state,obs,confidence=True)
                            partition_seconds=time.perf_counter()-ts
                            if arm.startswith('nonlinear'):
                                state,coarse=bridge.solve_bridge(state,obs,cg,pg,steps=int(arm[-1]),target=target,deadline=start+3.)
                            else:
                                state,coarse=coarse_solve(state,obs,cg,pg,nonlinear=False,steps=int(arm[-1]),target=target,deadline=start+3.)
                            F=coarse['cost']
                        except np.linalg.LinAlgError as e:failure=str(e);state=c['state'].copy();F=c['cost']
                    intervention_seconds=time.perf_counter()-start
                    _,tail,_=solve(state,obs,target,lam=c['lambda'],known_cost=F,cap=max(0.,3.-intervention_seconds))
                    elapsed=time.perf_counter()-start
                    if arm=='continue':
                        assert tail['cost']==baseline['cost'],(case['scene'],tau,k,tail['cost'],baseline['cost'])
                        assert tail['accepted']+k==baseline['accepted']
                    rows.append({'scene':case['scene'],'tau':tau,'target':target,'k':k,'rep':rep,'arm':arm,
                        'prefix_seconds':c['prefix_seconds'],'parent_cost':c['cost'],'saved_lambda':c['lambda'],
                        'seconds':c['prefix_seconds']+elapsed,'tail_seconds':elapsed,'hit':tail['hit'],
                        'partition_seconds':partition_seconds,'intervention_seconds':intervention_seconds,
                        'total_fine_accepted':k+tail['accepted'],'fine_saved':baseline['accepted']-k-tail['accepted'],
                        'coarse':coarse,'failure':failure,'tail':tail})
            write_json(ROOT/'late_oracle.json',{'baselines':baselines,'rows':rows})
        print('done',case['scene'],tau,flush=True)
summary=[]
for sc,tau in sorted(set((r['scene'],r['tau']) for r in rows)):
    choices=[]
    for k,arm in sorted(set((r['k'],r['arm']) for r in rows if r['scene']==sc and r['tau']==tau)):
        a=[r for r in rows if r['scene']==sc and r['tau']==tau and r['k']==k and r['arm']==arm]
        b=[r for r in rows if r['scene']==sc and r['tau']==tau and r['k']==k and r['arm']=='continue']
        choices.append({'k':k,'arm':arm,'hits':sum(r['hit'] for r in a),'runs':len(a),
            'full_speedup':np.median([r['seconds'] for r in b])/np.median([r['seconds'] for r in a]) if all(r['hit'] for r in a+b) else None,
            'tail_speedup':np.median([r['tail_seconds'] for r in b])/np.median([r['tail_seconds'] for r in a]) if all(r['hit'] for r in a+b) else None,
            'fine_saved':np.median([r['fine_saved'] for r in a])})
    nl=[c for c in choices if c['arm'].startswith('nonlinear') and c['full_speedup'] is not None]
    summary.append({'scene':sc,'tau':tau,'choices':choices,'nonlinear_hindsight_best':max(nl,key=lambda c:c['full_speedup']) if nl else None})
write_json(ROOT/'late_summary.json',summary);print(json.dumps(summary,indent=2,default=float))
