#!/usr/bin/env python3
"""Registered activation-selected late-stage diagnostic; not a speed ranking."""
import json
from speed_novelty_study import ROOT, read, put, register, run_one, observations, summary

def main():
    assert (ROOT/'COMPLETE.json').exists(), 'Finish the frozen speed panel first'
    proto=register()
    plan=read(ROOT/'late-diagnostic-plan.json')
    calibration=read(ROOT/'calibrate-rows.json')
    selected=[s for s in proto['scenes'] if any(r['scene']==s and r['arm']=='off' and r.get('negcurv',0)>0 for r in calibration)]
    assert plan['scenes']==selected
    rows=[]
    for scene in selected:
        dims,obs=observations(proto['scenes'][scene]['path'])
        for rep in range(1,plan['reps']+1):
            arms=plan['arms'];offset=(rep-1)%len(arms)
            for arm in arms[offset:]+arms[:offset]:
                rows.append(run_one(proto,'late-diagnostic',scene,arm,rep,plan['target'],plan['native_cap'],dims,obs,plan['iteration_cap']))
                put(ROOT/'late-diagnostic-rows.json',rows)
        del obs
    assert all(r['valid'] for r in rows),rows
    put(ROOT/'late-diagnostic-summary.json',summary(rows))
    print('DIAGNOSTIC COMPLETE',len(rows),flush=True)

if __name__=='__main__':
    main()
