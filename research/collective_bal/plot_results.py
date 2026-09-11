import csv
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from paths import ROOT

data = json.loads((ROOT/'results.json').read_text())['rows']
OUT = ROOT/'figures/convergence'; OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.size':10, 'axes.spines.top':False, 'axes.spines.right':False, 'pdf.fonttype':42})
fig, axes = plt.subplots(3,3,figsize=(15,11))
arms = ['fine','nonlinear8','bridge8','selective']
names = ['Ordinary BA','Original nonlinear coarse','Bridge-only nonlinear coarse','Selective bridge-only']
colors = ['#243746','#d98412','#007d79','#9854a5']; exports=[]
for i,scene in enumerate(['ladybug-49','dubrovnik-88','venice-52']):
    for j,seed in enumerate([60,61,62]):
        ax=axes[i,j]
        for arm,name,color in zip(arms,names,colors):
            rows=[r for r in data if r['scene']==scene and r['seed']==seed and r['arm']==arm]
            median=np.median([r['seconds'] for r in rows]); representative=min(rows,key=lambda r:abs(r['seconds']-median))
            for row in rows:
                trace=row['trace']; bold=row is representative
                ax.step([t['seconds'] for t in trace],[t['cost']/row['target'] for t in trace],where='post',
                        color=color,lw=1.8 if bold else .9,alpha=1 if bold else .15,label=name if bold else None)
                exports.extend({'scene':scene,'seed':seed,'rep':row['rep'],'arm':arm,'seconds':t['seconds'],
                                'cost':t['cost'],'target':row['target']} for t in trace)
        ax.axhline(1,color='#444444',ls='--',lw=.8); ax.set_yscale('log'); ax.grid(alpha=.15,which='both')
        ax.set_xlabel('Total CPU time (s)'); ax.set_ylabel('Cost / fixed target'); ax.set_title(f'{scene}, sample {seed}',loc='left')
        if i==0:ax.legend(fontsize=7.5)
fig.suptitle('Nonlinear collective correction on BAL samples retaining every camera',x=.035,ha='left',fontsize=15)
fig.text(.035,.015,'1,200 points/sample; 3 samples/scene, N=3 each. Setup and final full-cost verification included. Fixed-intrinsics CPU reference, not full BAL or GPU Eta2.',fontsize=9,color='#555555')
fig.tight_layout(rect=[.01,.04,.995,.96]);fig.savefig(OUT/'all_camera_bal.png',dpi=180);fig.savefig(OUT/'all_camera_bal.pdf');plt.close(fig)
with (OUT/'traces.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(exports[0]));w.writeheader();w.writerows(exports)
print('Saved all nine samples, PNG/PDF and plotted CSV')
