#!/usr/bin/env python3
"""Direct finite-policy search on complete, target-terminated BA episodes."""
import argparse, json, math, os, pathlib, shutil, statistics, subprocess
import rl_damping_pilot as p

ROOT=pathlib.Path('/tmp/prism-rl-damping-trajectory');BIN=ROOT/'build-v2/prism-tr'
p.ROOT=ROOT;p.NATIVE_CAP=900
TRAIN={'ladybug-598':(180411.357852*1.01,4),'dubrovnik-356':(724127.912566*1.01,4),
       'venice-89':(303286.305616*1.01,4)}
TRANSFER={'trafalgar-126':(105579.58394455544,4),'final-1936':(5125687.352261469,8),
          'muell-gba146':(1946488.746262194,12)}
LARGE='final-13682';LARGE_TARGET=27591576.557625167

def policies():
    folder=ROOT/'policies';folder.mkdir(exist_ok=True)
    result={}
    for label,mode,rho,cg in [('fast',1,.7,.25),('strict',1,.95,.125),('cap',2,.95,.125),('mixed',3,.95,.125)]:
        for budget in [2,4]:
            name=f'{label}-{budget}';path=folder/(name+'.txt')
            text=f'PRISM_RLD_EPISODE_V1 {mode} {budget} {rho} {cg} 1\n'
            if path.exists():assert path.read_text()==text
            else:path.write_text(text)
            result[name]={'OCA_RLD_EPISODE':str(path)}
    return result

def run(name,scene,flags,lam=.1,logging=False,iterations=600):
    return p.run(name,scene,extra=flags,binary=BIN,initial_lambda=lam,logging=logging,
                 iterations=iterations,process_timeout=180 if scene==LARGE else 45)

def row(r,scene,lam,arm,rep,target,cap):
    return dict(scene=scene,lambda0=lam,arm=arm,rep=rep,target=target,cap=cap,
        hit='target_seconds' in r and r['target_seconds']<=cap and r['audit_cost']<=target,
        **{k:r.get(k) for k in ['target_seconds','seconds','audit_cost','outers','rejects','matvecs','audit_error','name']})

def smoke():
    zero=ROOT/'zero.txt';zero.write_text('PRISM_RLD_EPISODE_V1 0 0 .95 .125 1\n')
    rows=[]
    for rep in range(3):
        rows.append(p.run(f'smoke-v2-parent-{rep}',binary=pathlib.Path('/tmp/prism-rl-damping-extended/build/prism-tr'),logging=False))
        rows.append(run(f'smoke-v2-off-{rep}','ladybug-49',{},iterations=8))
        rows.append(run(f'smoke-v2-zero-{rep}','ladybug-49',{'OCA_RLD_EPISODE':zero},logging=True,iterations=8))
    assert len({r['matvecs'] for r in rows})==1
    cs=[r['audit_cost'] for r in rows];assert (max(cs)-min(cs))/max(cs)<1e-7
    r=run('smoke-v2-active','ladybug-49',policies()['fast-2'],logging=True,iterations=12)
    ds=[e for e in r['events'] if e['type']=='decision'];active=[e for e in ds if e['action']]
    assert active and len(active)<=2
    assert all(y['outer']-x['outer']>=2 for x,y in zip(active,active[1:]))
    assert all(abs(e['lambda']/e['base_lambda']-10.**e['action'])<1e-12 for e in ds)
    p.put(ROOT/'smoke.json',dict(passed=True,binary_sha256=p.sha(BIN),off_costs=cs,matvecs=rows[0]['matvecs'],actions=[(e['outer'],e['action']) for e in ds]))

def summarize(rows,filename):
    out=[]
    for scene,lam,arm in dict.fromkeys((r['scene'],r['lambda0'],r['arm']) for r in rows):
        rs=[r for r in rows if (r['scene'],r['lambda0'],r['arm'])==(scene,lam,arm)]
        c=dict(scene=scene,lambda0=lam,arm=arm,n=len(rs),hits=sum(r['hit'] for r in rs))
        for key in ['target_seconds','seconds','audit_cost','outers','rejects','matvecs']:
            vs=[r[key] for r in rs if r[key] is not None]
            if vs:c[key]=dict(median=statistics.median(vs),min=min(vs),max=max(vs))
        out.append(c)
    p.put(ROOT/filename,out);return out

