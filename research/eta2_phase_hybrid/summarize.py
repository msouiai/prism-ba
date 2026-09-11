#!/usr/bin/env python3
import pathlib,json,statistics,math,collections
P=pathlib.Path(__file__).resolve().parent
rows=[json.loads(f.read_text()) for f in (P/'evidence').glob('*/*/result.json')]
summary=[]
for stage in sorted({r['stage'] for r in rows}):
    if 'parity' in stage or stage in ['calibrate-large','handover-smoke']:continue
    for scene in sorted({r['scene'] for r in rows if r['stage']==stage}):
        groups={a:[r for r in rows if r['stage']==stage and r['scene']==scene and r['arm']==a] for a in sorted({r['arm'] for r in rows if r['stage']==stage and r['scene']==scene})}
        champ=groups.get('champion',[])
        for arm,rr in groups.items():
            matched_champ=[r for r in champ if r['rep'] in {v['rep'] for v in rr}]
            hit=[r['target_seconds'] for r in rr if r['hit']];ch=[r['target_seconds'] for r in matched_champ if r['hit']]
            speed=statistics.median(ch)/statistics.median(hit) if hit and len(hit)==len(rr) and len(ch)==len(rr) else None
            sweeps=[s for r in rr for s in r.get('sweeps',[])];valid=[s for s in sweeps if s['valid']=='1']
            summary.append(dict(stage=stage,scene=scene,arm=arm,n=len(rr),hits=len(hit),target=rr[0]['target'],
                hit_seconds_median=statistics.median(hit) if hit else None,hit_seconds_min=min(hit) if hit else None,hit_seconds_max=max(hit) if hit else None,unconditional_speedup=speed,comparison_champion_n=len(matched_champ),
                **{k:statistics.median(r.get(k,0) for r in rr) for k in ['accepted','rejects','matvecs','native_seconds','final_cost','hybrid_sweeps','hybrid_products','hybrid_seconds','hybrid_failures']},
                final_cost_min=min(r['final_cost'] for r in rr),final_cost_max=max(r['final_cost'] for r in rr),
                stopping=dict(collections.Counter(r['stop_reason'] for r in rr)),handover=dict(collections.Counter(r['handover_reason'] or 'none' for r in rr)),
                menu_observations=len(sweeps),valid_menus=len(valid),raw_collapsed=sum(float(s['raw'])<=.001 for s in valid),clipped_collapsed=sum(float(s['clipped'])<=.001 for s in valid),
                selected=dict(collections.Counter(s['selected'] for s in valid)),verified_products_total=5*len(valid)))
(P/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
for r in summary:print(r['stage'],r['scene'],r['arm'],f"{r['hits']}/{r['n']}",r['hit_seconds_median'],'speed',r['unconditional_speedup'],'handover',r['handover'])
