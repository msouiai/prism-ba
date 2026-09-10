#!/usr/bin/env python3
"""Bounded checkpoint/branch pilot, independent audits and family validation."""
from __future__ import annotations
import argparse, csv, hashlib, json, math, os, pathlib, re, statistics, subprocess, sys, time
import numpy as np
from audit_prism_state import observations, audit

ROOT=pathlib.Path('/tmp/prism-rl-damping')
BIN=ROOT/'build-v2/prism-tr'
BASE=pathlib.Path('/workspace/prism-model-followup/candidate/prism-tr')
SELECTED=pathlib.Path('/workspace/prism-model-followup/selected_candidate.json')
DATA=pathlib.Path('/workspace/bal')
TRAIN=['ladybug-49','dubrovnik-88','venice-52']
NATIVE_CAP=600.
CACHE={}

def sha(p):
    h=hashlib.sha256()
    with pathlib.Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def put(p,obj):
    p=pathlib.Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n');tmp.replace(p)
def data(scene):
    if scene not in CACHE:CACHE[scene]=(sha(DATA/(scene+'.txt')),observations(DATA/(scene+'.txt')))
    return CACHE[scene]
def native_spent():
    return sum(json.loads(p.read_text()).get('seconds',0.) for p in (ROOT/'runs').glob('*/result.json'))

def run(name,scene='ladybug-49',extra=None,iterations=8,binary=BIN,logging=True,expect_fail=False,initial_lambda=.1,process_timeout=45):
    folder=ROOT/'runs'/name;rp=folder/'result.json'
    if rp.exists():
        row=json.loads(rp.read_text());assert row['binary_sha256']==sha(binary)
        command=json.loads((folder/'manifest.json').read_text())['command']
        assert float(command[command.index('--lam0')+1])==initial_lambda
        return row
    if native_spent()>=NATIVE_CAP:raise RuntimeError('predeclared native budget exhausted')
    folder.mkdir(parents=True,exist_ok=False)
    flags=json.loads(SELECTED.read_text())['flags'].copy()
    flags['OCA_MAX_SECONDS']='20'
    if logging:flags['OCA_RLD_LOG']=str(folder/'telemetry.jsonl')
    flags.update({k:str(v) for k,v in (extra or {}).items()})
    env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE_','MF_DEBUG'))};env.update(flags)
    dh,(dims,obs)=data(scene)
    cmd=['flock','/tmp/prism_gpu.lock','timeout',str(process_timeout),str(binary),'--problem',str(DATA/(scene+'.txt')),
         '--algo','mfree_shifted_cg','--dof9','--zero_k2','--lam0',str(initial_lambda),'--max_iter',str(iterations),
         '--csv',str(folder/'trace.csv'),'--state_out',str(folder/'endpoint.state')]
    manifest=dict(command=cmd,flags=flags,binary_sha256=sha(binary),data_sha256=dh,scene=scene)
    if flags.get('OCA_RLD_LOAD'):manifest['checkpoint_sha256']=sha(flags['OCA_RLD_LOAD'])
    put(folder/'manifest.json',manifest)
    print('RUN',name,flush=True);t=time.monotonic()
    with (folder/'stdout.log').open('x') as out,(folder/'stderr.log').open('x') as err:
        process=subprocess.run(cmd,env=env,stdout=out,stderr=err)
    text=(folder/'stdout.log').read_text();stderr=(folder/'stderr.log').read_text()
    row=dict(name=name,scene=scene,returncode=process.returncode,wall_seconds=time.monotonic()-t,
             binary_sha256=manifest['binary_sha256'],data_sha256=dh)
    if expect_fail:
        assert process.returncode and 'mismatch' in stderr,(text,stderr)
        row['expected_failure']=True;put(rp,row);return row
    if process.returncode:
        row['error']=stderr[-4000:];put(rp,row);raise RuntimeError(row)
    m=re.search(r'RESULT .*?iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)',text)
    q=re.search(r'MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+) negcurv=(\d+) cand_evals=(\d+)',text)
    assert m and q,text[-2000:]
    cost=audit(folder/'endpoint.state',dims,obs)
    gap=abs(cost-float(m[2]))/max(1,abs(cost));assert gap<1e-7 and math.isfinite(cost)
    trace=list(csv.DictReader(line for line in (folder/'trace.csv').read_text().splitlines() if not line.startswith('#')))
    events=[json.loads(x,parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x))) for x in (folder/'telemetry.jsonl').read_text().splitlines()] if logging else []
    row.update(outers=int(m[1]),native_cost=float(m[2]),seconds=float(m[3]),accepts=int(q[1]),rejects=int(q[2]),matvecs=int(q[3]),
               audit_cost=cost,audit_error=gap,state_sha256=sha(folder/'endpoint.state'),events=events,
               trace=[{k:float(v) for k,v in x.items()} for x in trace])
    x=re.search(r'TARGET reached outer=(\d+) seconds=(\S+) cost=(\S+)',text)
    if x:row.update(target_seconds=float(x[2]),target_cost=float(x[3]))
    put(rp,row);print('DONE',name,'cost',round(cost,6),'seconds',row['seconds'],'mv',row['matvecs'],flush=True)
    return row

