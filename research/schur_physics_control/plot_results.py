#!/usr/bin/env python3
"""Publication artifacts from the compact ledger; no interpolation of solver traces."""
import pathlib,json,statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=pathlib.Path(__file__).resolve().parent
s=json.loads((ROOT/'summary.json').read_text())
out=ROOT/'figures';out.mkdir(exist_ok=True)
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':180})
colors=['#2464a4','#df8330','#568b46'];labels=['eta2','Coarse rank 8','Coarse rank 16']
fig,axs=plt.subplots(1,3,figsize=(10.5,3.6))
for ax,scene in zip(axs,['muell-gba146','ladybug-598','final-1936']):
    for i,rank in enumerate([0,8,16]):
        rows=[r for r in s['target_rows'] if r['scene']==scene and r['rank']==rank]
        values=[r['target_seconds'] for r in rows];med=statistics.median(values)
        ax.bar(i,med,color=colors[i],alpha=.3,width=.65)
        ax.scatter([i-.10,i,i+.10],values,c=colors[i],s=23,zorder=3)
        ax.text(i,max(values)*1.07,f'{med:.3f}',ha='center')
    ax.set(xticks=range(3),xticklabels=['eta2','Rank 8','Rank 16'],title=scene,ylim=(0,ax.get_ylim()[1]*1.24))
    ax.set_ylabel('Native seconds to identical target');ax.grid(axis='y',alpha=.2)
fig.suptitle('Eta2 remains the incumbent — all 27 target runs hit',y=1.02)
fig.tight_layout();fig.savefig(out/'target_gate.png',bbox_inches='tight');fig.savefig(out/'target_gate.pdf',bbox_inches='tight');plt.close(fig)
fig,ax=plt.subplots(figsize=(7,4.1))
for color,arm,label in zip(colors,['v2','window8','eta2'],['v2','v2 + stop window 8','eta2']):
    rows=[r for r in s['audit_rows'] if r['cohort']=='stall' and r['arm']==arm]
    for stop,marker in [(True,'X'),(False,'o')]:
        selected=[r for r in rows if bool(r['stop_messages'])==stop]
        ax.scatter([r['cost']/1e6 for r in selected],[r['terminal_gradient']['normalized_gradient_energy'] for r in selected],label=f'{label}: '+('stop' if stop else '60-outer cap'),marker=marker,c=color,s=48,alpha=.85)
ax.set(xlabel='Terminal objective (millions)',ylabel=r'$g^T D^{-1}g / (2F)$',yscale='log',title='Final3068: a small cost change does not establish stationarity')
ax.grid(alpha=.2);ax.legend(fontsize=8,ncol=2);fig.tight_layout()
fig.savefig(out/'stationarity_audit.png',bbox_inches='tight');fig.savefig(out/'stationarity_audit.pdf',bbox_inches='tight');plt.close(fig)
