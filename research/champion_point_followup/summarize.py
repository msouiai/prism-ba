import pathlib,json,statistics,math
P=pathlib.Path(__file__).resolve().parent
med=statistics.median
rows=[json.loads(p.read_text()) for p in (P/'evidence/screen').glob('*/result.json')]
summary=[]
for a in sorted({r['arm'] for r in rows}):
    scenes=[]
    for s in sorted({r['scene'] for r in rows}):
        rr=[r for r in rows if r['arm']==a and r['scene']==s];bb=[r for r in rows if r['arm']=='champion' and r['scene']==s]
        if not rr or not bb:continue
        hit=[r for r in rr if r['hit']];bh=[r for r in bb if r['hit']]
        speed=med(r['target_seconds'] for r in bh)/med(r['target_seconds'] for r in hit) if len(hit)==len(rr) and len(bh)==len(bb) else None
        scenes.append(dict(scene=s,n=len(rr),hits=len(hit),seconds=med(r['target_seconds'] for r in hit) if hit else None,speedup=speed,outers=med(r['outers'] for r in rr),rejects=med(r['rejects'] for r in rr),matvecs=med(r.get('matvecs',0) for r in rr),overlay_seconds=med(r.get('overlay_seconds',0) for r in rr),overlay_selected=med(r.get('overlay_selected',0) for r in rr),overlay_calls=med(r.get('overlay_calls',0) for r in rr)))
    speeds=[r['speedup'] for r in scenes if r['speedup'] is not None];gm=math.exp(sum(map(math.log,speeds))/len(speeds)) if speeds else None
    passed=len(speeds)==3 and gm>=1.1 and min(speeds)>=1/1.2 and all(r['n']==3 for r in scenes)
    summary.append(dict(arm=a,geomean_speedup=gm,extension_gate=passed,scenes=scenes))
(P/'screen_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
for row in summary:print(row['arm'],row['geomean_speedup'],row['extension_gate'],[(s['scene'],s['hits'],s['speedup']) for s in row['scenes']])
if (P/'holdout_results.json').exists():
    rows=json.loads((P/'holdout_results.json').read_text());out=[]
    for f in sorted({r['family'] for r in rows}):
        for a in ['xyz','virtual_ray','observed_polish']:
            rs=[r for r in rows if r['family']==f and r['arm']==a];ratios=[]
            for id_ in sorted({r['id'] for r in rs}):
                x=[r for r in rs if r['id']==id_];b=[r for r in rows if r['id']==id_ and r['arm']=='xyz']
                if all(r['hit'] for r in x+b):ratios.append(med(r['seconds'] for r in b)/med(r['seconds'] for r in x))
            out.append(dict(family=f,arm=a,runs=len(rs),hits=sum(r['hit'] for r in rs),median_speedup=med(ratios) if ratios else None,paired_cases=len(ratios),**{k:med(r[k] for r in rs) for k in ['accepted','rejected','point_nrmse','camera_nrmse']}))
    (P/'holdout_summary.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
