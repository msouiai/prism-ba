#!/usr/bin/env python3
"""Recompute largest-scene statistics from the retained invocation records."""
import pathlib,json,statistics,re,argparse
ROOT=pathlib.Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--data',type=pathlib.Path,default=pathlib.Path('/workspace/prism-schur-physics-largest'));ap.add_argument('--output',type=pathlib.Path,default=ROOT/'largest_summary.json');a=ap.parse_args()
rows=json.loads((a.data/'runs.json').read_text())
def stat(xs):
    xs=list(xs);return {'median':statistics.median(xs),'min':min(xs),'max':max(xs)} if xs else None
out={'timing':'native TARGET events for fixed-target panels; activation caps and curvature diagnostic are not equal-quality timing comparisons','rows':rows,'groups':[],'native_seconds_total':sum(r.get('native_seconds',0) for r in rows)}
for panel in ['primary','tighter','activation']:
    for rank in [0,16]:
        rs=[r for r in rows if r['panel']==panel and r['rank']==rank]
        if not rs:continue
        times=stat(r['target_seconds'] for r in rs if r['target_hit'])
        d={'panel':panel,'rank':rank,'n':len(rs),'target':rs[0]['target'],'hits':sum(r['target_hit'] for r in rs),'target_seconds':times,'cost':stat(r['cost'] for r in rs if 'cost' in r),'native_seconds':stat(r['native_seconds'] for r in rs if 'native_seconds' in r),'outers':stat(r['outers'] for r in rs if 'outers' in r),'rejects':stat(r['rejects'] for r in rs if 'rejects' in r),'products':stat(r['matvecs'] for r in rs if 'matvecs' in r),'coarse_active':stat(r['coarse_active'] for r in rs),'coarse_rejects':stat(r['coarse_rejects'] for r in rs),'sampled_peak_gpu_MiB':stat(r['sampled_peak_gpu_MiB'] for r in rs),'process_seconds':stat(r['process_seconds'] for r in rs)}
        if times:
            base=stat(r['target_seconds'] for r in rows if r['panel']==panel and r['rank']==0 and r['target_hit'])
            d['ratio_to_eta2']=times['median']/base['median']
        depths=[]
        for r in rs:
            t=(a.data/f"{panel}-r{rank}-{r['rep']}.log").read_text()
            depths += [int(x) for x in re.findall(r'PCG_PREP .*?previous_depth=(\d+)',t)]
        d['maximum_observed_prior_depth']=max(depths,default=None)
        out['groups'].append(d)
p=a.data/'curvature/probe.json'
if p.exists():out['curvature']=json.loads(p.read_text())
a.output.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='rows'},indent=2))
