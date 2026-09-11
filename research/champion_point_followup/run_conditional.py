#!/usr/bin/env python3
import json,statistics
from run_native import *
CB=P/'build_conditional/prism-followup'
ARMS.update(polish_gate={'OCA_FOLLOW_POINT':'1','OCA_FOLLOW_GATE':'1'},virtual_gate={'OCA_FOLLOW_POINT':'3','OCA_FOLLOW_GATE':'1'})
targets=json.loads((P/'calibrate-targets.json').read_text())['targets']
rows=[]
for s in SCENES:
    arms=['champion','polish_gate','virtual_gate']
    for rep in range(3):
        for a in arms[rep:]+arms[:rep]:rows.append(run(s,a,rep,'conditional',targets[s],binary=CB))
write(P/'conditional-results.json',rows)
# Numerics audit: all timings here are descriptive, not a candidate benchmark.
for rep in range(1,6):
    run('dubrovnik-88','champion',rep,'original-parity',binary=ORIGINAL,maxiter=8)
    run('dubrovnik-88','champion',rep,'off-parity',maxiter=8)
summary={}
for stage in ['original-parity','off-parity']:
    rs=[json.loads(f.read_text()) for f in (P/'evidence'/stage).glob('dubrovnik-88*/result.json')]
    vals=[r['final_cost'] for r in rs];summary[stage]=dict(n=len(rs),values=vals,min=min(vals),max=max(vals),median=statistics.median(vals),outers=[r['outers'] for r in rs],matvecs=[r['matvecs'] for r in rs])
a=summary['original-parity'];b=summary['off-parity']
summary.update(initial_assertion_failed=True,initial_relative_difference=3.977875966176825e-6,initial_tolerance=1e-6,overlap=max(a['min'],b['min'])<=min(a['max'],b['max']),bitwise_equivalence_claim=False)
write(P/'off_parity.json',summary)
for rep in range(10):
    # Rotate binaries. Same target, cap, scene, and flags.
    order=[('original-target-repeat',ORIGINAL),('generated-target-repeat',BINARY)]
    for stage,b in order[rep%2:]+order[:rep%2]:run('venice-52','champion',rep,stage,targets['venice-52'],binary=b)
