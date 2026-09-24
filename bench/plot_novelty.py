#!/usr/bin/env python3
"""Standalone endpoint plots; incomplete cells never become comparison points."""
import argparse,collections,json,pathlib,statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
status_path=a.root/'study-status.json';complete=status_path.exists() and json.loads(status_path.read_text()).get('local_nonlinear_complete',False)
rows=json.loads((a.root/'novelty-results.json').read_text());groups=collections.defaultdict(list)
for r in rows:
 if r.get('status','ok')=='ok':groups[r['experiment'],r['scene'],r['arm']].append(r)
scenes=sorted({s for e,s,arm in groups if 'seed' not in s})
for scene in scenes:
 fig,ax=plt.subplots(figsize=(8,5));count=0
 for (experiment,s,arm),rr in sorted(groups.items()):
  if s!=scene or len(rr)!=3:continue
  x=[r['seconds'] for r in rr];y=[r['cost'] for r in rr];xm=statistics.median(x);ym=statistics.median(y)
  marker='s' if arm.startswith('ceres') else '^' if arm.startswith('caspar') else 'o'
  label=arm+(' (CPU)' if arm.startswith('ceres') else ' (GPU)')
  ax.errorbar(xm,ym,xerr=[[xm-min(x)],[max(x)-xm]],yerr=[[ym-min(y)],[max(y)-ym]],fmt=marker,capsize=3,label=label);count+=1
 if count:
  ax.set(xlabel='Solver seconds (log scale)',ylabel='Endpoint cost (lower is better)',title=f'{scene}: completed N=3 cells only')
  ax.set_xscale('log');ax.grid(alpha=.2);ax.legend(fontsize=7,loc='upper left',bbox_to_anchor=(1.01,1))
  fig.text(.02,.01,'Medians and ranges. Caspar-fp32 / Ceres: CPU-fp64 checked; Prism: GPU-fp64. '+('Local cells complete.' if complete else 'Study in progress.'),fontsize=7)
  fig.savefig(a.out/f'{scene}-endpoints.svg',bbox_inches='tight');fig.savefig(a.out/f'{scene}-endpoints.png',dpi=160,bbox_inches='tight')
 plt.close(fig)
print('Endpoint plots written to',a.out)
