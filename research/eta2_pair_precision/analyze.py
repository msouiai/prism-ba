#!/usr/bin/env python3
"""Rebuild registered summaries and paired screen gates from every raw row."""
import json,statistics
from pathlib import Path
P=Path(__file__).resolve().parent
def med(v):return statistics.median(v) if v else None
def span(v):return [min(v),max(v)] if v else None
def main():
    rows=[json.loads(f.read_text()) for f in sorted((P/'evidence').glob('*/*/result.json'))]
    groups=[]
    for key in sorted({(r['stage'],r['scene'],r['arm']) for r in rows}):
        rr=[r for r in rows if (r['stage'],r['scene'],r['arm'])==key]
        valid=[r for r in rr if r['valid']];hits=[r['target_seconds'] for r in valid if r['hit']]
        witnesses=[r for r in valid if any(t['kind']==1 and t['cost']>r['target'] for t in r.get('triggers',[]))] if rr[0]['target'] else []
        groups.append(dict(stage=key[0],scene=key[1],arm=key[2],n=len(rr),valid=len(valid),hits=len(hits),
            conditional_seconds=med(hits),conditional_range=span(hits),
            endpoint_median=med([r['cost'] for r in valid]),endpoint_range=span([r['cost'] for r in valid]),
            native_median=med([r['native_seconds'] for r in valid]),native_range=span([r['native_seconds'] for r in valid]),
            outers_median=med([r['outers'] for r in valid]),rejects_median=med([r['rejects'] for r in valid]),
            matvecs_median=med([r['matvecs'] for r in valid]),cap_hits=sum(r['cap_hit'] for r in valid),
            probes=sum(len(r.get('probes',[])) for r in valid),
            probe_accepts=sum(p['accept'] for r in valid for p in r.get('probes',[])),
            probe_truncations=sum(p['trunc'] for r in valid for p in r.get('probes',[])),
            stop_miss_witnesses=len(witnesses),stop_miss_witnesses_rescued=sum(r['hit'] for r in witnesses)))
    pairs=[]
    for r in rows:
        if r['stage'] not in ['compatibility','screen'] or r['arm']=='original' or not r['valid']:continue
        b=next(x for x in rows if x['stage']==r['stage'] and x['scene']==r['scene'] and x['rep']==r['rep'] and x['arm']=='original')
        ec=r['cost']/b['cost']-1;wall=r['native_seconds']/b['native_seconds']-1
        pairs.append(dict(stage=r['stage'],scene=r['scene'],arm=r['arm'],rep=r['rep'],
                          endpoint_delta=ec,wall_delta=wall,fail=ec>.005 or wall>.2))
    out=dict(groups=groups,paired_screen=pairs,all_valid=all(r['valid'] for r in rows),rows=len(rows))
    (P/'summary.json').write_text(json.dumps(out,indent=2)+'\n')
    gates={}
    for arm in ['pair','pair64']:
        gg=[g for g in groups if g['stage']=='final' and g['arm']==arm]
        if gg:
            g=gg[0]
            gates[arm+'_final_pass']=(g['n']==10 and g['valid']==10 and g['stop_miss_witnesses']>=2 and
              g['stop_miss_witnesses_rescued']==g['stop_miss_witnesses'] and
              g['conditional_seconds'] is not None and g['conditional_seconds']<=3.96)
    v=[g for g in groups if g['stage']=='venice' and g['arm']=='declip64']
    if v:gates['declip64_venice_hits']=v[0]['hits']
    gates['screen_failures']=[p for p in pairs if p['stage']=='screen' and p['fail']]
    (P/'gates.json').write_text(json.dumps(gates,indent=2)+'\n')
    for g in groups:print(g['stage'],g['scene'],g['arm'],str(g['hits'])+'/'+str(g['n']),
                         'target_s',g['conditional_seconds'],'native_s',g['native_median'],
                         'endpoint',g['endpoint_median'],'probes',g['probes'],
                         'witness_rescues',g['stop_miss_witnesses_rescued'],'/',g['stop_miss_witnesses'])
    for p in pairs:
        if p['fail']:print('SCREEN_FAIL',p)
if __name__=='__main__':main()
