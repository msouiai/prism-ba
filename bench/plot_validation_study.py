#!/usr/bin/env python3
"""CPU-audited endpoint plot; bars are observed ranges, not confidence intervals."""
import argparse,json,pathlib,statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from validation_study import SCENES,read_rows,med

p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,default=pathlib.Path('/workspace/prism-validation'));p.add_argument('--output',type=pathlib.Path,default=pathlib.Path('/workspace/prism-ba/docs/fixed_policy_budget_comparison.png'));a=p.parse_args()
rows=read_rows(a.root/'budgets');assert len(rows)==72 and all(r['status']=='ok' for r in rows)
fig,axes=plt.subplots(2,2,figsize=(10,7),layout='constrained')
styles={'selected':('PRISM multi + rearm','#2166ac','o'),'single':('PRISM single + safeguard','#d6604d','s'),'caspar32':('Caspar FP32 default','#555555','^')}
for ax,(scene,budgets) in zip(axes.flat,SCENES.items()):
 sr=[r for r in rows if r['scene']==scene];ref=min(med([r for r in sr if r['arm']==arm and r['budget']==b],'cost') for arm in styles for b in budgets)
 for arm,(label,color,marker) in styles.items():
  ys=[];lower=[];upper=[]
  for budget in budgets:
   costs=[100*(r['cost']/ref-1) for r in sr if r['arm']==arm and r['budget']==budget];m=statistics.median(costs)
   ys.append(m);lower.append(m-min(costs));upper.append(max(costs)-m)
  ax.errorbar(budgets,ys,yerr=[lower,upper],fmt=marker,color=color,label=label,capsize=4,markersize=6,alpha=.9)
 ax.set_title(scene);ax.set_xticks(budgets);ax.set_xlabel('Declared solve budget (s)');ax.set_ylabel('Excess cost over best median (%)')
 ax.axhline(0,color='#aaaaaa',linewidth=.7,linestyle=':');ax.grid(axis='y',alpha=.2)
 pad=.15*(max(budgets)-min(budgets));ax.set_xlim(min(budgets)-pad,max(budgets)+pad)
fig.suptitle('CPU-checked BA costs at fixed solve budgets\nMarkers: medians; bars: min–max of three runs',fontsize=13)
handles,labels=axes.flat[0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncol=3,frameon=False)
a.output.parent.mkdir(parents=True,exist_ok=True);fig.savefig(a.output,dpi=200)
print(a.output)
