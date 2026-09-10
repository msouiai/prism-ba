#!/usr/bin/env python3
"""Deeper training coverage, 12-outer returns and frozen opening comparator."""
import argparse, json, os, pathlib, statistics, subprocess
import numpy as np
import rl_damping_pilot as p

ROOT=pathlib.Path('/tmp/prism-rl-damping-extended')
BIN=ROOT/'build/prism-tr'
OLD=pathlib.Path('/tmp/prism-rl-damping')
p.ROOT=ROOT
SCENES={
 'trafalgar-126':dict(target=105579.58394455544,cap=4),
 'final-1936':dict(target=5125687.352261469,cap=8),
 'muell-gba146':dict(target=1946488.746262194,cap=12),
}

def run(*args,**kwargs):
    return p.run(*args,binary=BIN,**kwargs)

def smoke():
    rows=[]
    for rep in range(3):
        for arm,bin_,flags,log in [('old',OLD/'build-v2/prism-tr',{},False),
                                  ('off',BIN,{},False),('zero',BIN,{'OCA_RLD_OPENING':0},True)]:
            rows.append(p.run(f'check-{arm}-{rep}',binary=bin_,extra=flags,logging=log))
    costs=[r['audit_cost'] for r in rows]
    assert (max(costs)-min(costs))/max(costs)<1e-7
    assert len({r['matvecs'] for r in rows})==1
    r=run('check-opening',extra={'OCA_RLD_OPENING':2})
    ds=[e for e in r['events'] if e['type']=='decision']
    assert [e['action'] for e in ds]==[-1,-1]+[0]*(len(ds)-2)
    for e in ds:assert abs(e['lambda']/e['base_lambda']-10.**e['action'])<1e-12
    p.put(ROOT/'smoke.json',dict(passed=True,off_costs=costs,off_matvecs=rows[0]['matvecs'],
                                opening_actions=[e['action'] for e in ds]))

def select():
    chosen=[]
    for small,large in [('ladybug-598',None),('dubrovnik-135','dubrovnik-356'),('venice-89','venice-951')]:
        scene=small
        if large:
            r=json.loads((ROOT/'runs'/('scout-'+large)/'result.json').read_text())
            if any(e['cg']>=64 for e in r['events'] if e['type']=='outer'):scene=large
        r=json.loads((ROOT/'runs'/('scout-'+scene)/'result.json').read_text())
        decisions={e['outer'] for e in r['events'] if e['type']=='decision'}
        es=[e for e in r['events'] if e['type']=='outer' and e['accepted'] and e['outer'] in decisions]
        depths={e['outer']:e['cg'] for e in es}
        ks=[k for k in [1,3] if k in depths]
        candidates=[e for e in es if e['outer']>3 and e['cg']>=64]
        deep=[]
        for e in candidates:
            if all(abs(e['outer']-k)>=3 for k in deep):deep.append(e['outer'])
            if len(deep)==2:break
        if len(deep)<2:
            for e in sorted(es,key=lambda e:(-e['cg'],e['outer'])):
                if e['outer']>3 and all(abs(e['outer']-k)>=3 for k in deep):deep.append(e['outer'])
                if len(deep)==2:break
        for k in sorted(set(ks+deep)):
            chosen.append(dict(scene=scene,k=k,scout_previous_cg=depths[k]))
    path=ROOT/'selection.json'
    if path.exists():assert json.loads(path.read_text())==chosen
    else:p.put(path,chosen)
    print('FROZEN SELECTION',chosen,flush=True)
    return chosen

def collect():
    assert json.loads((ROOT/'smoke.json').read_text())['passed']
    cells=[]
    (ROOT/'checkpoints').mkdir(exist_ok=True)
    for cell in select():
        scene,k=cell['scene'],cell['k'];cp=ROOT/'checkpoints'/f'{scene}-{k}.cp'
        ref=run(f'capture-{scene}-{k}',scene,extra={'OCA_RLD_SAVE':cp,'OCA_RLD_AT':k,
                 'OCA_RLD_STEPS':12,'OCA_MAX_SECONDS':3},iterations=100)
        assert cp.exists(),cell
        branches=[]
        for rep in range(3):
            order=[0,-1,1];offset=rep%3;order=order[offset:]+order[:offset]
            for action in order:
                r=run(f'branch-{scene}-{k}-{action}-{rep}',scene,extra={'OCA_RLD_LOAD':cp,
                    'OCA_RLD_ACTION':action,'OCA_RLD_STEPS':12,'OCA_MAX_SECONDS':3},iterations=100)
                d=next(e for e in r['events'] if e['type']=='decision')
                assert d['outer']==k and d['action']==action
                branches.append(dict(name=r['name'],action=action,rep=rep))
        cells.append(dict(**cell,checkpoint_sha256=p.sha(cp),branches=branches))
        p.put(ROOT/'collection.json',dict(checkpoints=cells,native_seconds=p.native_spent()))
        print('COLLECTED',len(cells),'states',flush=True)

