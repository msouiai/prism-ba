"""Frozen largest-scene transfer, no policy fitting or target selection."""
import datetime,json,pathlib,shutil,statistics as st
import rl_damping_pilot as p
ROOT=pathlib.Path('/tmp/prism-rl-deep-eta2-large');REPO=pathlib.Path(__file__).parents[1]
PARENT=pathlib.Path('/tmp/prism-rl-deep-eta2');BIN=PARENT/'build/prism-tr'
SCENE='final-13682';TARGET=27591576.557625167
p.ROOT=ROOT;p.NATIVE_CAP=150
def read(path):return json.loads(pathlib.Path(path).read_text())
def register():
    ROOT.mkdir(exist_ok=True)
    previous=read(PARENT/'protocol.json');analysis=read(PARENT/'analysis.json')
    assert read(PARENT/'completion.json')['complete']
    assert p.sha(BIN)==previous['hashes'][str(BIN)]
    source=PARENT/'policy-full.txt';assert p.sha(source)==analysis['policy_hashes']['full']
    policy=ROOT/'policy.txt'
    if not policy.exists():shutil.copyfile(source,policy)
    assert p.sha(policy)==analysis['policy_hashes']['full']
    paths=[BIN,policy,p.DATA/(SCENE+'.txt'),REPO/'bench/rl_deep_eta2_large.py',
           REPO/'bench/rl_damping_pilot.py',REPO/'bench/audit_prism_state.py',
           REPO/'docs/rl_deep_eta2_large_protocol.md',p.SELECTED]
    hashes={str(q):p.sha(q) for q in paths}
    assert hashes[str(p.DATA/(SCENE+'.txt'))]=='76ef34416fdca524b1ec6755b62ab33cba15c8b5b830b5ff38369c8cd609d736'
    assert hashes[str(p.SELECTED)]==previous['hashes'][str(p.SELECTED)]
    obj=dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),hashes=hashes,
        target=TARGET,scene=SCENE,repeats=3,cap=20,lambda0=.1,eta=2,
        policy_parent_analysis_sha256=p.sha(PARENT/'analysis.json'),diagnostics=1)
    dest=ROOT/'protocol.json'
    if dest.exists():
        old=read(dest);assert all(old[k]==v for k,v in obj.items() if k!='time')
    else:p.put(dest,obj)
    return obj
def run():
    register();rows=[]
    for rep in range(3):
        names=['champion','learned'] if rep%2==0 else ['learned','champion']
        for arm in names:
            flags=dict(OCA_RLA_FIXED_ETA=2,OCA_TARGET_COST=TARGET,OCA_MAX_SECONDS=20)
            if arm=='learned':flags['OCA_RLD_POLICY']=str(ROOT/'policy.txt')
            r=p.run(f'{arm}-{rep}',SCENE,extra=flags,binary=BIN,initial_lambda=.1,
                    logging=False,iterations=600,process_timeout=180)
            rows.append(dict(arm=arm,rep=rep,target=TARGET,
                hit='target_seconds' in r and r['target_seconds']<=20 and r['audit_cost']<=TARGET,
                **{k:r.get(k) for k in ['name','target_seconds','seconds','audit_cost','audit_error','outers','rejects','matvecs']}))
            p.put(ROOT/'rows.json',rows)
            print('SCORED',rows[-1],flush=True)
    d=p.run('learned-diagnostic',SCENE,extra=dict(OCA_RLA_FIXED_ETA=2,OCA_TARGET_COST=TARGET,
        OCA_MAX_SECONDS=20,OCA_RLD_POLICY=str(ROOT/'policy.txt')),binary=BIN,initial_lambda=.1,
        logging=True,iterations=600,process_timeout=180)
    ds=[e for e in d['events'] if e['type']=='decision'];longest=streak=0
    for e in ds:
        streak=streak+1 if e['action']==1 else 0;longest=max(longest,streak)
    p.put(ROOT/'diagnostic.json',dict(decisions=ds,outer_events=[e for e in d['events'] if e['type']=='outer'],
        name=d['name'],positive_streak=longest,nonzero_actions=sum(e['action']!=0 for e in ds),
        exact_pathology_count=sum(abs(e['base_lambda']-.025)<1e-10 and abs(e['lambda']-.25)<1e-10 for e in ds),
        target_seconds=d.get('target_seconds'),cost=d['audit_cost'],outers=d['outers']))
    register()
    for folder in (ROOT/'runs').iterdir():
        r=read(folder/'result.json');assert p.sha(folder/'endpoint.state')==r['state_sha256']
    p.put(ROOT/'completion.json',dict(complete=True,timing_runs=6,diagnostics=1,
        endpoint_hashes_verified=7,native_seconds=p.native_spent()))
if __name__=='__main__':run()
