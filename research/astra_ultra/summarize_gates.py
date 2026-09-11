import json,numpy as np
from paths import ROOT,write_json
read=lambda name:json.loads((ROOT/name).read_text())
rows=read('path_results.json')['rows'];summary=read('path_summary.json');gates=[]
for arm in ['anchored','moving_host','virtual_ray','observed_polish']:
    winners=[];regressions=[]
    for family in ['depth','joint','low_parallax']:
        r=next(x for x in summary if x['family']==family and x['arm']==arm)
        refs=['xyz','anchored','moving_host'] if arm=='virtual_ray' else ['xyz']
        if all(r['comparisons'][b]['median_speedup']>=1.1 for b in refs) and r['hits']==r['runs']:winners.append(family)
    for case in sorted(set(r['id'] for r in rows)):
        a=next(r for r in rows if r['id']==case and r['arm']==arm and r['rep']==0)
        b=next(r for r in rows if r['id']==case and r['arm']=='xyz' and r['rep']==0)
        for metric,threshold in [('point_nrmse',.2),('camera_nrmse',.2),('rotation_median_deg',5.)]:
            if a[metric]>threshold and a[metric]>1.2*b[metric]:regressions.append({'id':case,'metric':metric,'baseline':b[metric],'candidate':a[metric]})
    gates.append({'arm':arm,'winning_families':winners,'severe_geometry_regressions':regressions,
        'general_promotion':len(winners)>=2 and not regressions})
decisions={'paths':gates,'stiffness':read('stiffness_diagnostic.json')['gate'],
    'energy_bound':next(r for r in read('energy_summary.json') if r['rule']=='bound_full'),
    'incumbent':'frozen Eta2 unchanged','native_promotion':False}
write_json(ROOT/'decisions.json',decisions);print(decisions)
