#!/usr/bin/env python3
"""All registered traces, cropped explicitly to the target region."""
from pathlib import Path
import csv,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent
rows=json.loads((P/'tail-results.json').read_text())
fig,axs=plt.subplots(1,2,figsize=(12,4.3),layout='constrained')
for ax,scene in zip(axs,['venice-52','final-3068']):
    seen=set()
    for r in rows:
        if r['scene']!=scene:continue
        curve=list(csv.DictReader(l for l in (P/r['source']/'curve.csv').read_text().splitlines() if not l.startswith('#')))
        t=[float(x['wall_s']) for x in curve];c=[float(x['cost'])/r['target'] for x in curve]
        arm=r['arm'];color='#526b8e' if arm=='off' else '#b14d42'
        label=('Frozen Eta2' if arm=='off' else 'Long-track tau × 0.3') if arm not in seen else None
        seen.add(arm);ax.step(t,c,where='post',color=color,alpha=.6,lw=1,label=label)
        ax.plot(t[-1],c[-1],'.',color=color,ms=4)
    ax.axhline(1,color='black',ls='--',lw=1,label='Registered target')
    ax.set_ylim(.985,1.13);ax.set_xlim(left=0);ax.grid(alpha=.18)
    ax.set_title(scene);ax.set_xlabel('Native elapsed seconds');ax.set_ylabel('Full cost / registered target')
axs[0].legend(fontsize=8,frameon=False)
fig.suptitle('Static long-track damping: target region, all N=5 pairs\nDots mark termination. Venice: 0/5 → 0/5; Final3068: 4/5 → 4/5.',fontsize=11)
out=P/'figures';out.mkdir(exist_ok=True)
fig.savefig(out/'convergence.png',dpi=180);fig.savefig(out/'convergence.pdf');plt.close(fig)
