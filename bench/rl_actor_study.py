#!/usr/bin/env python3
"""On-policy residual-control learning with explicit native-time rewards."""
import argparse,json,math,pathlib,statistics
import numpy as np
import rl_damping_pilot as p
import rl_damping_trajectory as t
ROOT=pathlib.Path('/tmp/prism-rl-actor');BIN=ROOT/'build/prism-tr'
PARENT=pathlib.Path('/tmp/prism-rl-curvature/build/prism-tr');NF=20
p.ROOT=ROOT;p.NATIVE_CAP=1000;t.ROOT=ROOT;t.BIN=BIN
SMALL=['ladybug-49','dubrovnik-88','venice-52']
EXPERIMENTS={'lambda-time':(3,'time'),'joint-time':(5,'time'),'joint-rate':(5,'rate')}

def put(name,obj):p.put(ROOT/name,obj)
def read(name):return json.loads((ROOT/name).read_text())
def softmax(W,x):
    z=W@x;z-=max(z);v=np.exp(z);return v/v.sum()
def policy(name,W):
    path=ROOT/'policies'/(name+'.txt');path.parent.mkdir(parents=True,exist_ok=True)
    text=f'PRISM_RLA_V1 {len(W)} {NF}\n'+'\n'.join(' '.join(f'{v:.17g}' for v in row) for row in W)+'\n'
    if path.exists():assert path.read_text()==text
    else:path.write_text(text)
    return path
def initial(na):
    W=np.zeros((na,NF));W[0,0]=math.log(.5);W[1:,0]=math.log(.5/(na-1));return W
def run(name,scene,flags={},lam=.1,logging=False,iters=600,binary=BIN):
    return p.run(name,scene,extra=flags,initial_lambda=lam,binary=binary,logging=logging,
        iterations=iters,process_timeout=180 if scene==t.LARGE else 45)
def progress(cost,initial,target):
    return float(np.clip(math.log(initial/max(cost,target))/math.log(initial/target),0,1))

def samples(r,task,reward,W):
    hit='target_seconds' in r and r['target_seconds']<=task['cap'] and r['audit_cost']<=task['target']
    end=r['target_seconds'] if hit else r['seconds']
    out=[];ends=[e for e in r['events'] if e['type']=='actor_outer']
    if ends:end=max(end,ends[-1]['seconds'])
    for event in r['events']:
        if event['type']!='actor':continue
        x=np.array(event['features']);probs=np.array(event['probabilities']);a=event['action']
        assert event['sampled'] and len(x)==NF and max(abs(probs-softmax(W,x)))<1e-12
        assert end>=event['seconds']
        P0=progress(event['cost'],event['initial_cost'],task['target'])
        if reward=='time':value=-(end-event['seconds'])/task['reference_seconds']+1-P0
        else:
            value=0.;last_t=event['seconds'];last_P=P0
            future=[e for e in ends if e['outer']>event['outer']]
            for i,e in enumerate(future):
                tm=end if i==len(future)-1 else e['seconds'];dt=tm-last_t;assert dt>0
                P=progress(e['cost'],event['initial_cost'],task['target'])
                value+=(P-last_P)/max(dt/task['reference_seconds'],1e-9)
                last_t=tm;last_P=P
        penalty=0 if hit else -4*task['cap']/task['reference_seconds'];value+=penalty
        out.append(dict(x=x.tolist(),probabilities=probs.tolist(),action=a,return_value=value,
            seconds_remaining=end-event['seconds'],remaining_progress=1-P0,failure_penalty=penalty,
            outer=event['outer']))
    return out

