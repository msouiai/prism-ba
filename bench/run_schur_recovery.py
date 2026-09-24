#!/usr/bin/env python3
"""Execute the predeclared bounded study, resuming completed cells safely."""
import json
import pathlib
import subprocess
import sys

ROOT=pathlib.Path('/workspace/prism-schur-recovery')
STUDY=pathlib.Path(__file__).with_name('schur_recovery_study.py')

def run(phase,*args):
    subprocess.run([sys.executable,str(STUDY),'--phase',phase,*args],check=True)

def main():
    # Calibration is completed before this orchestrator starts.
    assert (ROOT/'new-anchors.json').exists()
    run('compatibility','--reps','1')
    run('controls')
    run('extension')
    rows=json.loads((ROOT/'extension/results.json').read_text())
    scenes=list(dict.fromkeys(r['scene'] for r in rows))
    activated=[s for s in scenes if any(r.get('negcurv',0)>0 or r.get('numeric_rebuilds',0)>0 for r in rows if r['scene']==s)]
    ambiguous=[]
    for s in scenes:
        rr=[r for r in rows if r['scene']==s]
        near=any(r['valid'] and not r['hit'] and r.get('cost',float('inf'))<=r['target']*1.02 for r in rr)
        off=sum(r['hit'] for r in rr if r['arm']=='off')
        guard=sum(r['hit'] for r in rr if r['arm']=='rayleigh')
        if near or off!=guard:ambiguous.append(s)
    path=ROOT/'adaptive-followups.json'
    followups=dict(activated=activated,ambiguous=ambiguous,
                   rule='Exactly plan.json controls_scope and sensitivity_rule; no parameter tuning or early termination from outcomes.')
    if path.exists():assert json.loads(path.read_text())==followups
    else:path.write_text(json.dumps(followups,indent=2)+'\n')
    if activated:
        run('controls','--name','extension-controls','--scenes',*activated)
    for mult,label in [('1.005','half-percent'),('1.02','two-percent')]:
        run('sensitivity','--name','ladybug-'+label,'--scenes','ladybug-1723','--multiplier',mult,
            '--arms','off','x4','x4_floor','rayleigh','caspar32','caspar64')
        run('sensitivity','--name','trafalgar-'+label,'--scenes','trafalgar-126','--multiplier',mult)
        if ambiguous:
            run('sensitivity','--name','extension-'+label,'--scenes',*ambiguous,'--multiplier',mult)
    (ROOT/'COMPLETE.json').write_text(json.dumps(dict(complete=True,followups=followups),indent=2)+'\n')
    print('ALL PREDECLARED PHASES COMPLETE',flush=True)

if __name__=='__main__':main()
