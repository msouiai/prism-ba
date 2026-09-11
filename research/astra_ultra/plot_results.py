import json,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from paths import ROOT

out=ROOT/'figures';out.mkdir(exist_ok=True)
paths=json.loads((ROOT/'path_summary.json').read_text())
stiff=json.loads((ROOT/'stiffness_diagnostic.json').read_text())
energy=json.loads((ROOT/'energy_results.json').read_text())['rows']
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
fig,axes=plt.subplots(1,3,figsize=(16,5.))
ax=axes[0];families=['depth','joint','low_parallax'];x=np.arange(3)
colors={'xyz':'#243746','anchored':'#9b84ad','moving_host':'#5e9fa5','virtual_ray':'#df9427','observed_polish':'#377957'}
for offset,arm,label in [(-.27,'anchored','Fixed anchor'),(-.09,'moving_host','Moving host'),(.09,'virtual_ray','Virtual rays'),(.27,'observed_polish','Observed polishing')]:
    vals=[next(r for r in paths if r['family']==f and r['arm']==arm)['comparisons']['xyz']['median_speedup'] for f in families]
    ax.bar(x+offset,vals,.17,label=label,color=colors[arm])
ax.axhline(1,color='#555',lw=1);ax.set_xticks(x,['Depth','Joint pose','Low parallax']);ax.set_ylim(0,1.8)
ax.set_ylabel('Paired median speedup vs XYZ');ax.set_title('U1: full CPU time to identical target',loc='left',fontsize=11)
ax.legend(fontsize=8,ncol=2);ax.text(.02,.02,'4 cases/family × N=3; all180runs hit',transform=ax.transAxes,fontsize=8,
    bbox={'facecolor':'white','alpha':.9,'edgecolor':'none'})
ax=axes[1]
for f,col in zip(families,['#54809b','#a778a8','#4c9778']):
    a=[r for r in stiff['rows'] if r['family']==f]
    ax.scatter([r['excess_over_gn'] for r in a],[r['perspective']/r['gn'] for r in a],s=28,alpha=.8,label=f.replace('_',' '),color=col)
ax.axvline(1,color='#555',ls='--',lw=1);ax.axhline(0,color='#aaa',lw=.7)
ax.set_xlabel('Total missing curvature / GN curvature');ax.set_ylabel('Perspective residual curvature / GN')
ax.set_title('U2: severe positive curvature is rare',loc='left',fontsize=11);ax.legend(fontsize=8)
ax.text(.02,.02,'Only2/36parents qualify; one family',transform=ax.transAxes,fontsize=8,
    bbox={'facecolor':'white','alpha':.9,'edgecolor':'none'})
ax=axes[2];arms=['eta05','eta08','oracle_full','bound_full','bound_camera']
totals=[sum(r['rules'][a]['products'] for r in energy) for a in arms]
ax.bar(np.arange(5),totals,color=['#243746','#377957','#a5b5bc','#df9427','#bd9a62'])
ax.set_xticks(np.arange(5),['eta .5','eta .8','Oracle\n+points','Bound\n+points','Bound\ncameras'])
ax.set_ylabel('Total charged Schur products,45parents');ax.set_title('U3: cheap bound costs more work',loc='left',fontsize=11)
for i,n in enumerate(totals):ax.text(i,n+3,str(n),ha='center',fontsize=9)
ax.set_ylim(0,230)
fig.suptitle('Ultra-effort Astra hypotheses: narrow gains, no new champion',x=.04,ha='left',fontsize=15)
fig.text(.04,.015,'Original Eta2 unchanged. U2/U3 are frozen-parent diagnostics, not full solver timing. Oracle energy computation is expensive and excluded from product counts.',fontsize=9,color='#555')
fig.tight_layout(rect=[.01,.07,.995,.93])
for ext in ['png','pdf']:fig.savefig(out/f'ultra_summary.{ext}',dpi=180)
plt.close(fig)
# All four low-parallax cases, not a hand-picked favorable example.
rows=json.loads((ROOT/'path_results.json').read_text())['rows']
cases={c['id']:c for c in json.loads((ROOT/'cases.json').read_text())}
fig,axs=plt.subplots(2,2,figsize=(11,7))
labels={'xyz':'XYZ','moving_host':'Moving host','virtual_ray':'Virtual rays','observed_polish':'Observed polishing'}
for ax,seed in zip(axs.ravel(),range(500,504)):
    for arm,label in labels.items():
        a=[r for r in rows if r['family']=='low_parallax' and r['seed']==seed and r['arm']==arm]
        median=np.median([r['seconds'] for r in a]);main=min(a,key=lambda r:abs(r['seconds']-median))
        for r in a:
            bold=r is main
            ref=cases[r['id']]['reference_cost']
            excess=[(t['cost']-ref)/ref for t in r['trace']]
            assert min(excess)>0, 'Use a signed axis if a future run crosses the feasible reference.'
            ax.step([t['seconds'] for t in r['trace']],excess,where='post',
                color=colors[arm],lw=1.6 if bold else .7,alpha=1 if bold else .2,label=label if bold else None)
    ax.axhline(.01,color='#777',ls='--',lw=.7);ax.set_yscale('log');ax.set_xlabel('Total CPU time (s)');ax.set_ylabel('(Pixel cost − feasible reference) / reference')
    ax.set_title(f'Low-parallax seed {seed}',loc='left');ax.grid(alpha=.15);ax.legend(fontsize=8)
fig.suptitle('Joint virtual rays save work here; observed-point polishing is the stronger control',fontsize=12)
fig.tight_layout(rect=[0,0,1,.95])
for ext in ['png','pdf']:fig.savefig(out/f'low_parallax_curves.{ext}',dpi=180)
plt.close(fig);print('saved summary and all4low-parallax convergence plots')