def smoke():
    zero=initial(5);zero[:,0]=-5;zero[0,0]=5;path=policy('zero',zero);rows=[]
    for rep in range(3):
        for name,binary,flags,log in [('parent',PARENT,{},False),('off',BIN,{},False),
                ('zero',BIN,{'OCA_RLA_POLICY':path},True)]:
            rows.append(run(f'smoke-{name}-{rep}','ladybug-49',flags,logging=log,iters=8,binary=binary))
    assert len({(r['outers'],r['rejects'],r['matvecs']) for r in rows})==1
    costs=[r['audit_cost'] for r in rows];assert (max(costs)-min(costs))/max(costs)<1e-7
    W=initial(5);path=policy('sample',W)
    r=run('smoke-sample','ladybug-49',{'OCA_RLA_POLICY':path,'OCA_RLA_SAMPLE':9123},logging=True,iters=12)
    events=[e for e in r['events'] if e['type']=='actor'];moves=[e for e in events if e['action']]
    assert events and len(moves)<=3 and len({e['outer'] for e in events})==len(events)
    assert all(b['outer']-a['outer']>=2 for a,b in zip(moves,moves[1:]))
    for e in events:assert max(abs(softmax(W,np.array(e['features']))-e['probabilities']))<1e-12
    d={e['outer']:e for e in r['events'] if e['type']=='decision'}
    for e in events:
        v=d[e['outer']];factor={0:1,1:.5,2:2,3:1,4:1}[e['action']]
        assert abs(v['lambda']/v['base_lambda']-factor)<1e-12
    put('smoke.json',dict(passed=True,binary_sha256=p.sha(BIN),costs=costs,
        work=[(r['outers'],r['rejects'],r['matvecs']) for r in rows],sample_events=events))

def references():
    assert read('smoke.json')['binary_sha256']==p.sha(BIN)
    targets={s:target for s,(target,cap) in t.TRAIN.items()};calibration=[]
    for scene in SMALL:
        rs=[run(f'calibrate-{scene}-{rep}',scene,{},iters=8,binary=PARENT) for rep in range(3)]
        target=statistics.median(r['audit_cost'] for r in rs)*1.01
        assert target<min(r['trace'][0]['cost'] for r in rs)*.99
        targets[scene]=target;calibration.append(dict(scene=scene,target=target,runs=[r['name'] for r in rs]))
    put('target-calibration.json',dict(targets=targets,calibration=calibration))
    tasks=[];rows=[]
    for scene in ['ladybug-49','ladybug-598','dubrovnik-88','dubrovnik-356','venice-52','venice-89']:
        for lam in [.1,10.]:
            target=targets[scene];rs=[]
            for rep in range(3):
                r=run(f'reference-{scene}-l{lam}-{rep}',scene,dict(OCA_TARGET_COST=target,OCA_MAX_SECONDS=4),lam)
                rr=t.row(r,scene,lam,'baseline',rep,target,4);rows.append(rr);rs.append(rr)
            valid=all(r['hit'] for r in rs)
            if valid:tasks.append(dict(scene=scene,lambda0=lam,target=target,cap=4,
                reference_seconds=statistics.median(r['target_seconds'] for r in rs)))
            print('REFERENCE',scene,lam,'eligible',valid,flush=True)
            put('reference-rows.json',rows)
    assert len(tasks)==12,'Disclose/exclude unreliable reference before fitting; expected twelve tasks.'
    put('tasks.json',tasks);t.summarize(rows,'reference-summary.json')
    put('training-protocol.json',dict(tasks=tasks,experiments=EXPERIMENTS,updates=8,
        binary_sha256=p.sha(BIN),protocol_sha256=p.sha(pathlib.Path(__file__).parents[1]/'docs/rl_actor_protocol.md')))

