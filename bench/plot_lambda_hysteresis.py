#!/usr/bin/env python3
import pathlib,json,argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,required=True);a=p.parse_args();rows=json.loads((a.root/'results.json').read_text());out=a.root/'figures';out.mkdir(exist_ok=True)
for scene in sorted({r['scene'] for r in rows}):
 rr=[r for r in rows if r['scene']==scene and r['rep']==1 and r.get('status','ok')=='ok']
 if len(rr)!=2:continue
 fig,axs=plt.subplots(1,2,figsize=(11,4))
 for r in rr:
  events=[e for e in r['events'] if e['retry']==0];tr=r['trace']
  axs[0].plot([e['outer'] for e in events],[e['center'] for e in events],label=r['arm'],alpha=.8,lw=.8)
  axs[1].plot([float(t['wall_s']) for t in tr],[float(t['cost']) for t in tr],label=r['arm'])
 axs[0].set(yscale='log',xlabel='Outer iteration',ylabel='Menu center lambda')
 axs[1].set(yscale='log',xlabel='Logged solver seconds',ylabel='Objective cost')
 for ax in axs:ax.grid(alpha=.2);ax.legend()
 fig.suptitle(f'{scene}: first repeat trajectories (not aggregate evidence)');fig.tight_layout();fig.savefig(out/f'{scene}.svg');plt.close(fig)