def train():
    assert json.loads((ROOT/'smoke.json').read_text())['passed']
    assert json.loads((ROOT/'smoke.json').read_text())['binary_sha256']==p.sha(BIN)
    arms={'baseline':{},**policies(),'opening-2':{'OCA_RLD_OPENING':2}}
    protocol=dict(scenes=TRAIN,initial_lambdas=[.1,10.],reps=3,arms=arms,binary_sha256=p.sha(BIN),
                  policy_sha256={a:p.sha(f['OCA_RLD_EPISODE']) for a,f in arms.items() if 'OCA_RLD_EPISODE' in f})
    pp=ROOT/'training-protocol.json'
    if pp.exists():assert json.loads(pp.read_text())==json.loads(json.dumps(protocol))
    else:p.put(pp,protocol)
    rows=[]
    for rep in range(3):
        for si,(scene,(target,cap)) in enumerate(TRAIN.items()):
            for li,lam in enumerate([.1,10.]):
                names=list(arms);off=(rep+si+li)%len(names);names=names[off:]+names[:off]
                for arm in names:
                    r=run(f'train-q1-{scene}-l{lam}-{arm}-{rep}',scene,
                          dict(OCA_TARGET_COST=target,OCA_MAX_SECONDS=cap,**arms[arm]),lam)
                    rows.append(row(r,scene,lam,arm,rep,target,cap));p.put(ROOT/'training-rows.json',rows)
                summarize(rows,'training-summary.json')
                print('TRAIN COMPLETE TASK',scene,lam,'rep',rep,'episodes',len(rows),'native',round(p.native_spent(),2),flush=True)

def select():
    rows=json.loads((ROOT/'training-rows.json').read_text());assert len(rows)==180
    names=['baseline']+list(policies());loss={a:{} for a in names+['opening-2']}
    for scene in TRAIN:
        for lam in [.1,10.]:
            base=[r for r in rows if r['scene']==scene and r['lambda0']==lam and r['arm']=='baseline']
            denom=statistics.median(r['target_seconds'] for r in base) if all(r['hit'] for r in base) else TRAIN[scene][1]
            for arm in loss:
                rs=[r for r in rows if r['scene']==scene and r['lambda0']==lam and r['arm']==arm]
                assert len(rs)==3
                loss[arm][f'{scene}/{lam}']=statistics.mean(math.log((r['target_seconds'] if r['hit'] else 4*r['cap'])/denom) for r in rs)
    scores={a:statistics.mean(v.values()) for a,v in loss.items()}
    selected=min(list(policies()),key=lambda a:scores[a]);deployment=min(names,key=lambda a:scores[a])
    family={}
    for held in TRAIN:
        candidate=min(names,key=lambda a:statistics.mean(v for task,v in loss[a].items() if not task.startswith(held+'/')))
        family[held]=dict(selected=candidate,loss=statistics.mean(v for task,v in loss[candidate].items() if task.startswith(held+'/')),
                         baseline_loss=statistics.mean(v for task,v in loss['baseline'].items() if task.startswith(held+'/')))
    dst=ROOT/'selected-policy.txt';src=pathlib.Path(policies()[selected]['OCA_RLD_EPISODE'])
    if dst.exists():assert dst.read_bytes()==src.read_bytes()
    else:shutil.copy2(src,dst)
    result=dict(scores=scores,task_losses=loss,selected_feedback=selected,training_choice=deployment,
                family_holdout=family,policy_sha256=p.sha(dst),selection_scope='Training scenes only; full target-terminated episodes; no transfer outcomes read.')
    p.put(ROOT/'selection.json',result);print('SELECTION',json.dumps(result),flush=True)

def transfer():
    selected=json.loads((ROOT/'selection.json').read_text());assert p.sha(ROOT/'selected-policy.txt')==selected['policy_sha256']
    arms={'baseline':{},'feedback':{'OCA_RLD_EPISODE':str(ROOT/'selected-policy.txt')},'opening-2':{'OCA_RLD_OPENING':2}}
    protocol=dict(scenes=TRANSFER,initial_lambdas=[.1,10.],reps=3,arms=arms,policy_sha256=selected['policy_sha256'],binary_sha256=p.sha(BIN))
    pp=ROOT/'transfer-protocol.json'
    if pp.exists():assert json.loads(pp.read_text())==json.loads(json.dumps(protocol))
    else:p.put(pp,protocol)
    rows=[]
    for rep in range(3):
        for si,(scene,(target,cap)) in enumerate(TRANSFER.items()):
            for li,lam in enumerate([.1,10.]):
                names=list(arms);off=(rep+si+li)%len(names);names=names[off:]+names[:off]
                for arm in names:
                    r=run(f'transfer-{scene}-l{lam}-{arm}-{rep}',scene,
                        dict(OCA_TARGET_COST=target,OCA_MAX_SECONDS=cap,**arms[arm]),lam)
                    rows.append(row(r,scene,lam,arm,rep,target,cap));p.put(ROOT/'transfer-rows.json',rows)
                cs=summarize(rows,'transfer-summary.json')
                print('TRANSFER',scene,lam,[(c['arm'],c['n'],c['hits'],c.get('target_seconds',{}).get('median')) for c in cs if c['scene']==scene and c['lambda0']==lam],flush=True)

