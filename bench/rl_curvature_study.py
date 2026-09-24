#!/usr/bin/env python3
"""Registered feature ablation and complete-episode finite policy search."""
import argparse,json,math,pathlib,statistics,shutil
import rl_damping_trajectory as t
import rl_damping_pilot as p

ROOT=pathlib.Path('/tmp/prism-rl-curvature');BIN=ROOT/'build/prism-tr'
PARENT=pathlib.Path('/tmp/prism-rl-damping-trajectory/build-v2/prism-tr')
p.ROOT=ROOT;p.NATIVE_CAP=660;t.ROOT=ROOT;t.BIN=BIN

def policies():
    folder=ROOT/'policies';folder.mkdir(exist_ok=True)
    out={}
    for kind,use in [('plain',0),('curv',1)]:
        for label,mode in [('down',1),('mixed',3)]:
            for gate,rho,alpha in [('lenient',.75,1.5),('strict',.95,3)]:
                name=f'{kind}-{label}-{gate}';path=folder/(name+'.txt')
                text=f'PRISM_RLC_V1 {use} {mode} 2 {rho} {alpha} 100\n'
                if path.exists():assert path.read_text()==text
                else:path.write_text(text)
                out[name]={'OCA_RLC_POLICY':str(path)}
    return out

def smoke():
    rows=[]
    for rep in range(3):
        for name,binary,extra,logging in [('parent',PARENT,{},False),('off',BIN,{},False),
                ('collect',BIN,{'OCA_RLC_COLLECT':1},True)]:
            rows.append(p.run(f'smoke-{name}-{rep}',binary=binary,extra=extra,logging=logging))
    assert len({(r['matvecs'],r['outers'],r['rejects']) for r in rows})==1
    costs=[r['audit_cost'] for r in rows];assert (max(costs)-min(costs))/max(costs)<1e-7
    for r in rows:
        ev={e['outer']:e for e in r['events'] if e['type']=='outer'}
        for c in (e for e in r['events'] if e['type']=='curvature'):
            pred=-c['slope']-.5*c['curvature']
            assert abs(pred-ev[c['outer']]['prediction'])<1e-10*max(1,abs(pred))
            assert c['depth']>=0 and (not c['spectrum_valid'] or c['depth']>=4)
    r=p.run('smoke-active',binary=BIN,extra=policies()['curv-mixed-lenient'],logging=True,iterations=12)
    ds=[e for e in r['events'] if e['type']=='decision' and e['action']]
    assert len(ds)<=2 and all(b['outer']-a['outer']>=2 for a,b in zip(ds,ds[1:]))
    p.put(ROOT/'smoke.json',dict(passed=True,binary_sha256=p.sha(BIN),costs=costs,
        work=[(r['outers'],r['rejects'],r['matvecs']) for r in rows],active_actions=ds))
    print('SMOKE PASS',flush=True)

def train():
    assert json.loads((ROOT/'smoke.json').read_text())['binary_sha256']==p.sha(BIN)
    arms={'baseline':{'OCA_RLC_COLLECT':1},**policies()}
    proto=dict(scenes=t.TRAIN,initial_lambdas=[.1,10.],reps=3,arms=arms,binary_sha256=p.sha(BIN),
        policy_sha256={a:p.sha(f['OCA_RLC_POLICY']) for a,f in arms.items() if 'OCA_RLC_POLICY' in f},
        protocol_sha256=p.sha(pathlib.Path(__file__).parents[1]/'docs/rl_curvature_protocol.md'))
    dest=ROOT/'training-protocol.json'
    if dest.exists():assert json.loads(dest.read_text())==json.loads(json.dumps(proto))
    else:p.put(dest,proto)
    rows=[]
    for rep in range(3):
        for si,(scene,(target,cap)) in enumerate(t.TRAIN.items()):
            for li,lam in enumerate([.1,10.]):
                names=list(arms);off=(rep+si+li)%len(names);names=names[off:]+names[:off]
                for arm in names:
                    r=t.run(f'train-{scene}-l{lam}-{arm}-{rep}',scene,
                        dict(OCA_TARGET_COST=target,OCA_MAX_SECONDS=cap,**arms[arm]),lam,logging=True)
                    rr=t.row(r,scene,lam,arm,rep,target,cap)
                    rr['actions']=sum(bool(e['action']) for e in r['events'] if e['type']=='decision')
                    rows.append(rr);p.put(ROOT/'training-rows.json',rows)
                t.summarize(rows,'training-summary.json')
                print('TRAIN TASK',scene,lam,rep,'episodes',len(rows),'native',p.native_spent(),flush=True)

