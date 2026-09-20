#!/usr/bin/env python3
"""Preregistered global forcing configuration confirmation, no policy fitting."""
import argparse, datetime, json, pathlib
import rl_damping_pilot as p
import rl_damping_trajectory as t
import schur_recovery_study as s
ROOT=pathlib.Path('/tmp/prism-rl-sustained')
BIN=pathlib.Path('/tmp/prism-rl-actor/build/prism-tr')
p.ROOT=ROOT; p.NATIVE_CAP=400; t.ROOT=ROOT
def read(path):return json.loads(pathlib.Path(path).read_text())
def register():
    ROOT.mkdir(exist_ok=True)
    path=ROOT/'protocol.json'
    if path.exists():return read(path)
    tasks=[dict(scene=sc,target=q,cap=cap,reps=5,panel='primary') for sc,(q,cap) in t.TRANSFER.items()]
    tasks.append(dict(scene=t.LARGE,target=t.LARGE_TARGET,cap=20,reps=5,panel='primary'))
    old=read('/workspace/prism-expanded10-convergence/protocol.json')
    for sc in ['final-871','venice-951']:
        v=old['scenes'][sc];tasks.append(dict(scene=sc,target=v['target'],cap=v['cap'],reps=3,panel='extension'))
    tasks.append(dict(scene=t.LARGE,target=27318392.631312046,cap=20,reps=3,panel='tighter'))
    hashes={sc:p.sha(p.DATA/(sc+'.txt')) for sc in dict.fromkeys(x['scene'] for x in tasks)}
    for sc in ['final-871','venice-951']:assert hashes[sc]==old['scenes'][sc]['input_sha256']
    historical=read('/workspace/prism-final13682-convergence/protocol.json')
    assert hashes[t.LARGE]==historical['scenes'][t.LARGE]['input_sha256']
    proto=dict(registered=datetime.datetime.now(datetime.timezone.utc).isoformat(),tasks=tasks,
        binaries={a:p.sha(b) for a,b in dict(prism=BIN,caspar32=s.BINS['caspar32'],caspar64=s.BINS['caspar64']).items()},
        scenes={sc:dict(input_sha256=h) for sc,h in hashes.items()},audit_relative_tolerance=1e-7,
        candidate=dict(lambda0=.1,flags={'OCA_RLA_FIXED_ETA':2}),incumbent_lambda={'muell-gba146':10.,'otherwise':.1},
        flags=read(p.SELECTED)['flags'],code_sha256=p.sha(__file__),
        protocol_sha256=p.sha(pathlib.Path(__file__).parents[1]/'docs/rl_sustained_protocol.md'))
    p.put(path,proto);return proto
def run():
    proto=register();assert proto['code_sha256']==p.sha(__file__)
    assert proto['binaries']['prism']==p.sha(BIN)
    for sc,m in proto['scenes'].items():assert p.sha(p.DATA/(sc+'.txt'))==m['input_sha256']
    rows=[]
    for ti,task in enumerate(proto['tasks']):
        sc=task['scene']
        for rep in range(task['reps']):
            names=['incumbent','eta2']
            if (ti+rep)%2:names.reverse()
            for arm in names:
                lam=10. if arm=='incumbent' and sc=='muell-gba146' else .1
                flags=dict(OCA_TARGET_COST=task['target'],OCA_MAX_SECONDS=task['cap'])
                if arm=='eta2':flags['OCA_RLA_FIXED_ETA']=2
                r=p.run(f'{task["panel"]}-{sc}-{arm}-{rep}',sc,extra=flags,initial_lambda=lam,
                    binary=BIN,logging=False,iterations=600,process_timeout=180 if sc==t.LARGE else 45)
                rr=t.row(r,sc,lam,arm,rep,task['target'],task['cap']);rr['panel']=task['panel'];rows.append(rr)
                p.put(ROOT/'rows.json',rows)
                print('CONFIRM',task['panel'],sc,arm,rep,rr['hit'],rr['target_seconds'],flush=True)
        p.CACHE.clear()
    folder=ROOT/'caspar';folder.mkdir(exist_ok=True)
    _,(dims,obs)=p.data(t.LARGE)
    for rep in range(3):
        for arm in (['caspar32','caspar64'] if rep%2==0 else ['caspar64','caspar32']):
            assert p.sha(s.BINS[arm])==proto['binaries'][arm]
            spent=p.native_spent()+sum(read(q).get('seconds',0) for q in folder.glob('*.result.json'))
            assert spent<400
            r=s.run_one(folder,t.LARGE,arm,rep+1,t.LARGE_TARGET,20,dims,obs,proto)
            assert r['valid'],r
            rows.append(dict(scene=t.LARGE,lambda0=None,arm=arm,rep=rep,panel='caspar',target=t.LARGE_TARGET,
                cap=20,hit=r['hit'],target_seconds=r['crossing'],seconds=r['seconds'],audit_cost=r['cost'],
                outers=r['outers'],rejects=r['rejects'],matvecs=None,audit_error=r['audit_error'],
                setup_seconds=r['setup_seconds'],artifact=r['artifact']))
            p.put(ROOT/'rows.json',rows)
    print('COMPLETE',len(rows),'runs',flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['register','run']);a=ap.parse_args()
    if a.phase=='register':register()
    else:run()
