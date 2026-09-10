#!/usr/bin/env python3
"""Frozen single/five/Caspar timing ablation and separately labelled profiles."""
import json, pathlib, shutil
import expanded_caspar_screen as engine

ROOT = pathlib.Path('/workspace/prism-menu-ablation')
SCENES = [('trafalgar-126',104534.24152926281,4),
          ('dubrovnik-88',359003.9111293723,4),
          ('final-1936',5074937.9725361075,12)]

def main():
    ROOT.mkdir(exist_ok=True)
    engine.ROOT = ROOT
    jobs=[]
    for rep in range(3):
        for i in range(3):
            scene,nominal,cap=SCENES[(i+rep)%3]
            arms=['single','five','caspar64']
            offset=(rep+i)%3
            for arm in arms[offset:]+arms[:offset]:
                jobs.append(dict(name=f'{scene}-{arm}-{rep+1}',scene=scene,arm=arm,
                    rep=rep+1,cap=cap,target=nominal*(1-1e-8),prism_stop_target=nominal,
                    nominal_target=nominal,profile=False,learn_log=False,process_timeout=90,
                    cpu_cache='/workspace/prism-caspar-expanded/cpu-cache'))
    profiles=[]
    for scene,nominal,cap in SCENES:
        for arm in ['single','five']:
            profiles.append(dict(name=f'{scene}-{arm}-profile',scene=scene,arm=arm,
                rep=0,cap=cap,target=nominal*(1-1e-8),prism_stop_target=nominal,
                nominal_target=nominal,profile=True,learn_log=True,process_timeout=90,
                cpu_cache='/workspace/prism-caspar-expanded/cpu-cache'))
    source=pathlib.Path(__file__).parent
    files=['menu_caspar_ablation.py','early_restart_screen.py','current_caspar_comparison.py',
           'expanded_caspar_screen.py','cached_benchmark_input.py','audit_prism_state.py',
           'profile_iterations.py','novelty_ablation.py']
    protocol=dict(jobs=jobs,profiles=profiles,prism_sha256=engine.sha(engine.PRISM),
        caspar_sha256=engine.sha(engine.CASPAR),
        data_sha256={s:engine.sha(pathlib.Path('/workspace/bal')/(s+'.txt')) for s,_,_ in SCENES},
        tooling_sha256={f:engine.sha(source/f) for f in files},
        timing='27 unprofiled native solve times; 6 separate synchronized diagnostic profiles. Process walls have different audit/setup scopes.',
        certification='Both native stopping tests and independent CPU endpoint use nominal*(1-1e-8).',
        selection='Previously chosen contrasting original medium targets; no new calibration or tuning.',
        ranking='Certified hits first, then median time for 3/3 hits; within 5% is a timing tie.')
    pp=ROOT/'protocol.json'
    if pp.exists(): assert json.loads(pp.read_text())==protocol
    else:
        engine.write(pp,protocol)
        (ROOT/'tooling').mkdir(exist_ok=True)
        for f in files: shutil.copy2(source/f,ROOT/'tooling'/f)
    for phase,plan in [('measurements',jobs),('profiles',profiles)]:
        rows=[]
        for j in plan:
            assert engine.sha(engine.PRISM)==protocol['prism_sha256']
            assert engine.sha(engine.CASPAR)==protocol['caspar_sha256']
            rows.append(engine.run(j,phase))
            engine.write(ROOT/(phase+'-results.json'),rows)
        assert all(r['status']=='ok' for r in rows), 'Failures retained; inspect before continuing'
    print('COMPLETE: 27 unprofiled comparisons + 6 separate profiles',flush=True)

if __name__=='__main__': main()
