#!/usr/bin/env python3
"""Summarize the frozen CG-capture expansion and nonlinear screens."""
import argparse,json,pathlib,statistics
p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,default=pathlib.Path('/workspace/prism-recycle-cg'));a=p.parse_args();root=a.root
rows=[json.loads(p.read_text()) for p in sorted((root/'screen').glob('*.result.json'))]
assert len(rows)==12 and all(r['status']=='ok' for r in rows)
fields=['cost','seconds','iters','matvecs','scored','rejects','expansions','reuse_hits','fallbacks','retained_vectors']
groups=[]
for scene in ['ladybug-1197','dubrovnik-356']:
 for arm in ['legacy','rebuild','reuse']:
  rs=[r for r in rows if r['scene']==scene and r['arm']==arm];assert len(rs)==2
  groups.append(dict(scene=scene,arm=arm,**{f:statistics.median(r[f] for r in rs) for f in fields}))
audit=json.loads((root/'audit-summary.json').read_text());micro=[]
for scene in ['ladybug-1197','dubrovnik-356']:
 rs=[r for r in audit if r['scene']==scene];assert len(rs)==6
 valid=all(r['valid'] and r['residual']<=r['tolerance'] for r in rs)
 item=dict(scene=scene,all_valid=valid)
 for reuse in [0,1]:
  ms=[r for r in rs if r['reuse']==reuse];assert len(ms)==3
  item['reuse' if reuse else 'rebuild']={f:statistics.median(r[f] for r in ms) for f in ['seconds','matvecs','captured','depth']}
  item['reuse' if reuse else 'rebuild']['time_range']=[min(r['seconds'] for r in ms),max(r['seconds'] for r in ms)]
 item['speed_ratio']=item['rebuild']['seconds']/item['reuse']['seconds'] if valid else None
 item['max_relative_residual']=max(r['residual'] for r in rs);micro.append(item)
result=dict(runs=len(rows),native_seconds=sum(r['seconds'] for r in rows),max_audit_relerr=max(r['audit_relerr'] for r in rows),medians=groups,fixed_operator=micro)
(root/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