def train():
    tasks=read('tasks.json');assert len(tasks)==12;allmetrics=[]
    for ei,(name,(na,reward)) in enumerate(EXPERIMENTS.items()):
        W=initial(na);m=np.zeros_like(W);v=np.zeros_like(W);critic=np.zeros(NF);history=[]
        for batch in range(8):
            statepath=ROOT/f'training/{name}/update-{batch}.json'
            if statepath.exists():
                state=json.loads(statepath.read_text());W=np.array(state['weights']);m=np.array(state['adam_m']);v=np.array(state['adam_v']);critic=np.array(state['critic']);history=state['history'];allmetrics.append(state['metrics']);continue
            path=policy(f'{name}/batch-{batch}',W);grad=np.zeros_like(W);batch_samples=[];episodes=[]
            for j in range(len(tasks)):
                ti=(j+batch)%len(tasks);task=tasks[ti];seed=780000+ei*10000+batch*101+ti
                r=run(f'train-{name}-b{batch}-t{ti}',task['scene'],dict(OCA_TARGET_COST=task['target'],
                    OCA_MAX_SECONDS=task['cap'],OCA_RLA_POLICY=path,OCA_RLA_SAMPLE=seed),task['lambda0'],logging=True)
                ss=samples(r,task,reward,W)
                for s in ss:
                    x=np.array(s['x']);pr=np.array(s['probabilities']);adv=s['return_value']-x@critic
                    grad-=adv*pr[:,None]*x[None,:];grad[s['action']]+=adv*x
                    batch_samples.append(s)
                rr=t.row(r,task['scene'],task['lambda0'],name,batch,task['target'],task['cap'])
                rr['relative_time']=(r['target_seconds'] if rr['hit'] else 4*task['cap'])/task['reference_seconds']
                rr['samples']=len(ss);rr['moves']=sum(s['action']!=0 for s in ss);episodes.append(rr)
                put(f'training/{name}/batch-{batch}-episodes.json',episodes)
            grad/=len(tasks);norm=float(np.linalg.norm(grad));grad/=max(1,norm)
            m=.9*m+.1*grad;v=.999*v+.001*grad*grad
            W=np.clip(W+.05*(m/(1-.9**(batch+1)))/(np.sqrt(v/(1-.999**(batch+1)))+1e-8),-5,5)
            # Baseline for the NEXT batch only; no action-dependent fit to the
            # current sample is used in that sample's policy gradient.
            history+=batch_samples
            if history:
                X=np.array([s['x'] for s in history]);Y=np.array([s['return_value'] for s in history]);reg=np.eye(NF)*.1;reg[0,0]=.01
                critic=np.linalg.solve(X.T@X+reg,X.T@Y)
            metrics=dict(experiment=name,batch=batch,hits=sum(r['hit'] for r in episodes),episodes=len(episodes),
                geometric_relative_time=math.exp(statistics.mean(math.log(r['relative_time']) for r in episodes)),
                samples=len(batch_samples),moves=sum(r['moves'] for r in episodes),gradient_norm=norm)
            put(f'training/{name}/update-{batch}.json',dict(weights=W.tolist(),adam_m=m.tolist(),adam_v=v.tolist(),
                critic=critic.tolist(),history=history,metrics=metrics));allmetrics.append(metrics)
            put('learning-metrics.json',allmetrics);print('UPDATE',json.dumps(metrics),flush=True)
        final=policy(name+'/final',W);put(f'{name}-frozen.json',dict(path=str(final),sha256=p.sha(final),updates=8,reward=reward))

def arms():
    out={'baseline':{}}
    for name in EXPERIMENTS:
        meta=read(name+'-frozen.json');assert p.sha(meta['path'])==meta['sha256'];out[name]={'OCA_RLA_POLICY':meta['path']}
    out['fixed-eta2']={'OCA_RLA_FIXED_ETA':2};return out