def analyze():
    cells=[]
    for c in json.loads((ROOT/'collection.json').read_text())['checkpoints']:
        rows=[(b,json.loads((ROOT/'runs'/b['name']/'result.json').read_text())) for b in c['branches']]
        h=min(sum(e['dt'] for e in r['events'] if e['type']=='outer') for b,r in rows)
        h4=min(sum(e['dt'] for e in [e for e in r['events'] if e['type']=='outer'][:4]) for b,r in rows)
        auc={a:[] for a in [-1,0,1]};progress={a:[] for a in auc}
        short={a:[] for a in auc}
        for b,r in rows:
            score=p.curve_score(r,h);auc[b['action']].append(score['auc']);progress[b['action']].append(score['progress'])
            short[b['action']].append(p.curve_score(r,h4)['auc'])
        med={a:statistics.median(v) for a,v in auc.items()}
        x=next(e['features'] for e in rows[0][1]['events'] if e['type']=='decision')
        best=min([0,-1,1],key=lambda a:med[a]);spread=max(auc[0])-min(auc[0])
        cells.append(dict(scene=c['scene'],k=c['k'],features=x,horizon=h,auc=med,auc_raw=auc,
            short_horizon=h4,short_auc={a:statistics.median(v) for a,v in short.items()},
            short_best=min([0,-1,1],key=lambda a:statistics.median(short[a])),
            progress_raw=progress,best=best,signal=med[0]-med[best]>spread,baseline_spread=spread,
            continuation_outers=[sum(e['type']=='outer' for e in r['events']) for b,r in rows]))
    X=np.array([c['features'] for c in cells]);Y=np.array([[c['auc'][0]-c['auc'][a] for a in [-1,0,1]] for c in cells])
    groups=[c['scene'].split('-')[0] for c in cells]
    pred,models=p.fit_predict(X,Y,groups)
    js=[max([1,0,2],key=lambda j:pred[i,j]) for i in range(len(X))]
    advantages=[float(Y[i,j]) for i,j in enumerate(js)]
    fam={g:float(np.mean([v for v,h in zip(advantages,groups) if h==g])) for g in sorted(set(groups))}
    mean=X.mean(0);sd=X.std(0);sd[sd<1e-8]=1.
    Z=np.c_[np.clip((X-mean)/sd,-5,5),np.ones(len(X))];reg=np.eye(65)*10;reg[-1,-1]=.01
    W=np.linalg.solve(Z.T@Z+reg,Z.T@Y)
    policy='PRISM_RLD_LINEAR_V1 64\n'+' '.join(map(repr,mean.tolist()+sd.tolist()+W.T.flatten().tolist()))+'\n'
    pp=ROOT/'policy.txt'
    if pp.exists():assert pp.read_text()==policy
    else:pp.write_text(policy)
    p.put(ROOT/'family_models.json',models)
    result=dict(cells=cells,policy_sha256=p.sha(pp),family_advantages=fam,mean_advantage=float(np.mean(advantages)),
        heldout_actions=[j-1 for j in js],max_history_depth=float(X[:,[7,23,39,55]].max()),
        deep_states=int(sum(X[:,7]>=.5)),signals=sum(c['signal'] for c in cells))
    p.put(ROOT/'analysis.json',result)
    print('MODEL', {k:v for k,v in result.items() if k!='cells'},flush=True)

def parity():
    source=ROOT/'parity.cc'
    source.write_text('#include "rl_damping.h"\n#include <iostream>\nint main(){PrismRLDamping p;while(std::cin>>p.history[0]){for(int j=1;j<p.NX;++j)std::cin>>p.history[j];std::cout<<p.Action(1)<<"\\n";}}\n')
    subprocess.run(['g++','-O2','-std=c++17','-I'+str(ROOT/'build/headers'),str(source),'-o',str(ROOT/'parity')],check=True)
    X=np.array([c['features'] for c in json.loads((ROOT/'analysis.json').read_text())['cells']])
    nums=np.array(list(map(float,(ROOT/'policy.txt').read_text().split()[2:])))
    pred=np.c_[np.clip((X-nums[:64])/nums[64:128],-5,5),np.ones(len(X))]@nums[128:].reshape(3,65).T
    expected=[max([1,0,2],key=lambda j:pred[i,j])-1 for i in range(len(X))]
    env={k:v for k,v in os.environ.items() if not k.startswith('OCA_')};env['OCA_RLD_POLICY']=str(ROOT/'policy.txt')
    r=subprocess.run([str(ROOT/'parity')],input='\n'.join(' '.join(map(str,x)) for x in X),text=True,capture_output=True,env=env,check=True)
    assert list(map(int,r.stdout.split()))==expected
    p.put(ROOT/'parity.json',dict(passed=True,states=len(X),actions=expected))