def smoke():
    rows=[]
    for rep in range(3):
        for mode,bin_,logging,extra in [('parent',BASE,False,{}),('off',BIN,False,{}),('zero',BIN,True,{'OCA_RLD_ACTION':'0'})]:
            rows.append(run(f'smoke-{mode}-{rep}',binary=bin_,logging=logging,extra=extra))
    endpoints=[x['audit_cost'] for x in rows]
    assert (max(endpoints)-min(endpoints))/max(endpoints)<1e-7,endpoints
    assert len({x['matvecs'] for x in rows})==1,[x['matvecs'] for x in rows]
    cp=ROOT/'checkpoints/smoke.cp';cp.parent.mkdir(exist_ok=True)
    cont=run('smoke-save',extra={'OCA_RLD_SAVE':cp,'OCA_RLD_AT':4})
    loads=[run(f'smoke-load-{r}',extra={'OCA_RLD_LOAD':cp,'OCA_RLD_ACTION':0,'OCA_RLD_STEPS':4}) for r in range(3)]
    ev=[e for e in cont['events'] if e['type']=='outer' and e['outer']>4]
    for row in loads:
        got=[e for e in row['events'] if e['type']=='outer']
        assert len(ev)==len(got)
        for x,y in zip(ev,got):
            for key in ['cost','lambda_used','lambda_next','rho','prediction']:
                assert abs(x[key]-y[key])/max(1,abs(x[key]))<1e-7,(key,x[key],y[key])
            assert all(x[k]==y[k] for k in ['cg','matvecs','rejects','repairs'])
    fails=run('smoke-mismatch',extra={'OCA_RLD_LOAD':cp,'OCA_FTOL':'2e-5'},expect_fail=True)
    actions=[]
    for action in [-1,1]:
        row=run(f'smoke-action-{action}',extra={'OCA_RLD_LOAD':cp,'OCA_RLD_ACTION':action,'OCA_RLD_STEPS':4})
        d=next(e for e in row['events'] if e['type']=='decision')
        assert d['action']==action and abs(d['lambda']/d['base_lambda']-10.**action)<1e-12
        actions.append(row)
    put(ROOT/'smoke.json',dict(passed=True,off_costs=endpoints,off_matvecs=rows[0]['matvecs'],
         continuation_costs=[cont['audit_cost']]+[x['audit_cost'] for x in loads],
         matched_fields=['cost','lambda_used','lambda_next','rho','prediction','cg','matvecs','rejects','repairs'],
         nonzero_action_costs=[x['audit_cost'] for x in actions],mismatch_rejected=fails['expected_failure']))
    print('SMOKE PASSED',flush=True)

def collect():
    assert json.loads((ROOT/'smoke.json').read_text())['passed']
    collected=[];missing=[]
    for scene in TRAIN:
        for k in range(1,9):
            cp=ROOT/'checkpoints'/f'{scene}-{k}.cp'
            reference=run(f'capture-{scene}-{k}',scene,{'OCA_RLD_SAVE':cp,'OCA_RLD_AT':k,'OCA_RLD_STEPS':4},iterations=20)
            if not cp.exists():missing.append(dict(scene=scene,k=k));continue
            branches=[]
            for rep in range(3):
                order=[0,-1,1] if rep%2==0 else [1,-1,0]
                for action in order:
                    r=run(f'branch-{scene}-{k}-{action}-{rep}',scene,
                          {'OCA_RLD_LOAD':cp,'OCA_RLD_ACTION':action,'OCA_RLD_STEPS':4},iterations=20)
                    branches.append(dict(action=action,rep=rep,name=r['name']))
            collected.append(dict(scene=scene,k=k,checkpoint_sha256=sha(cp),branches=branches))
            put(ROOT/'collection.json',dict(checkpoints=collected,missing=missing,native_seconds=native_spent()))
            analyze(partial=True)

def curve_score(row,horizon):
    ev=[e for e in row['events'] if e['type']=='outer'];assert ev
    c0=ev[0]['cost0'];cost=c0;elapsed=0.;integral=0.
    for e in ev:
        t=elapsed+e['dt']
        integral+=max(0.,min(horizon,t)-elapsed)*cost/c0
        if t>horizon:break
        elapsed=t;cost=e['cost']
    if elapsed<horizon and sum(e['dt'] for e in ev)<=horizon:integral+=(horizon-elapsed)*cost/c0
    return dict(auc=integral/horizon,progress=1-cost/c0)

