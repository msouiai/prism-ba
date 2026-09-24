"""Round6: training-only deep coverage, longer returns, current champion."""
import argparse,datetime,json,os,pathlib,statistics as st,subprocess
import numpy as np
import rl_damping_pilot as p
ROOT=pathlib.Path('/tmp/prism-rl-deep-eta2');REPO=pathlib.Path(__file__).parents[1]
BIN=ROOT/'build/prism-tr';PARENT=pathlib.Path('/tmp/prism-rl-actor/build/prism-tr')
SHALLOW=['ladybug-49','dubrovnik-88','venice-52'];DEEP=['ladybug-598','dubrovnik-356']
TRANSFER={'trafalgar-126':(105579.58394455544,4),'final-1936':(5125687.352261469,8),
          'muell-gba146':(1946488.746262194,12)}
FAMILY={'ladybug-598':(182215.47143052,4),'dubrovnik-356':(731369.19169166,4),
        'venice-89':(306319.16867216,4)}
p.ROOT=ROOT;p.NATIVE_CAP=2000
def read(name):return json.loads((ROOT/name).read_text())
def put(name,value):p.put(ROOT/name,value)
def run(name,scene='ladybug-49',flags=None,iterations=600,logging=True,binary=BIN,**kw):
    return p.run(name,scene,extra=dict(OCA_RLA_FIXED_ETA=2,**(flags or {})),
        iterations=iterations,logging=logging,binary=binary,process_timeout=180,**kw)
def register():
    ROOT.mkdir(exist_ok=True);(ROOT/'checkpoints').mkdir(exist_ok=True)
    obj=dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        hashes={str(q):p.sha(q) for q in [pathlib.Path(__file__),REPO/'bench/rl_damping_pilot.py',
          REPO/'bench/audit_prism_state.py',REPO/'docs/rl_deep_eta2_protocol.md',
          REPO/'bench/build_rl_deep_eta2.py',BIN,PARENT,p.SELECTED]},
        data={s:p.sha(p.DATA/(s+'.txt')) for s in sorted(set(SHALLOW+DEEP+list(TRANSFER)+list(FAMILY)))},
        transfer=TRANSFER,family=FAMILY,eta=2,lambda0=.1,return_outers=32,repeats=3,promotion=1.10)
    if (ROOT/'protocol.json').exists():
        old=read('protocol.json');assert all(old[k]==json.loads(json.dumps(v)) for k,v in obj.items() if k!='time')
    else:put('protocol.json',obj)
def smoke():
    register();rows=[]
    for rep in range(3):
        for arm,binary,flags in [('parent',PARENT,{}),('new',BIN,{}),('zero',BIN,{'OCA_RLD_OPENING':0})]:
            rows.append(run(f'smoke-{arm}-{rep}',binary=binary,flags=flags,iterations=8))
    costs=[r['audit_cost'] for r in rows]
    assert (max(costs)-min(costs))/max(costs)<1e-7
    assert len({r['matvecs'] for r in rows})==1
    cp=ROOT/'checkpoints/smoke.cp'
    cont=run('smoke-continuous',flags={'OCA_RLD_SAVE':str(cp),'OCA_RLD_AT':4,'OCA_RLD_STEPS':32},iterations=36)
    refs=[e for e in cont['events'] if e['type']=='outer' and e['outer']>4]
    continuous=[cont]+[run('smoke-long-continuous-'+str(n),iterations=36) for n in [1,2]]
    continuous_work=[sum(e['matvecs'] for e in r['events'] if e['type']=='outer' and e['outer']>4) for r in continuous]
    restored=[]
    for rep in range(3):
        r=run(f'smoke-replay-{rep}',flags={'OCA_RLD_LOAD':str(cp),'OCA_RLD_ACTION':0,'OCA_RLD_STEPS':32})
        got=[e for e in r['events'] if e['type']=='outer'];assert len(got)==len(refs)
        for a,b in zip(refs[:4],got[:4]):
            for key in ['cost','lambda_used','lambda_next','rho','prediction']:
                assert abs(a[key]-b[key])/max(1,abs(a[key]))<1e-7,(key,a,b)
            assert all(a[k]==b[k] for k in ['cg','matvecs','rejects','repairs'])
        expected=next(e for e in cont['events'] if e['type']=='decision' and e['outer']==4)
        actual=next(e for e in r['events'] if e['type']=='decision')
        assert actual['features']==expected['features']
        assert min(continuous_work)<=sum(e['matvecs'] for e in got)<=max(continuous_work)
        restored.append(r['audit_cost'])
    endpoints=restored+[r['audit_cost'] for r in continuous]
    assert (max(endpoints)-min(endpoints))/max(endpoints)<1e-7
    bad=p.run('smoke-eta-mismatch',extra={'OCA_RLA_FIXED_ETA':1,'OCA_RLD_LOAD':str(cp)},
              binary=BIN,expect_fail=True,logging=True)
    opening=run('smoke-opening',flags={'OCA_RLD_OPENING':2},iterations=8)
    acts=[e['action'] for e in opening['events'] if e['type']=='decision']
    assert acts==[-1,-1]+[0]*(len(acts)-2)
    put('smoke.json',dict(passed=True,costs=costs,matvecs=rows[0]['matvecs'],
        replay_costs=restored,replay_outers=len(refs),continuous_costs=[r['audit_cost'] for r in continuous],
        continuous_work=continuous_work,eta_mismatch_rejected=bad['expected_failure'],opening_actions=acts))
    print('SMOKE PASSED',flush=True)
