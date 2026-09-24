#!/usr/bin/env python3
"""Relabel completed trajectories to expose reward-objective differences."""
import json,math,pathlib,statistics
ROOT=pathlib.Path('/tmp/prism-rl-curvature');OUT=pathlib.Path('/tmp/prism-rl-actor')
def main():
    rows=json.loads((ROOT/'training-rows.json').read_text());assert len(rows)==162 and all(r['hit'] for r in rows)
    scores={}
    for row in rows:
        rs=[r for r in rows if r['scene']==row['scene'] and r['lambda0']==row['lambda0'] and r['arm']=='baseline']
        ref=statistics.median(r['target_seconds'] for r in rs)
        r=json.loads((ROOT/'runs'/row['name']/'result.json').read_text());ev=[e for e in r['events'] if e['type']=='outer']
        F0=ev[0]['cost0'];target=row['target'];scale=math.log(F0/target)
        P=lambda cost:max(0,min(1,math.log(F0/max(cost,target))/scale))
        gain=sum(P(e['cost'])-P(e['cost0']) for e in ev)
        rate=sum((P(e['cost'])-P(e['cost0']))/(e['dt']/ref) for e in ev)
        value=dict(capped_gain=gain,uncapped_gain=math.log(F0/r['audit_cost'])/scale,
            summed_gain_rate=rate,negative_time=-row['target_seconds']/ref,
            shaped_time=1-row['target_seconds']/ref)
        assert abs(gain-1)<1e-9
        scores.setdefault(row['arm'],[]).append(value)
    summary={arm:{key:statistics.mean(r[key] for r in rs) for key in rs[0]} for arm,rs in scores.items()}
    winners={key:max(summary,key=lambda a:summary[a][key]) for key in ['uncapped_gain','summed_gain_rate','negative_time','shaped_time']}
    result=dict(episodes=len(rows),scores=summary,winners=winners,capped_gain_tied=True,
        caveat='Gain-rate relabeling uses legacy outer dt, excluding setup and some boundary overhead; diagnostic only. Target-time rewards use authoritative native TARGET timestamps. No policy refitting.')
    (OUT/'reward-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