def validate():
    parity()
    arms={'baseline':{},'old-learned':{'OCA_RLD_POLICY':OLD/'policy.txt'},
          'extended-learned':{'OCA_RLD_POLICY':ROOT/'policy.txt'},'opening-2':{'OCA_RLD_OPENING':2},
          'work-rule':{'OCA_RLD_POLICY':OLD/'work-rule.txt'}}
    protocol=dict(scenes=SCENES,repeats=3,arms={a:{k:str(v) for k,v in f.items()} for a,f in arms.items()},
        binary_sha256=p.sha(BIN),policy_sha256={a:p.sha(f['OCA_RLD_POLICY']) for a,f in arms.items() if 'OCA_RLD_POLICY' in f},initial_lambda=.1)
    pp=ROOT/'validation-protocol.json'
    if pp.exists():assert json.loads(pp.read_text())==protocol
    else:p.put(pp,protocol)
    rows=[]
    for rep in range(3):
        for si,(scene,spec) in enumerate(SCENES.items()):
            names=list(arms);offset=(rep+si)%len(names);names=names[offset:]+names[:offset]
            for arm in names:
                row=run(f'validation-{scene}-{arm}-{rep}',scene,extra=dict(OCA_TARGET_COST=spec['target'],
                    OCA_MAX_SECONDS=spec['cap'],**arms[arm]),iterations=600,logging=False)
                rows.append(dict(scene=scene,arm=arm,rep=rep,target=spec['target'],
                    hit='target_seconds' in row and row['audit_cost']<=spec['target'],
                    **{k:row.get(k) for k in ['target_seconds','seconds','audit_cost','outers','rejects','matvecs','audit_error']}))
                p.put(ROOT/'validation-rows.json',rows)
            summarize(rows)

def summarize(rows):
    summary={}
    for scene in SCENES:
        summary[scene]={}
        for arm in sorted({r['arm'] for r in rows}):
            rs=[r for r in rows if r['scene']==scene and r['arm']==arm]
            if not rs:continue
            c=dict(n=len(rs),hits=sum(r['hit'] for r in rs))
            for key in ['target_seconds','seconds','audit_cost','outers','rejects','matvecs']:
                vs=[r[key] for r in rs if r[key] is not None]
                if vs:c[key]=dict(median=statistics.median(vs),min=min(vs),max=max(vs))
            summary[scene][arm]=c
    p.put(ROOT/'validation-summary.json',dict(scenes=summary,native_seconds=p.native_spent()))
    for scene,arms in summary.items():
        if arms:print('STATUS',scene,{a:(c['n'],c['hits'],round(c.get('target_seconds',c['seconds'])['median'],4)) for a,c in arms.items()},flush=True)

def champion():
    """Follow-up registered after the original panel; preserve its protocol."""
    pp=ROOT/'champion-check-protocol.json'
    if pp.exists():
        protocol=json.loads(pp.read_text());assert protocol['binary_sha256']==p.sha(BIN)
    else:
        p.put(pp,dict(reason='Resolve known initial-lambda mismatch against historical Muell champion; no policy retuning.',
            scene='muell-gba146',initial_lambda=10,target=SCENES['muell-gba146']['target'],
            repeats=3,arms=['baseline','opening-2'],cap=12,binary_sha256=p.sha(BIN)))
    rows=[]
    for rep in range(3):
        for arm in (['baseline','opening-2'] if rep%2==0 else ['opening-2','baseline']):
            flags=dict(OCA_TARGET_COST=SCENES['muell-gba146']['target'],OCA_MAX_SECONDS=12)
            if arm=='opening-2':flags['OCA_RLD_OPENING']=2
            r=run(f'champion-muell-{arm}-{rep}','muell-gba146',extra=flags,initial_lambda=10,
                  iterations=600,logging=False)
            rows.append(dict(arm=arm,rep=rep,**{k:r.get(k) for k in
                ['target_seconds','seconds','audit_cost','outers','rejects','matvecs']}))
            p.put(ROOT/'champion-check-rows.json',rows)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['smoke','select','collect','analyze','validate','champion']);a=ap.parse_args()
    ROOT.mkdir(exist_ok=True)
    globals()[a.stage]()
