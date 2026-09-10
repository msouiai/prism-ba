#!/usr/bin/env python3
import pathlib,json,argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,required=True);a=p.parse_args();rows=json.loads((a.root/'results.json').read_text());out=a.root/'figures';out.mkdir(exist_ok=True)
colors={'single':'#2878b5','multi':'#f18f01','adaptive':'#32936f'}
for scene in sorted({r['scene'] for r in rows}):
 rr=[r for r in rows if r['scene']==scene and r.get('status','ok')=='ok'];best=min(r['cost'] for r in rr)
 fig,ax=plt.subplots(figsize=(7,4))
 for arm in colors:
  for i,r in enumerate(x for x in rr if x['arm']==arm):
   tr=r['trace'];over=max(0,r['seconds']-float(tr[-1]['wall_s']))
   ax.plot([float(t['wall_s'])+over+.000101 for t in tr],[100*(float(t['cost'])/best-1) for t in tr],color=colors[arm],alpha=.65,lw=.9,label=arm if i==0 else None)
 for band in [1,3,5]:ax.axhline(band,color='gray',ls='--',lw=.7)
 ax.set(xscale='log',yscale='symlog',xlabel='Conservative solver-time bound (seconds)',ylabel='Cost above empirical best endpoint (%)',title=scene)
 ax.set_ylim(-.05,100);ax.grid(alpha=.15);ax.legend();fig.tight_layout();fig.savefig(out/f'{scene}.svg');plt.close(fig)
