#!/usr/bin/env python3
"""All fresh N=10 trajectories in the target region, no selected exemplars."""
import csv,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent;Q=P/'confirmation'
rows=json.loads((Q/'tail-results.json').read_text());assert len(rows)==40
fig,axs=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
counts={}
for ax,scene in zip(axs,['final-3068','venice-52']):
    seen=set();rr=[r for r in rows if r['scene']==scene]
    counts[scene]={a:sum(r['hit'] for r in rr if r['arm']==a) for a in ('off','on')}
    for r in rr:
        curve=list(csv.DictReader(l for l in (P/r['source']/'curve.csv').read_text().splitlines() if not l.startswith('#')))
        t=[float(x['wall_s']) for x in curve];y=[float(x['cost'])/r['target'] for x in curve]
        arm=r['arm'];color='#42688b' if arm=='off' else '#b4473c'
        label=('Frozen Eta2' if arm=='off' else 'Track multipliers 1 / 1 / 0.3') if arm not in seen else None
        seen.add(arm);ax.step(t,y,where='post',color=color,alpha=.55,lw=1,label=label)
        ax.plot(t[-1],y[-1],'.',color=color,ms=4)
    ax.axhline(1,color='black',ls='--',lw=1,label='Registered target')
    ax.set_ylim(.985,1.15);ax.set_xlim(left=0);ax.grid(alpha=.18)
    ax.set_xlabel('Native elapsed seconds');ax.set_ylabel('Full cost / registered target')
    ax.set_title(f"{scene}: {counts[scene]['off']}/10 → {counts[scene]['on']}/10 hits")
axs[0].legend(frameon=False,fontsize=8)
fig.suptitle('Fresh static point-damping confirmation: all N=10 runs per arm\nTarget region shown; dots mark termination. Earlier N=5 screen is not pooled.',fontsize=11)
out=Q/'figures';out.mkdir(exist_ok=True)
fig.savefig(out/'tail_convergence.png',dpi=180);fig.savefig(out/'tail_convergence.pdf');plt.close(fig)