def fit_predict(X,Y,groups):
    # Fixed regularization, no tuning on the held-out family's returns.
    predictions=np.zeros_like(Y);models={}
    for family in sorted(set(groups)):
        train=np.array([g!=family for g in groups]);test=~train
        mean=X[train].mean(0);sd=X[train].std(0);sd[sd<1e-8]=1.
        Z=np.clip((X[train]-mean)/sd,-5,5);Z=np.c_[Z,np.ones(sum(train))]
        reg=np.eye(Z.shape[1])*10.;reg[-1,-1]=.01
        W=np.linalg.solve(Z.T@Z+reg,Z.T@Y[train])
        predictions[test]=np.c_[np.clip((X[test]-mean)/sd,-5,5),np.ones(sum(test))]@W
        models[family]=dict(mean=mean.tolist(),sd=sd.tolist(),weights=W.tolist())
    return predictions,models

def analyze(partial=False):
    p=ROOT/'collection.json'
    if not p.exists():return
    collection=json.loads(p.read_text());cells=[]
    for cell in collection['checkpoints']:
        rows=[(x,json.loads((ROOT/'runs'/x['name']/'result.json').read_text())) for x in cell['branches']]
        horizon=min(sum(e['dt'] for e in r['events'] if e['type']=='outer') for _,r in rows)
        assert horizon>0
        metrics={a:[] for a in [-1,0,1]}
        for meta,row in rows:metrics[meta['action']].append(curve_score(row,horizon)['auc'])
        med={a:statistics.median(v) for a,v in metrics.items()};base=med[0];spread=max(metrics[0])-min(metrics[0])
        best=min([0,-1,1],key=lambda a:med[a]);signal=best!=0 and base-med[best]>spread
        decisions=[e for e in rows[0][1]['events'] if e['type']=='decision']
        if not decisions:raise RuntimeError('checkpoint not after an accepted step')
        cells.append(dict(scene=cell['scene'],k=cell['k'],horizon=horizon,auc=med,auc_raw=metrics,
                          baseline_spread=spread,best=best,signal=signal,features=decisions[0]['features'],
                          best_advantage=base-med[best]))
    signals=[x for x in cells if x['signal']]
    gate=len(signals)>=6 and len({x['scene'] for x in signals})>=2
    report=dict(checkpoints=len(cells),signal_count=len(signals),signal_families=sorted({x['scene'] for x in signals}),
                signal_gate=gate,native_seconds=native_spent(),cells=cells)
    if gate and not partial and len({x['scene'] for x in cells})>=3:
        X=np.array([x['features'] for x in cells]);Y=np.array([[x['auc'][0]-x['auc'][a] for a in [-1,0,1]] for x in cells]);groups=[x['scene'] for x in cells]
        pred,models=fit_predict(X,Y,groups)
        actions=[];advantages=[];const_adv=[];rule_adv=[]
        for i,x in enumerate(cells):
            j=max([1,0,2],key=lambda j:pred[i,j]);actions.append(j-1);advantages.append(Y[i,j])
            train=[n for n,g in enumerate(groups) if g!=groups[i]];c=max([1,0,2],key=lambda j:Y[train,j].mean());const_adv.append(Y[i,c])
            # Simple baseline: cancel a decade decrease after reaching CG cap.
            rule=2 if X[i,7]>=.99 else 1;rule_adv.append(Y[i,rule])
        modelgate=np.mean(advantages)>max(0,np.mean(const_adv),np.mean(rule_adv))
        report['model']=dict(actions=actions,mean_advantage=float(np.mean(advantages)),constant_mean_advantage=float(np.mean(const_adv)),
                             work_rule_mean_advantage=float(np.mean(rule_adv)),validation_gate=bool(modelgate),
                             family_advantages={g:float(np.mean([a for a,f in zip(advantages,groups) if f==g])) for g in sorted(set(groups))})
        put(ROOT/'family_models.json',models)
        if modelgate:
            mean=X.mean(0);sd=X.std(0);sd[sd<1e-8]=1.;Z=np.c_[np.clip((X-mean)/sd,-5,5),np.ones(len(X))]
            reg=np.eye(Z.shape[1])*10.;reg[-1,-1]=.01;W=np.linalg.solve(Z.T@Z+reg,Z.T@Y)
            (ROOT/'policy.txt').write_text('PRISM_RLD_LINEAR_V1 64\n'+' '.join(map(repr,mean.tolist()+sd.tolist()+W.T.flatten().tolist()))+'\n')
    put(ROOT/('partial.json' if partial else 'analysis.json'),report)
    print('SIGNAL',len(cells),'states',len(signals),'clear nonbaseline', 'gate',gate,report.get('model',''),flush=True)
    return report

def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['smoke','collect','analyze']);a=ap.parse_args()
    ROOT.mkdir(exist_ok=True);(ROOT/'runs').mkdir(exist_ok=True)
    if a.stage=='smoke':smoke()
    elif a.stage=='collect':collect();analyze()
    else:analyze()
if __name__=='__main__':main()
