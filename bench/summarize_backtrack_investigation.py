#!/usr/bin/env python3
import argparse,json,pathlib,statistics

def main():
 p=argparse.ArgumentParser();p.add_argument('root',type=pathlib.Path);a=p.parse_args();root=a.root;stages={};allrows=[]
 for stage in ['trace','extra-trace','small','rejection-screen','venice-quality','medium','guarded','large']:
  path=root/stage/'results.json'
  if not path.exists():continue
  rows=json.loads(path.read_text());allrows.extend(rows)
  if not all('arm' in r for r in rows):continue
  result={}
  for scene in sorted({r['scene'] for r in rows}):
   arms={}
   for arm in sorted({r['arm'] for r in rows if r['scene']==scene}):
    rr=[r for r in rows if r['scene']==scene and r['arm']==arm]
    entry=dict(n=len(rr),**{k:statistics.median(r[k] for r in rr) for k in ['seconds','cost','actual_iters','matvecs','scored','backtrack','bt_trials','bt_rescues']})
    if 'target' in rr[0]:entry.update(target=rr[0]['target'],hits=sum(r['hit'] for r in rr),crossing_seconds=statistics.median(r['crossing_seconds'] for r in rr) if all(r['hit'] for r in rr) else None)
    arms[arm]=entry
   for arm,e in arms.items():
    if arm=='baseline' or 'baseline' not in arms:continue
    b=arms['baseline'];e['cost_ratio']=e['cost']/b['cost'];e['return_speedup']=b['seconds']/e['seconds']
    if e.get('crossing_seconds') and b.get('crossing_seconds'):e['crossing_speedup']=b['crossing_seconds']/e['crossing_seconds']
   result[scene]=arms
  stages[stage]=result
 result=dict(stages=stages,runs=len(allrows),native_seconds=sum(r['seconds'] for r in allrows),max_cpu_relative_error=max(r['audit_relerr'] for r in allrows),target_runs=sum('target' in r for r in allrows),target_hits=sum(r.get('hit',False) for r in allrows))
 if 'guarded' in stages:
  g=stages['guarded'];result['large_gate']=all(s['guarded']['hits']==s['guarded']['n'] and s['baseline']['hits']==s['baseline']['n'] and s['guarded'].get('crossing_speedup',0)>=1/1.1 for s in g.values()) and g['dubrovnik-356']['guarded'].get('crossing_speedup',0)>1.1
 (root/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
