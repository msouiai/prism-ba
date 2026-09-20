#!/usr/bin/env python3
import argparse,json,pathlib,statistics

def main():
 p=argparse.ArgumentParser();p.add_argument('root',type=pathlib.Path);a=p.parse_args();root=a.root;stages={};allrows=[]
 for path in sorted(root.glob('*/results.json')):
  rows=json.loads(path.read_text());allrows.extend(rows);result={}
  for scene in sorted({r['scene'] for r in rows}):
   arms={}
   for arm in sorted({r['arm'] for r in rows if r['scene']==scene}):
    rr=[r for r in rows if r['scene']==scene and r['arm']==arm]
    keys=['seconds','cost','actual_iters','matvecs','scored','backtrack','bt_trials','bt_rescues']
    keys += [k for k in ['upward_probes','upward_wins'] if all(k in x for x in rr)]
    e=dict(n=len(rr),**{k:statistics.median(r[k] for r in rr) for k in keys})
    if 'target' in rr[0]:e.update(target=rr[0]['target'],hits=sum(r['hit'] for r in rr),crossing_seconds=statistics.median(r['crossing_seconds'] for r in rr) if all(r['hit'] for r in rr) else None)
    arms[arm]=e
   for arm,e in arms.items():
    ref='baseline' if 'baseline' in arms else arm.replace('_candidate','_base')
    if arm==ref or ref not in arms:continue
    b=arms[ref];e.update(cost_ratio=e['cost']/b['cost'],return_speedup=b['seconds']/e['seconds'])
    if e.get('crossing_seconds') and b.get('crossing_seconds'):e['crossing_speedup']=b['crossing_seconds']/e['crossing_seconds']
   result[scene]=arms
  stages[path.parent.name]=result
 summary=dict(stages=stages,runs=len(allrows),native_seconds=sum(r['seconds'] for r in allrows),max_cpu_relative_error=max(r['audit_relerr'] for r in allrows),target_runs=sum('target' in r for r in allrows),target_hits=sum(r.get('hit',False) for r in allrows))
 if 'revision' in stages:
  rr=stages['revision'];summary['large_gate']=all(s['weak_upward']['hits']==s['weak_upward']['n'] and s['baseline']['hits']==s['baseline']['n'] and s['weak_upward'].get('crossing_speedup',0)>=1/1.1 for s in rr.values()) and rr['dubrovnik-356']['weak_upward'].get('crossing_speedup',0)>1.1
 (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
