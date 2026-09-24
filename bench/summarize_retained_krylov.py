#!/usr/bin/env python3
"""Summarize the frozen retained-basis screen without retuning it."""
import json,pathlib,statistics
root=pathlib.Path('/workspace/prism-recycle')
rows=[json.loads(p.read_text()) for p in sorted((root/'screen').glob('*.result.json'))]
assert len(rows)==12 and all(r['status']=='ok' for r in rows)
fields=['cost','seconds','matvecs','scored','rejects','expansions','reuse_hits','fallbacks','retained_vectors']
groups=[]
for scene in ['ladybug-1197','dubrovnik-356']:
 for arm in ['legacy','rebuild','reuse']:
  rs=[r for r in rows if r['scene']==scene and r['arm']==arm];assert len(rs)==2
  groups.append(dict(scene=scene,arm=arm,**{f:statistics.median(r[f] for r in rs) for f in fields}))
report={'runs':len(rows),'native_seconds':sum(r['seconds'] for r in rows),'max_audit_relerr':max(r['audit_relerr'] for r in rows),'medians':groups}
fixed=[json.loads(p.read_text()) for p in sorted((root/'fixed-work').glob('*.result.json'))]
assert len(fixed)==8 and all(r['status']=='ok' for r in fixed)
report['fixed_work_medians']=[]
for scene in ['ladybug-1197','dubrovnik-356']:
 for arm in ['rebuild','reuse']:
  rs=[r for r in fixed if r['scene']==scene and r['arm']==arm];assert len(rs)==2
  assert all(r['iters']<={'ladybug-1197':30,'dubrovnik-356':100}[scene] for r in rs)
  report['fixed_work_medians'].append(dict(scene=scene,arm=arm,iterations=[r['iters'] for r in rs],all_reached_cap=all(r['iters']=={'ladybug-1197':30,'dubrovnik-356':100}[scene] for r in rs),**{f:statistics.median(r[f] for r in rs) for f in fields}))
report['fixed_work_native_seconds']=sum(r['seconds'] for r in fixed)
report['all_max_audit_relerr']=max(r['audit_relerr'] for r in rows+fixed)
(root/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
