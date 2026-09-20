#!/usr/bin/env python3
"""Summarize retained subspace studies and verify recorded model diagnostics."""
import argparse,json,pathlib,re,math,statistics
p=argparse.ArgumentParser();p.add_argument('root',type=pathlib.Path);root=p.parse_args().root
stages={p.parent.name:json.loads(p.read_text()) for p in root.glob('*/results.json')};allrows=[r for rr in stages.values() for r in rr]
summary=dict(runs=len(allrows),native_seconds=sum(r['seconds'] for r in allrows),target_runs=sum('target' in r for r in allrows),hits=sum(r.get('hit',False) for r in allrows),max_cpu_error=max(r['audit_relerr'] for r in allrows),stages=stages,models={})
for stage,rr in stages.items():
 for r in rr:
  rows=[]
  for line in (root/stage/(r['name']+'.log')).read_text().splitlines():
   if not line.startswith('SUBSPACE o='):continue
   x={k:float(v) for k,v in re.findall(r'(\w+)=(\S+)',line)}
   error=abs(x['gc']+x['gp']-x['slope_check'])/max(1,abs(x['slope_check']));assert error<1e-7
   if x['mode']==5 and math.isfinite(x['error']):
    g=x['gc']+x['gp'];curv=x['cc']+2*x['cp']+x['pp']+2*x['error'];t=min(1,max(0,-g/curv)) if curv>0 else 0
    pred=-(g*t+.5*curv*t*t);assert x['pred']>=pred-1e-7*max(1,abs(pred))
   rows.append(x)
  if rows:summary['models'][stage+'/'+r['name']]=dict(calls=len(rows),median_a=statistics.median(x['a'] for x in rows),median_b=statistics.median(x['b'] for x in rows),nonuniform=sum(abs(x['a']-x['b'])>1e-8 for x in rows),accepted=sum(x['accepted'] for x in rows),max_slope_error=max(abs(x['gc']+x['gp']-x['slope_check'])/max(1,abs(x['slope_check'])) for x in rows))
(root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print({k:v for k,v in summary.items() if k not in ['stages','models']})
