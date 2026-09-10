#!/usr/bin/env python3
"""Plot measured staircases; never interpolate or extend a stopped run."""
import pathlib,csv,json,argparse,math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=pathlib.Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--data',type=pathlib.Path,default=pathlib.Path('/workspace/prism-schur-physics-largest-curves'));args=ap.parse_args()
out=ROOT/'figures/convergence';out.mkdir(parents=True,exist_ok=True)
curves=[]
for rank in [0,16]:
    stem=args.data/f'rank{rank}';meta=json.loads(stem.with_suffix('.json').read_text())
    assert meta['returncode']==0 and meta['target_hit']
    with stem.with_suffix('.csv').open() as f:rows=list(csv.DictReader(l for l in f if not l.startswith('#')))
    assert int(rows[-1]['iter'])==meta['target_outers']
    assert abs(float(rows[-1]['cost'])-meta['target_cost'])<1e-7*meta['target_cost']
    offset=meta['target_seconds']-float(rows[-1]['wall_s']);assert offset>=0
    points=[{'iteration':0,'seconds':0.0,'cost':float(rows[0]['cost']),'event':'initial'}]
    points += [{'iteration':int(r['iter']),'seconds':float(r['wall_s'])+offset,'cost':float(r['cost']),'event':'setup_complete' if int(r['iter'])==0 else 'outer_complete'} for r in rows]
    curves.append({'name':'Eta2' if rank==0 else 'Eta2 + rank16','kind':'fresh display trace, N=1','coarse_active':meta['coarse_active'],'csv_to_native_offset':offset,'color':'#1967a3' if rank==0 else '#ec8a23','style':'-' if rank==0 else '--','points':points})
with (args.data/'historical/curves.csv').open() as f:old=list(csv.DictReader(f))
for arm,name,color,style in [('caspar32','Caspar FP32 (historical)','#ab3b4b','-.'),('caspar64','Caspar FP64 (historical)','#7552a3',':')]:
    selected=[r for r in old if r['arm']==arm and r['representative']=='True']
    assert selected and len({r['rep'] for r in selected})==1
    points=[{'iteration':int(r['iteration']),'seconds':float(r['elapsed_s']),'cost':float(r['cost']),'event':r['event']} for r in selected if r['cost_kind']=='native']
    endpoints=[r for r in selected if r['cost_kind']=='independent_fp64'];assert len(endpoints)==1
    audited={'seconds':float(endpoints[0]['elapsed_s']),'cost':float(endpoints[0]['cost']),'iteration':int(endpoints[0]['iteration'])}
    curves.append({'name':name,'kind':'historical median-target-time run from N=3','rep':int(selected[0]['rep']),'color':color,'style':style,'points':points,'audited_endpoint':audited})
for c in curves:
    assert all(math.isfinite(p['cost']) and p['cost']>0 for p in c['points'])
    assert all(b['seconds']>=a['seconds'] for a,b in zip(c['points'],c['points'][1:]))
(ROOT/'largest_curves.json').write_text(json.dumps(curves,indent=2)+'\n')
with (ROOT/'largest_curves.csv').open('w') as f:
    writer=csv.DictWriter(f,fieldnames=['algorithm','cohort','iteration','seconds','cost','event'],lineterminator='\n');writer.writeheader()
    for c in curves:
        for p in c['points']:writer.writerow(dict(algorithm=c['name'],cohort=c['kind'],**p))
plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':180})
target=27591576.557625167
fig,axes=plt.subplots(1,2,figsize=(12.4,5.4))
for ax in axes:
    for c in curves:
        pts=c['points'];x=[p['seconds'] for p in pts];y=[p['cost']/1e6 for p in pts]
        ax.step(x,y,where='post',color=c['color'],linestyle=c['style'],linewidth=2.25,label=c['name'])
        ax.scatter(x[-1],y[-1],color=c['color'],s=32,zorder=4)
        if 'audited_endpoint' in c:
            p=c['audited_endpoint'];ax.scatter(p['seconds'],p['cost']/1e6,color=c['color'],marker='D',s=34,zorder=5)
    ax.axhline(target/1e6,color='#666666',linestyle=(0,(5,5)),linewidth=1)
    ax.set_xlabel('Native solver time (s)');ax.set_ylabel('Objective (millions; lower is better)');ax.grid(alpha=.2)
axes[0].set(yscale='log',ylim=(23,1300),xlim=(0,15.7),title='Full descent')
axes[0].set_yticks([25,50,100,250,500,1000],labels=['25','50','100','250','500','1000'])
axes[1].set(ylim=(24.3,35),xlim=(2.0,15.7),title='Close-up near the quality target')
axes[1].text(9.1,target/1e6+.22,'Historical target: 27.592M',fontsize=9,color='#555555')
handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,.94),ncol=2,frameon=False,fontsize=10)
fig.suptitle('Final13682 convergence',fontsize=16,y=1.00)
fig.subplots_adjust(left=.075,right=.985,bottom=.24,top=.75,wspace=.24)
fig.text(.5,.055,'Fresh Prism display traces: one run each; coarse correction inactive. Caspar: historical same-input references.\nCurves end at recorded stops. Prism CSV clocks align to the same-run TARGET event (approximate within logging delay).',ha='center',fontsize=9,color='#444444')
for ext in ['png','pdf','svg']:fig.savefig(out/f'final13682_coarse_time.{ext}',bbox_inches='tight')
plt.close(fig)
fig,ax=plt.subplots(figsize=(8.7,4.5))
for c in curves[:2]:
    pts=[p for p in c['points'] if p['event']!='setup_complete']
    ax.plot([p['iteration'] for p in pts],[p['cost']/1e6 for p in pts],color=c['color'],linestyle=c['style'],marker='o' if c is curves[0] else 'x',markersize=4,label=c['name'])
ax.set(xlabel='Outer iteration',ylabel='Objective (millions; lower is better)',yscale='log',title='Final13682: current Prism trajectories')
ax.set_yticks([25,50,100,250,500,1000],labels=['25','50','100','250','500','1000']);ax.grid(alpha=.2);ax.legend()
fig.text(.5,.005,'One timestamped run per arm. The coarse correction never activates; no timing is inferred from this iteration plot.',ha='center',fontsize=9)
fig.tight_layout(rect=(0,.055,1,1))
for ext in ['png','pdf','svg']:fig.savefig(out/f'final13682_coarse_iterations.{ext}',bbox_inches='tight')
plt.close(fig)
for svg in out.glob('final13682_coarse_*.svg'):
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
print(json.dumps([{'algorithm':c['name'],'last':c['points'][-1],'offset':c.get('csv_to_native_offset'),'coarse_active':c.get('coarse_active')} for c in curves],indent=2))