def select():
    assert read('smoke.json')['passed'];chosen=[];attempted=[]
    for scene in SHALLOW+DEEP:
        scout=None
        if scene in DEEP:
            scout=run('scout-'+scene,scene,{'OCA_MAX_SECONDS':10},iterations=100)
        wanted=[1,3,5,7] if scene in SHALLOW else [1,3]
        candidates=[]
        if scout:
            boundaries={e['outer'] for e in scout['events'] if e['type']=='decision'}
            candidates=[e['outer'] for e in scout['events'] if e['type']=='outer' and
                e['accepted'] and e['cg']>=64 and e['outer']>3 and e['outer'] in boundaries]
        selected_deep=[];tried=0
        for k in wanted+candidates:
            deep=k not in wanted
            if deep:
                if len(selected_deep)>=4 or tried>=8:break
                if any(abs(k-j)<3 for j in selected_deep):continue
                tried+=1
            cp=ROOT/'checkpoints'/f'{scene}-{k}.cp'
            r=run(f'capture-{scene}-{k}',scene,{'OCA_RLD_SAVE':str(cp),'OCA_RLD_AT':k,
                    'OCA_RLD_STEPS':1,'OCA_MAX_SECONDS':10},iterations=110)
            ds=[e for e in r['events'] if e['type']=='decision' and e['outer']==k]
            valid=cp.exists() and bool(ds) and (not deep or ds[0]['features'][7]>=.5)
            attempted.append(dict(scene=scene,k=k,deep_requested=deep,valid=bool(valid),
                saved_depth=ds[0]['features'][7]*128 if ds else None))
            put('capture_attempts.json',attempted)
            if not valid:
                assert deep,('missing shallow/early state',scene,k)
                continue
            if deep:selected_deep.append(k)
            chosen.append(dict(scene=scene,k=k,source='shallow' if scene in SHALLOW else 'deep-source',
                actual_deep=ds[0]['features'][7]>=.5,features=ds[0]['features'],
                checkpoint_sha256=p.sha(cp)))
        if scene in DEEP:assert len(selected_deep)>=2,('insufficient actual deep coverage',scene,selected_deep)
        print('COVERAGE',scene,len([c for c in chosen if c['scene']==scene]),'deep',len(selected_deep),flush=True)
        p.CACHE.clear()
    put('selection.json',chosen)
    print('FROZEN STATES',len(chosen),'deep',sum(c['actual_deep'] for c in chosen),flush=True)
