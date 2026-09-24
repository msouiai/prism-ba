#!/usr/bin/env python3
"""Descriptive native-time performance profiles, retaining censored scenes."""
import argparse,json,pathlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
 ap=argparse.ArgumentParser();ap.add_argument('root',type=pathlib.Path);a=ap.parse_args()
 s=json.loads((a.root/'summary.json').read_text());fig,axes=plt.subplots(1,3,figsize=(12,3.6),sharey=True)
 colors={'restart':'#176b99','caspar64':'#c95c22'};labels={'restart':'PRISM','caspar64':'Caspar FP64'}
 for ax,level in zip(axes,['loose','medium','tight']):
  cells=[x for x in s['cells'] if x['level']==level];ratios={k:[] for k in colors}
  for cell in cells:
   times={k:v['crossing'] for k,v in cell['arms'].items() if v['hits']==3}
   best=min(times.values()) if times else None
   for k in ratios:ratios[k].append(times[k]/best if k in times else np.inf)
  for k,v in ratios.items():
   tau=np.unique(np.r_[1,np.linspace(1,5,400),[x for x in v if np.isfinite(x) and x<=5]])
   ax.step(tau,[np.mean(np.array(v)<=t+1e-12) for t in tau],where='post',color=colors[k],label=labels[k],linewidth=2)
  ax.set(title=level.capitalize(),xlabel='Native time / best consistent solver',xlim=(1,5),ylim=(0,1.03));ax.grid(alpha=.2)
 axes[0].set_ylabel('Fraction of 12 problems (3/3 hits required)');axes[-1].legend(loc='lower right')
 fig.suptitle('Frozen BAL extension: descriptive profiles, failures retained',fontsize=13)
 fig.tight_layout();fig.savefig(a.root/'performance_profiles.png',dpi=180);fig.savefig(a.root/'performance_profiles.pdf')
if __name__=='__main__':main()
