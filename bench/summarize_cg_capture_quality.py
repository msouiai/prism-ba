#!/usr/bin/env python3
import argparse,json,pathlib,statistics
p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,default=pathlib.Path('/workspace/prism-recycle-cg-fast'));a=p.parse_args();root=a.root
rows=[json.loads(p.read_text()) for p in sorted((root/'runs').glob('*.result.json'))]
assert len(rows)==12 and all(r['status']=='ok' for r in rows)
groups=[];ratios=[]
for scene in ['ladybug-1197','dubrovnik-356']:
 arms={}
 for arm in ['legacy','checked','fast']:
  rs=[r for r in rows if r['scene']==scene and r['arm']==arm];assert len(rs)==2
  hits=[r for r in rs if r['hit']]
  item=dict(scene=scene,arm=arm,hits=len(hits),target=rs[0]['target'],cap_seconds=rs[0]['cap_seconds'],median_crossing=statistics.median(r['crossing_seconds'] for r in hits) if len(hits)==2 else None,times=[r['crossing_seconds'] if r['hit'] else None for r in rs],costs=[r['cost'] for r in rs],matvecs=statistics.median(r['matvecs'] for r in rs),scored=statistics.median(r['scored'] for r in rs))
  arms[arm]=item;groups.append(item)
 for reference in ['legacy','checked']:
  eligible=arms[reference]['hits']==arms['fast']['hits']==2
  ratios.append(dict(scene=scene,reference=reference,reference_over_fast=arms[reference]['median_crossing']/arms['fast']['median_crossing'] if eligible else None))
result=dict(runs=12,native_seconds=sum(r['seconds'] for r in rows),max_audit_relerr=max(r['audit_relerr'] for r in rows),groups=groups,ratios=ratios)
(root/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
