#!/usr/bin/env python3
import argparse,json,pathlib,statistics
p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,default=pathlib.Path('/workspace/prism-recycle-selective'));a=p.parse_args();root=a.root
rows=[json.loads(p.read_text()) for p in sorted((root/'runs').glob('*.result.json'))]
targets=json.loads((root/'targets.json').read_text())
assert len(rows)==6*len(targets) and all(r['status']=='ok' for r in rows)
groups=[];ratios=[]
for scene in targets:
 arms={}
 for arm in ['legacy','always','selective']:
  rs=[r for r in rows if r['scene']==scene and r['arm']==arm];assert len(rs)==2
  hits=[r for r in rs if r['hit']]
  item=dict(scene=scene,arm=arm,hits=len(hits),target=rs[0]['target'],cap_seconds=rs[0]['cap_seconds'],median_crossing=statistics.median(r['crossing_seconds'] for r in hits) if len(hits)==2 else None,times=[r['crossing_seconds'] if r['hit'] else None for r in rs],costs=[r['cost'] for r in rs],matvecs=statistics.median(r['matvecs'] for r in rs),scored=statistics.median(r['scored'] for r in rs))
  for field in ['reuse_selected','cheap_skips','capacity_skips','cooldown_skips','capture_fallbacks']:item[field]=statistics.median(r[field] for r in rs)
  for field in ['seconds','cost','iters','rejects']:item['median_'+field]=statistics.median(r[field] for r in rs)
  item['stop_reasons']=[r['stop_reason'] for r in rs]
  arms[arm]=item;groups.append(item)
 for reference in ['legacy','always']:
  eligible=arms[reference]['hits']==arms['selective']['hits']==2
  ratios.append(dict(scene=scene,reference=reference,reference_over_selective=arms[reference]['median_crossing']/arms['selective']['median_crossing'] if eligible else None))
result=dict(runs=len(rows),native_seconds=sum(r['seconds'] for r in rows),max_audit_relerr=max(r['audit_relerr'] for r in rows),groups=groups,ratios=ratios)
(root/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
