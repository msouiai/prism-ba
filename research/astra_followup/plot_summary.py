import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from paths import ROOT

out=ROOT/'figures';out.mkdir(exist_ok=True)
late=json.loads((ROOT/'late_summary.json').read_text())
chart=json.loads((ROOT/'chart_summary.json').read_text())
schur=json.loads((ROOT/'schur_summary.json').read_text())
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
fig,axes=plt.subplots(1,3,figsize=(15,4.8))
ax=axes[0];scenes=['ladybug-49','dubrovnik-88','venice-52'];x=np.arange(3)
for off,tau,color in [(-.18,.001,'#336b8a'),(.18,.00001,'#78a4ba')]:
    vals=[next(r for r in late if r['scene']==s and r['tau']==tau)['nonlinear_hindsight_best']['full_speedup'] for s in scenes]
    ax.bar(x+off,vals,.34,color=color,label=f'tau={tau:g}')
ax.axhline(1,color='#444',lw=1);ax.set_ylim(0,1.2);ax.set_xticks(x,['Ladybug49','Dubrovnik88','Venice52'])
ax.tick_params(axis='x',labelsize=8);ax.set_ylabel('Speedup vs continued ordinary LM')
ax.set_title('A1: best late insertion in hindsight',loc='left',fontsize=11);ax.legend(fontsize=8)
ax.text(.02,.02,'0 fine steps saved\nComposed prefix + repeated tail',transform=ax.transAxes,fontsize=9,bbox={'facecolor':'white','alpha':.9,'edgecolor':'none'})
ax=axes[1]
families=['low_parallax','moderate_parallax','rotation']
for off,arm,color,label in [(-.18,'anchored','#8d70a5','Anchored inverse depth'),(.18,'mean_view','#d28b28','Mean-view candidate')]:
    vals=[next(r for r in chart if r['family']==f and r['arm']==arm)['speedup_vs_xyz'] for f in families]
    ax.bar(x+off,vals,.34,color=color,label=label)
ax.axhline(1,color='#444',lw=1);ax.set_ylim(0,1.45);ax.set_xticks(x,['Low parallax','Moderate','Rotation'])
ax.tick_params(axis='x',labelsize=9);ax.set_ylabel('Paired median speedup vs XYZ')
ax.set_title('A2: same-tangent point paths',loc='left',fontsize=11);ax.legend(fontsize=8)
ax.text(.02,.02,'10 seeds/family, N=3\nCost hits do not certify geometry',transform=ax.transAxes,fontsize=9,bbox={'facecolor':'white','alpha':.9,'edgecolor':'none'})
ax=axes[2];arms=['plain','old4','theta4','energy4']
a=[next(r for r in schur if r['scene']=='muell-gba146' and r['arm']==arm) for arm in arms]
setup=[r['setup_ms'] for r in a];solve=[r['wall_ms']-r['setup_ms'] for r in a]
ax.bar(np.arange(4),setup,color='#a9bdc8',label='Setup / history refresh')
ax.bar(np.arange(4),solve,bottom=setup,color='#336b8a',label='Solve + remaining overhead')
ax.set_xticks(np.arange(4),['Plain','Old Ritz4','Theta4','Energy4']);ax.tick_params(axis='x',labelsize=8)
ax.set_ylabel('Current-system median wall time (ms)')
ax.set_title('A3: frozen Muell GPU system',loc='left',fontsize=11);ax.legend(fontsize=8)
fig.suptitle('Astra-guided BA screens: no new champion',x=.04,ha='left',fontsize=15)
fig.text(.04,.02,'A1/A2: small fixed-intrinsics CPU references. A3: native fixed-system GPU replay. Original Eta2 solver unchanged; no new Caspar comparison.',fontsize=9,color='#555')
fig.tight_layout(rect=[.01,.07,.995,.94])
for ext in ['png','pdf']:fig.savefig(out/f'screen_summary.{ext}',dpi=180)
plt.close(fig);print(out/'screen_summary.png')