def select():
    rows=json.loads((ROOT/'training-rows.json').read_text());assert len(rows)==162
    names=['baseline']+list(policies());loss={a:{} for a in names}
    for scene in t.TRAIN:
        for lam in [.1,10.]:
            rs=[r for r in rows if r['scene']==scene and r['lambda0']==lam]
            base=[r for r in rs if r['arm']=='baseline'];assert all(r['hit'] for r in base)
            denom=statistics.median(r['target_seconds'] for r in base)
            for arm in names:
                vs=[r for r in rs if r['arm']==arm];assert len(vs)==3
                loss[arm][f'{scene}/{lam}']=statistics.mean(math.log((r['target_seconds'] if r['hit'] else 4*r['cap'])/denom) for r in vs)
    scores={a:statistics.mean(v.values()) for a,v in loss.items()};selection={}
    for kind in ['plain','curv']:
        candidates=[a for a in names if a.startswith(kind+'-')]
        selected=min(candidates,key=lambda a:scores[a]);family={}
        for held in t.TRAIN:
            winner=min(['baseline']+candidates,key=lambda a:statistics.mean(v for task,v in loss[a].items() if not task.startswith(held+'/')))
            family[held]=dict(selected=winner,loss=statistics.mean(v for task,v in loss[winner].items() if task.startswith(held+'/')),
                baseline_loss=statistics.mean(v for task,v in loss['baseline'].items() if task.startswith(held+'/')))
        dst=ROOT/f'selected-{kind}.txt';src=pathlib.Path(policies()[selected]['OCA_RLC_POLICY'])
        if dst.exists():assert dst.read_bytes()==src.read_bytes()
        else:shutil.copy2(src,dst)
        selection[kind]=dict(selected=selected,training_choice=min(['baseline']+candidates,key=lambda a:scores[a]),
            family_holdout=family,policy_sha256=p.sha(dst))
    p.put(ROOT/'selection.json',dict(scores=scores,task_losses=loss,selection=selection))
    print('SELECTION',json.dumps(selection),flush=True)

def evaluation(large=False):
    sel=json.loads((ROOT/'selection.json').read_text())['selection']
    for kind in sel:assert p.sha(ROOT/f'selected-{kind}.txt')==sel[kind]['policy_sha256']
    old=ROOT/'old-cap-2.txt'
    if not old.exists():old.write_text('PRISM_RLD_EPISODE_V1 2 2 .95 .125 1\n')
    arms={'baseline':{},'old-cap-2':{'OCA_RLD_EPISODE':str(old)},
          'selected-plain':{'OCA_RLC_POLICY':str(ROOT/'selected-plain.txt')},
          'selected-curv':{'OCA_RLC_POLICY':str(ROOT/'selected-curv.txt')},
          'deterministic':policies()['curv-mixed-lenient']}
    tasks=[(t.LARGE,.1,t.LARGE_TARGET,20)] if large else [
        (scene,.1,target,cap) for scene,(target,cap) in t.TRANSFER.items()]+[
        ('muell-gba146',10.,*t.TRANSFER['muell-gba146'])]
    phase='large' if large else 'transfer';proto=dict(tasks=tasks,arms=arms,reps=3,binary_sha256=p.sha(BIN),
        selection_sha256=p.sha(ROOT/'selection.json'),logging=False)
    path=ROOT/f'{phase}-protocol.json'
    if path.exists():assert json.loads(path.read_text())==json.loads(json.dumps(proto))
    else:p.put(path,proto)
    # Identical controller bytes share measurements and are declared aliases.
    aliases={};seen={}
    for arm,flags in arms.items():
        signature=json.dumps({k:(pathlib.Path(v).read_text() if k.endswith('POLICY') else v) for k,v in flags.items()},sort_keys=True)
        if signature in seen:aliases[arm]=seen[signature]
        else:seen[signature]=arm
    p.put(ROOT/f'{phase}-aliases.json',aliases)
    rows=[]
    for rep in range(3):
        for si,(scene,lam,target,cap) in enumerate(tasks):
            names=[a for a in arms if a not in aliases];off=(rep+si)%len(names);names=names[off:]+names[:off]
            for arm in names:
                r=t.run(f'{phase}-{scene}-l{lam}-{arm}-{rep}',scene,
                    dict(OCA_TARGET_COST=target,OCA_MAX_SECONDS=cap,**arms[arm]),lam,logging=False)
                rows.append(t.row(r,scene,lam,arm,rep,target,cap));p.put(ROOT/f'{phase}-rows.json',rows)
                cs=t.summarize(rows,f'{phase}-summary.json')
                print(phase.upper(),scene,lam,arm,rep,'hit',rows[-1]['hit'],'time',rows[-1]['target_seconds'],flush=True)
    # One per task, never included in the N=3 timing panel.
    diag=[]
    for scene,lam,target,cap in tasks:
        r=t.run(f'diagnostic-{scene}-l{lam}',scene,dict(OCA_TARGET_COST=target,OCA_MAX_SECONDS=cap,
            **arms['selected-curv']),lam,logging=True)
        diag.append(dict(scene=scene,lambda0=lam,events=r['events'],name=r['name']))
    p.put(ROOT/f'{phase}-diagnostics.json',diag)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['smoke','train','select','transfer','large']);a=ap.parse_args()
    ROOT.mkdir(exist_ok=True)
    if a.stage in ['transfer','large']:evaluation(a.stage=='large')
    else:globals()[a.stage]()