def collect():
    register();cells=[]
    for cell in read('selection.json'):
        scene,k=cell['scene'],cell['k'];cp=ROOT/'checkpoints'/f'{scene}-{k}.cp'
        assert p.sha(cp)==cell['checkpoint_sha256'];branches=[]
        for rep in range(3):
            order=[0,-1,1];order=order[rep:]+order[:rep]
            for action in order:
                r=run(f'branch-{scene}-{k}-{action}-{rep}',scene,{'OCA_RLD_LOAD':str(cp),
                    'OCA_RLD_ACTION':action,'OCA_RLD_STEPS':32,'OCA_MAX_SECONDS':6})
                d=next(e for e in r['events'] if e['type']=='decision')
                assert d['outer']==k and d['action']==action and d['features']==cell['features']
                branches.append(dict(name=r['name'],action=action,rep=rep))
        cells.append(dict(**cell,branches=branches));put('collection.json',cells)
        print('COLLECTED',len(cells),'of',len(read('selection.json')),'native',p.native_spent(),flush=True)
        p.CACHE.clear()
def fit(X,Y):
    mean=X.mean(0);sd=X.std(0);sd[sd<1e-8]=1
    Z=np.c_[np.clip((X-mean)/sd,-5,5),np.ones(len(X))]
    reg=np.eye(65)*10;reg[-1,-1]=.01
    W=np.linalg.solve(Z.T@Z+reg,Z.T@Y)
    return dict(mean=mean.tolist(),sd=sd.tolist(),weights=W.tolist())
def export(name,m):
    vals=m['mean']+m['sd']+np.array(m['weights']).T.flatten().tolist()
    out='PRISM_RLD_LINEAR_V1 64\n'+' '.join(map(repr,vals))+'\n';dest=ROOT/name
    if dest.exists():assert dest.read_text()==out
    else:dest.write_text(out)
def analyze():
    cells=[]
    for c in read('collection.json'):
        rr=[(b,read('runs/'+b['name']+'/result.json')) for b in c['branches']]
        events=[[e for e in r['events'] if e['type']=='outer'] for _,r in rr]
        h=min(sum(e['dt'] for e in es) for es in events)
        h4=min(sum(e['dt'] for e in es[:4]) for es in events)
        auc={a:[] for a in [-1,0,1]};short={a:[] for a in auc}
        for b,r in rr:
            auc[b['action']].append(p.curve_score(r,h)['auc'])
            short[b['action']].append(p.curve_score(r,h4)['auc'])
        med={a:st.median(v) for a,v in auc.items()}
        cells.append(dict(**{k:v for k,v in c.items() if k!='branches'},horizon=h,short_horizon=h4,
            auc=med,auc_raw=auc,short_auc={a:st.median(v) for a,v in short.items()},
            lengths=[len(es) for es in events],best=min([0,-1,1],key=lambda a:med[a])))
    assert len(cells)==len(read('selection.json'))
    X=np.array([c['features'] for c in cells]);Y=np.array([[c['auc'][0]-c['auc'][a] for a in [-1,0,1]] for c in cells])
    groups=[c['scene'].split('-')[0] for c in cells]
    pred,models=p.fit_predict(X,Y,groups);actions=[max([1,0,2],key=lambda j:pred[i,j]) for i in range(len(X))]
    families={g:float(np.mean([Y[i,actions[i]] for i,h in enumerate(groups) if h==g])) for g in sorted(set(groups))}
    shallow=np.array([c['source']=='shallow' for c in cells])
    models['full']=fit(X,Y);models['shallow']=fit(X[shallow],Y[shallow])
    for name,m in models.items():export('policy-'+name+'.txt',m)
    put('models.json',models)
    put('analysis.json',dict(cells=cells,deep_states=int(sum(X[:,7]>=.5)),family_advantages=families,
        heldout_actions=[j-1 for j in actions],policy_hashes={name:p.sha(ROOT/('policy-'+name+'.txt')) for name in models},
        training_scenes=sorted(set(c['scene'] for c in cells)),selection_uses_transfer=False))
    print('FIT FROZEN',families,'deep',sum(X[:,7]>=.5),flush=True)