def evaluate(phase):
    ar=arms()
    if phase=='training-eval':tasks=read('tasks.json');ar={k:v for k,v in ar.items() if k!='fixed-eta2'}
    elif phase=='transfer':tasks=[dict(scene=s,lambda0=.1,target=q,cap=cap) for s,(q,cap) in t.TRANSFER.items()]+[
        dict(scene='muell-gba146',lambda0=10.,target=t.TRANSFER['muell-gba146'][0],cap=12)]
    else:tasks=[dict(scene=t.LARGE,lambda0=.1,target=t.LARGE_TARGET,cap=20)]
    put(phase+'-protocol.json',dict(tasks=tasks,arms=ar,reps=3,binary_sha256=p.sha(BIN),
        policy_sha256={a:p.sha(f['OCA_RLA_POLICY']) for a,f in ar.items() if 'OCA_RLA_POLICY' in f}))
    rows=[]
    for rep in range(3):
        for ti,task in enumerate(tasks):
            names=list(ar);off=(ti+rep)%len(names);names=names[off:]+names[:off]
            for a in names:
                r=run(f'{phase}-{task["scene"]}-l{task["lambda0"]}-{a}-{rep}',task['scene'],
                    dict(OCA_TARGET_COST=task['target'],OCA_MAX_SECONDS=task['cap'],**ar[a]),task['lambda0'])
                rows.append(t.row(r,task['scene'],task['lambda0'],a,rep,task['target'],task['cap']))
                put(phase+'-rows.json',rows);t.summarize(rows,phase+'-summary.json')
                print(phase.upper(),task['scene'],task['lambda0'],a,rep,rows[-1]['hit'],rows[-1]['target_seconds'],flush=True)
    if phase!='training-eval':
        diagnostics=[]
        for task in tasks:
            for a in EXPERIMENTS:
                r=run(f'diagnostic-{task["scene"]}-l{task["lambda0"]}-{a}',task['scene'],
                    dict(OCA_TARGET_COST=task['target'],OCA_MAX_SECONDS=task['cap'],**ar[a]),task['lambda0'],logging=True)
                diagnostics.append(dict(scene=task['scene'],lambda0=task['lambda0'],arm=a,name=r['name'],events=r['events']))
        put(phase+'-diagnostics.json',diagnostics)

def stochastic():
    ar=arms();ar.pop('fixed-eta2');ar['untrained-joint']={'OCA_RLA_POLICY':str(policy('untrained-joint',initial(5)))}
    tasks=[dict(scene=s,lambda0=.1,target=q,cap=cap,reps=5) for s,(q,cap) in t.TRANSFER.items()]+[
        dict(scene='muell-gba146',lambda0=10.,target=t.TRANSFER['muell-gba146'][0],cap=12,reps=5),
        dict(scene=t.LARGE,lambda0=.1,target=t.LARGE_TARGET,cap=20,reps=3)]
    put('stochastic-protocol.json',dict(tasks=tasks,arms=ar,seeds=[910000+r for r in range(5)],
        binary_sha256=p.sha(BIN),policy_sha256={a:p.sha(f['OCA_RLA_POLICY']) for a,f in ar.items() if f}))
    rows=[]
    for rep in range(5):
        for ti,task in enumerate(tasks):
            if rep>=task['reps']:continue
            names=list(ar);off=(rep+ti)%len(names);names=names[off:]+names[:off]
            for a in names:
                flags=dict(OCA_TARGET_COST=task['target'],OCA_MAX_SECONDS=task['cap'],**ar[a])
                if a!='baseline':flags['OCA_RLA_SAMPLE']=910000+rep
                r=run(f'stochastic-{task["scene"]}-l{task["lambda0"]}-{a}-{rep}',task['scene'],flags,task['lambda0'])
                rr=t.row(r,task['scene'],task['lambda0'],a,rep,task['target'],task['cap']);rr['seed']=910000+rep if a!='baseline' else None
                rows.append(rr);put('stochastic-rows.json',rows);t.summarize(rows,'stochastic-summary.json')
                print('STOCHASTIC',task['scene'],task['lambda0'],a,rep,rr['hit'],rr['target_seconds'],flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['smoke','references','train','training-eval','transfer','large','stochastic']);a=ap.parse_args()
    ROOT.mkdir(exist_ok=True)
    if a.stage in ['training-eval','transfer','large']:evaluate(a.stage)
    else:globals()[a.stage]()
