#!/usr/bin/env python3
"""Frozen complete-solve follow-up conditional on the pilot's learning gate."""
import json, pathlib, statistics, subprocess, os
import numpy as np
from rl_damping_pilot import ROOT,BIN,run,put,sha,native_spent

SCENES={
 'trafalgar-126':dict(target=104534.24152926281*1.01,cap=4),
 'final-1936':dict(target=5074937.9725361075*1.01,cap=8),
 'muell-gba146':dict(target=1946488.746262194,cap=12),
}

def policy_parity():
    source=ROOT/'policy_parity.cc'
    source.write_text('#include "rl_damping.h"\n#include <iostream>\nint main(){PrismRLDamping p;while(std::cin>>p.history[0]){for(int j=1;j<p.NX;++j)std::cin>>p.history[j];std::cout<<p.Action(1)<<"\\n";}}\n')
    subprocess.run(['g++','-O2','-std=c++17','-I'+str(ROOT/'build-v2/headers'),str(source),'-o',str(ROOT/'policy-parity')],check=True)
    d=json.loads((ROOT/'analysis.json').read_text());X=np.array([c['features'] for c in d['cells']])
    text=(ROOT/'policy.txt').read_text().split();assert text[:2]==['PRISM_RLD_LINEAR_V1','64']
    nums=np.array(list(map(float,text[2:])));mean=nums[:64];sd=nums[64:128];W=nums[128:].reshape(3,65)
    pred=np.c_[np.clip((X-mean)/sd,-5,5),np.ones(len(X))]@W.T
    expected=[max([1,0,2],key=lambda j:pred[i,j])-1 for i in range(len(X))]
    env=os.environ.copy();env['OCA_RLD_POLICY']=str(ROOT/'policy.txt')
    result=subprocess.run([str(ROOT/'policy-parity')],input='\n'.join(' '.join(map(repr,row.tolist())) for row in X),text=True,capture_output=True,env=env,check=True)
    actual=list(map(int,result.stdout.split()));assert actual==expected,(actual,expected)
    put(ROOT/'policy-parity.json',dict(passed=True,states=len(X),actions=actual,policy_sha256=sha(ROOT/'policy.txt')))

def main():
    a=json.loads((ROOT/'analysis.json').read_text());assert a['model']['validation_gate']
    policy_parity()
    # A deterministic CG-cap rule expressed in the same inference code.
    W=np.zeros((3,65));W[2,7]=1.;W[2,-1]=-.99
    rule=ROOT/'work-rule.txt'
    rule.write_text('PRISM_RLD_LINEAR_V1 64\n'+' '.join(map(repr,([0.]*64+[1.]*64+W.flatten().tolist())))+'\n')
    policies={'baseline':None,'learned':ROOT/'policy.txt','work-rule':rule}
    protocol=dict(scenes=SCENES,repeats=3,initial_lambda=.1,arms=list(policies),binary_sha256=sha(BIN),
        policy_sha256={k:sha(v) for k,v in policies.items() if v},
        scope='Frozen final transfer check; telemetry disabled, inference and features timed. Same-binary baseline has no controller overhead. No training on these scenes. Previously seen research scenes, not pristine held-out recordings.')
    pp=ROOT/'validation-protocol.json'
    if pp.exists():assert json.loads(pp.read_text())==protocol
    else:put(pp,protocol)
    rows=[]
    for rep in range(3):
        for si,(scene,spec) in enumerate(SCENES.items()):
            names=list(policies);offset=(rep+si)%len(names);names=names[offset:]+names[:offset]
            for arm in names:
                flags=dict(OCA_TARGET_COST=spec['target'],OCA_MAX_SECONDS=spec['cap'])
                if policies[arm]:flags['OCA_RLD_POLICY']=policies[arm]
                row=run(f'validation-{scene}-{arm}-{rep}',scene,flags,iterations=600,logging=False)
                rows.append(dict(scene=scene,arm=arm,rep=rep,target=spec['target'],
                    hit='target_seconds' in row and row['audit_cost']<=spec['target'],
                    **{k:row.get(k) for k in ['target_seconds','seconds','audit_cost','outers','rejects','matvecs','audit_error']}))
                put(ROOT/'validation-rows.json',rows)
    summary={}
    for scene in SCENES:
        summary[scene]={}
        for arm in policies:
            rs=[r for r in rows if r['scene']==scene and r['arm']==arm]
            summary[scene][arm]={'hits':sum(r['hit'] for r in rs)}
            for key in ['target_seconds','seconds','audit_cost','outers','rejects','matvecs']:
                vals=[r[key] for r in rs if r[key] is not None]
                if vals:summary[scene][arm][key]=dict(median=statistics.median(vals),min=min(vals),max=max(vals))
    ratios=[];hits_ok=True
    for scene,arms in summary.items():
        b,p=arms['baseline'],arms['learned']
        if b['hits']==3 and p['hits']!=3:hits_ok=False
        if b['hits']==p['hits']==3:ratios.append(b['target_seconds']['median']/p['target_seconds']['median'])
    promote=hits_ok and len(ratios)==len(SCENES) and statistics.median(ratios)>=1.1
    put(ROOT/'validation-summary.json',dict(scenes=summary,median_speedup=statistics.median(ratios) if ratios else None,
        reliable_hits_retained=hits_ok,promote=promote,native_seconds=native_spent()))
    print(json.dumps(summary,indent=2),flush=True)
    print('PROMOTE',promote,'ratios',ratios,flush=True)

if __name__=='__main__':main()