def parity():
    s=ROOT/'parity.cc';s.write_text('#include "rl_damping.h"\n#include <iostream>\nint main(){PrismRLDamping p;while(std::cin>>p.history[0]){for(int j=1;j<p.NX;++j)std::cin>>p.history[j];std::cout<<p.Action(1)<<"\\n";}}\n')
    subprocess.run(['g++','-O2','-std=c++17','-I'+str(ROOT/'build/headers'),str(s),'-o',str(ROOT/'parity')],check=True)
    X=np.array([c['features'] for c in read('analysis.json')['cells']])
    for name,m in read('models.json').items():
        pred=np.c_[np.clip((X-m['mean'])/m['sd'],-5,5),np.ones(len(X))]@np.array(m['weights'])
        expected=[max([1,0,2],key=lambda j:pred[i,j])-1 for i in range(len(X))]
        env={k:v for k,v in os.environ.items() if not k.startswith('OCA_')};env['OCA_RLD_POLICY']=str(ROOT/('policy-'+name+'.txt'))
        r=subprocess.run([str(ROOT/'parity')],input='\n'.join(' '.join(map(str,x)) for x in X),text=True,capture_output=True,env=env,check=True)
        assert list(map(int,r.stdout.split()))==expected,name
    put('parity.json',dict(passed=True,policies=len(read('models.json')),states=len(X)))
def evaluate(panel):
    register();parity();analysis=read('analysis.json')
    for n,h in analysis['policy_hashes'].items():assert p.sha(ROOT/('policy-'+n+'.txt'))==h
    rows=[];tasks=FAMILY if panel=='family' else TRANSFER
    for si,(scene,(target,cap)) in enumerate(tasks.items()):
        policy=scene.split('-')[0] if panel=='family' else 'full'
        arms={'champion':{},'learned':{'OCA_RLD_POLICY':str(ROOT/('policy-'+policy+'.txt'))},
              'opening-decay':{'OCA_RLD_OPENING':2}}
        if panel=='transfer':arms['shallow-learned']={'OCA_RLD_POLICY':str(ROOT/'policy-shallow.txt')}
        for rep in range(3):
            names=list(arms);i=(rep+si)%len(names);names=names[i:]+names[:i]
            for arm in names:
                r=run(f'{panel}-{scene}-{arm}-{rep}',scene,dict(OCA_TARGET_COST=target,OCA_MAX_SECONDS=cap,**arms[arm]),logging=False)
                row=dict(scene=scene,arm=arm,rep=rep,target=target,cap=cap,
                    hit='target_seconds' in r and r['target_seconds']<=cap and r['audit_cost']<=target,
                    **{k:r.get(k) for k in ['name','target_seconds','seconds','audit_cost','audit_error','outers','rejects','matvecs']})
                rows.append(row);put(panel+'-rows.json',rows)
                print('EVAL',panel,scene,arm,rep,row['hit'],row['target_seconds'],flush=True)
        p.CACHE.clear()
def diagnostic():
    old=pathlib.Path('/tmp/prism-rl-damping-extended/policy.txt')
    assert p.sha(old)=='011a21e025563d281eb4f5ab31dbc22762d9f62fed45890662897c79e8aba929'
    out={}
    for arm,flags in [('champion',{}),('learned',{'OCA_RLD_POLICY':str(ROOT/'policy-full.txt')}),
                      ('old-pathology',{'OCA_RLD_POLICY':str(old)})]:
        r=run('diagnostic-final1936-'+arm,'final-1936',dict(OCA_TARGET_COST=TRANSFER['final-1936'][0],OCA_MAX_SECONDS=8,**flags),iterations=32)
        ds=[e for e in r['events'] if e['type']=='decision'];streak=longest=0
        for e in ds:
            streak=streak+1 if e['action']==1 else 0;longest=max(streak,longest)
        out[arm]=dict(name=r['name'],decisions=ds,outers=r['outers'],cost=r['audit_cost'],
            exact_pathology_count=sum(abs(e['base_lambda']-.025)<1e-10 and abs(e['lambda']-.25)<1e-10 for e in ds),
            positive_streak=longest,old_policy_sha256=p.sha(old) if arm=='old-pathology' else None)
    put('diagnostic.json',out)
def all_stages():
    smoke();select();collect();analyze();evaluate('family');evaluate('transfer');diagnostic()
    put('completion.json',dict(complete=True,native_seconds=p.native_spent(),runs=len(list((ROOT/'runs').glob('*/result.json')))))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['register','smoke','select','collect','analyze','family','transfer','diagnostic','all']);a=ap.parse_args()
    if a.phase in ['family','transfer']:evaluate(a.phase)
    elif a.phase=='all':all_stages()
    else:globals()[a.phase]()