def large():
    import schur_recovery_study as s
    selected=json.loads((ROOT/'selection.json').read_text());assert p.sha(ROOT/'selected-policy.txt')==selected['policy_sha256']
    old=json.loads(pathlib.Path('/workspace/prism-final13682-convergence/protocol.json').read_text())
    dh,(dims,obs)=p.data(LARGE);assert dh==old['scenes'][LARGE]['input_sha256']
    caspar=ROOT/'caspar';caspar.mkdir(exist_ok=True)
    for arm in ['caspar32','caspar64']:assert p.sha(s.BINS[arm])==old['binaries'][arm]
    pp=ROOT/'large-protocol.json';proto=dict(old,arms=['baseline','feedback','opening-2','caspar32','caspar64'],
        binaries={**{a:p.sha(BIN) for a in ['baseline','feedback','opening-2']},
                  **{a:old['binaries'][a] for a in ['caspar32','caspar64']}},
        new_binary_sha256=p.sha(BIN),policy_sha256=selected['policy_sha256'],scope='Fresh frozen policy transfer; no tuning on largest scene.')
    if pp.exists():assert json.loads(pp.read_text())==proto
    else:p.put(pp,proto)
    rows=[]
    for rep in range(3):
        names=proto['arms'];off=rep%len(names);names=names[off:]+names[:off]
        for arm in names:
            extra=sum(json.loads(q.read_text()).get('seconds',0) for q in caspar.glob('*.result.json'))
            assert p.native_spent()+extra<900
            if arm.startswith('caspar'):
                raw=s.run_one(caspar,LARGE,arm,rep+1,LARGE_TARGET,20,dims,obs,old)
                assert raw['valid'],raw
                rr=dict(scene=LARGE,lambda0=None,arm=arm,rep=rep,hit=raw['hit'],target=LARGE_TARGET,cap=20,
                    target_seconds=raw['crossing'],seconds=raw['seconds'],audit_cost=raw['cost'],outers=raw['outers'],
                    rejects=raw['rejects'],matvecs=None,audit_error=raw['audit_error'],setup_seconds=raw['setup_seconds'],artifact=raw['artifact'])
            else:
                flags=dict(OCA_TARGET_COST=LARGE_TARGET,OCA_MAX_SECONDS=20)
                if arm=='feedback':flags['OCA_RLD_EPISODE']=ROOT/'selected-policy.txt'
                if arm=='opening-2':flags['OCA_RLD_OPENING']=2
                raw=run(f'large-{arm}-{rep}',LARGE,flags,.1)
                rr=row(raw,LARGE,.1,arm,rep,LARGE_TARGET,20)
            rows.append(rr);p.put(ROOT/'large-rows.json',rows)
            print('LARGE',arm,rep,'hit',rr['hit'],'target',rr['target_seconds'],'cost',rr['audit_cost'],flush=True)
            summarize(rows,'large-summary.json')
    diag=run('large-feedback-diagnostic',LARGE,dict(OCA_TARGET_COST=LARGE_TARGET,OCA_MAX_SECONDS=20,
        OCA_RLD_EPISODE=ROOT/'selected-policy.txt'),.1,logging=True)
    decisions=[e for e in diag['events'] if e['type']=='decision']
    p.put(ROOT/'large-policy-diagnostic.json',dict(scope='Mechanism trace only, excluded from timing panel',
        actions=[dict(outer=e['outer'],action=e['action'],fallback=e['episode_fallback'],
                      baseline_lambda=e['base_lambda'],used_lambda=e['lambda'],
                      previous_cg_fraction=e['features'][7],previous_rho=e['features'][2]) for e in decisions]))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['smoke','train','select','transfer','large']);a=ap.parse_args()
    ROOT.mkdir(exist_ok=True);globals()[a.stage]()
