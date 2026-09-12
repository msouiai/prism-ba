#!/usr/bin/env python3
"""Standalone scientific comparison figures from the complete registered rows."""
from pathlib import Path
import csv,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

P=Path(__file__).resolve().parent
names={'stcg':'Steihaug PCG','pi':'PI radius','coarse':'Additive coarse K8','frontload':'Accurate opening',
       'opening_unclip':'Opening unclipping','passenger':'Terminal passenger','soft_kick':'Terminal soft kick'}
panels={}
for name in names:
    f=P/(name+'-native-summary.json')
    if f.exists():
        x=json.loads(f.read_text())
        if len(x.get('practical',{}))==9 and all(c['arms'][a]['n']==3 for c in x['practical'].values() for a in ('off','on')):
            panels[name]=x
assert panels
fig,axs=plt.subplots(4,2,figsize=(14,11),sharex=True,squeeze=False,layout='constrained')
for ax,(name,data) in zip(axs.flat,panels.items()):
    keys=list(data['practical'])
    for i,k in enumerate(keys):
        c=data['practical'][k];off,on=c['arms']['off'],c['arms']['on']
        if off['hits']==on['hits']==3:
            ratio=off['target_median']/on['target_median']
            lo=off['target_range'][0]/on['target_range'][1];hi=off['target_range'][1]/on['target_range'][0]
            clear=c['time_signal'] in ('faster_disjoint','slower_disjoint')
            color='#177e5d' if lo>1 else '#bc3e39' if hi<1 else '#58606b'
            ax.errorbar(i,ratio,yerr=np.array([[ratio-lo],[hi-ratio]]),fmt='o',color=color,
                        markerfacecolor=color if clear else 'white',capsize=3,markersize=6)
        else:
            ax.text(i,.65,f"{off['hits']}/3 → {on['hits']}/3",rotation=90,ha='center',color='#bc3e39')
    ax.axhline(1,color='black',lw=.9,ls='--');ax.grid(axis='y',alpha=.2)
    ax.set_ylabel('Off / on target time');ax.set_title(names[name],loc='left',weight='bold',fontsize=11)
    ax.set_ylim(bottom=0)
labels=[k.replace('ladybug-539','Ladybug539').replace('trafalgar-138','Trafalgar138').replace('final-394','Final394').replace('-1.005','\n0.5%').replace('-1.01','\n1%').replace('-1.02','\n2%') for k in keys]
for ax in axs.flat:
    ax.set_xticks(range(9),labels,fontsize=7,rotation=40,ha='right')
for ax in list(axs.flat)[len(panels):]:ax.set_visible(False)
axs[2,1].tick_params(labelbottom=True)
fig.suptitle('Frozen Eta2 ingredients: identical-target native comparisons\nN=3 per arm/cell; above 1 is faster. Whiskers are observed range-ratio envelopes, not confidence intervals.',fontsize=12)
out=P/'figures';out.mkdir(exist_ok=True)
fig.savefig(out/'native_time_to_target.png',dpi=180);fig.savefig(out/'native_time_to_target.pdf');plt.close(fig)

fig,axs=plt.subplots(1,2,figsize=(14,4.8),sharey=True,layout='constrained')
for ax,scene in zip(axs,['venice-52','final-3068']):
    for i,(name,data) in enumerate(panels.items()):
        if scene not in data.get('tail',{}):continue
        d=data['tail'][scene]['arms']
        for j,a in enumerate(('off','on')):
            if d[a]['n']!=5:continue
            x=i+(j-.5)*.32
            ax.bar(x,d[a]['hits'],width=.3,color='#8f99a8' if a=='off' else '#315c99',label=a if i==0 else None)
            ax.text(x,d[a]['hits']+.07,f"{d[a]['hits']}/5",ha='center',fontsize=9)
    ax.set_xticks(range(len(panels)),[names[k] for k in panels],rotation=35,ha='right',fontsize=9)
    ax.set_title(scene);ax.set_ylim(0,5.8);ax.set_yticks(range(6));ax.grid(axis='y',alpha=.15)
axs[0].set_ylabel('Observed target hits');axs[1].legend(frameon=False)
fig.suptitle('Tail targets: separate small paired cohorts\nOff arms are independently rerun; differences between cohorts are not candidate effects.',fontsize=12)
fig.savefig(out/'native_tail_hits.png',dpi=180);fig.savefig(out/'native_tail_hits.pdf');plt.close(fig)

# All primary and independent-confirmation Venice trajectories; no selected exemplar.
rows=json.loads((P/'frontload-tail-results.json').read_text())+json.loads((P/'frontload-confirmation-results.json').read_text())
rows=[r for r in rows if r['scene']=='venice-52']
assert len(rows)==20 and all(sum(r['arm']==a for r in rows)==10 for a in ('off','on'))
fig,axs=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
seen=set()
for r in rows:
    curve=list(csv.DictReader(line for line in (P/r['source']/'curve.csv').read_text().splitlines() if not line.startswith('#')))
    t=np.array([float(x['wall_s']) for x in curve]);y=np.array([float(x['cost']) for x in curve])
    arm=r['arm'];color='#8a5662' if arm=='off' else '#197b69'
    label=('Eta2 control: 0/10 hits' if arm=='off' else 'Accurate opening: 10/10 hits') if arm not in seen else None
    seen.add(arm)
    for ax in axs:
        ax.step(t,y,where='post',color=color,alpha=.45,lw=1,label=label)
        ax.plot(t[-1],y[-1],'.',color=color,ms=3)
for ax in axs:
    ax.axhline(243740.27,color='black',ls='--',lw=1,label='Registered target: 243,740.27')
    ax.grid(alpha=.18);ax.set_xlabel('Native elapsed seconds');ax.set_ylabel('Full original-observation cost')
axs[0].set_yscale('log');axs[0].set_title('Complete trajectories, all 20 runs')
axs[1].set_ylim(243000,249000);axs[1].set_xlim(left=0);axs[1].set_title('Target region; dots mark termination')
axs[0].legend(fontsize=8,frameon=False)
fig.suptitle('Venice52: a confirmed local opening benefit\nFirst crossing times: median 0.37605s, range 0.3730–0.4288s. This arm regresses on the broader panel.',fontsize=11)
fig.savefig(out/'venice_opening_convergence.png',dpi=180);fig.savefig(out/'venice_opening_convergence.pdf');plt.close(fig)
print('Figures:',out)
