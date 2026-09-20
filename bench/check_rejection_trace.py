#!/usr/bin/env python3
"""Check Armijo acceptance and rearming eligibility in experimental traces."""
import argparse,json,math
from collections import defaultdict
from pathlib import Path
from summarize_rejection_study import records
p=argparse.ArgumentParser();p.add_argument('paths',nargs='+',type=Path)
p.add_argument('--initial-confirm',action='store_true',help='Replay starts with backtracking disabled for original-policy confirmation')
a=p.parse_args();results=[]
for path in a.paths:
    rows=records(path);attempts={r['a']:r for r in rows if r['t']=='a'}
    enabled=not a.initial_confirm;last=None;on=off=0;bt=defaultdict(list);coverage=0
    for r in rows:
        if r['t']=='a':last=r
        if r['t']=='bt':
            assert enabled,(path,r)
            assert r['alpha']>0 and r['alpha']<=.5 and r['slope']<0
            assert math.isfinite(r['slope']);bt[r['a']].append(r)
        if r['t']=='bt_off':
            assert enabled;enabled=False;off+=1
        if r['t']=='bt_on':
            assert not enabled and last and last['acc'] and last['o']==r['o']
            assert last['a']==r['next_a']-1 and last['a'] not in bt
            # Standard timed/diagnostic protocol uses ftol=1e-5.
            assert r['rel']>1e-4
            assert abs(r['rel']-(last['cost0']-last['bcost'])/last['cost0'])<1e-8
            enabled=True;on+=1
        if r['t']=='coverage':coverage+=1
    rescues=0
    for ident,probes in bt.items():
        prev=1.;acceptable=[];cost=attempts[ident]['cost0']
        for i,r in enumerate(probes):
            assert abs(r['alpha']-prev*.5)<1e-12;prev=r['alpha']
            assert abs(r['bound']-(cost+1e-4*r['alpha']*r['slope']))<1e-7*max(1,cost)
            if r['cost'] is not None and r['cost']<cost and r['cost']<=r['bound']:acceptable.append(i)
        if acceptable:
            assert acceptable==[len(probes)-1],(path,ident,acceptable)
            assert attempts[ident]['acc'];rescues+=1
    results.append(dict(path=str(path),attempts=len(attempts),backtrack_trials=len(bt),rescues=rescues,rearms=on,confirmations=off,coverage_attempts=coverage))
print(json.dumps(results,indent=2))
