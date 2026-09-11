import os
os.environ['MPLCONFIGDIR']='/tmp/prism-followup-mpl'
import pathlib,json,numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=pathlib.Path(__file__).resolve().parent;O=P/'figures';O.mkdir(exist_ok=True)
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':150})
h=json.loads((P/'holdout_summary.json').read_text())
fig,ax=plt.subplots(figsize=(7,3.5),layout='constrained')
families=['depth','joint','low_parallax'];labels=['Depth perturbation','Camera rotation','Low parallax']
for j,(arm,label,color) in enumerate([('virtual_ray','Virtual rays','#3b82b6'),('observed_polish','Point polishing','#db8035')]):
    vals=[next(r['median_speedup'] for r in h if r['family']==f and r['arm']==arm) for f in families]
    rect=ax.bar(np.arange(3)+(j-.5)*.3,vals,.28,label=label,color=color)
    ax.bar_label(rect,labels=[f'{v:.2f}×' for v in vals],padding=3)
ax.axhline(1,color='k',lw=1,ls='--');ax.set_xticks(range(3),labels);ax.set_ylim(0,1.65);ax.set_ylabel('Speedup over ordinary CPU LM');ax.legend(frameon=False);ax.set_title('Fresh geometric holdouts: 12 cases, N=3\nSix-DOF CPU mechanism test; not Eta2 GPU performance',fontsize=11)
for ext in ['png','pdf']:fig.savefig(O/('fresh_holdouts.'+ext))
plt.close(fig)
rows=[json.loads(f.read_text()) for f in (P/'evidence/conditional').glob('*/result.json')]
fig,axs=plt.subplots(1,3,figsize=(13,3.8),layout='constrained')
for ax,s in zip(axs,['ladybug-49','dubrovnik-88','venice-52']):
    for a,l,c in [('champion','Eta2','#333333'),('polish_gate','Eta2 + conditional polish','#db8035')]:
        rs=[r for r in rows if r['scene']==s and r['arm']==a];hit=sorted(r['target_seconds'] for r in rs if r['hit']);limit=max([r['native_seconds'] for r in rows if r['scene']==s])*1.1
        tx=[0]+hit+[limit];yy=[0]+[(i+1)/len(rs) for i in range(len(hit))]+[len(hit)/len(rs)]
        ax.step(tx,yy,where='post',label=f'{l} ({len(hit)}/{len(rs)})',color=c,lw=2)
    ax.set_title(s);ax.set_xlabel('Native solver seconds');ax.set_ylim(-.02,1.05);ax.set_ylabel('Fraction reaching the identical target');ax.legend(fontsize=8,frameon=False,loc='lower right');ax.grid(alpha=.18)
fig.suptitle('Conditional polishing: speed and target reliability\nMisses remain misses; curves include candidate overhead',fontsize=12)
for ext in ['png','pdf']:fig.savefig(O/('conditional_targets.'+ext))
plt.close(fig)
