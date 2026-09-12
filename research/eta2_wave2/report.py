"""Rebuild wave-2 ledgers and figures from retained, independently audited runs."""
from pathlib import Path
import csv,json,math,statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
P=Path(__file__).resolve().parent
LABELS={'off':'Frozen Eta2','forcing_reject':'Tighter CG + oversized rejection',
 'accurate_reference':'Coherent accurate opening','coupled':'Coupled tau root',
 'frozen':'Frozen tau root','opening':'Opening-only root','geodesic':'Geodesic correction'}
GROUPS=['compatibility','venice','final','practical','root-compatibility','root-tail','root-practical',
 'geodesic-compatibility','geodesic-tail','geodesic-practical','plateau-compatibility','plateau-tail']
def load(p):return json.loads(Path(p).read_text())
def stats(values):
    v=list(values)
    return dict(median=statistics.median(v),min=min(v),max=max(v)) if v else None
def fmt(v,d=3):return '—' if v is None else f'{v:.{d}f}'
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|',*['| '+' | '.join(map(str,r))+' |' for r in rows]])
def main():
    allrows=[];groups={};summaries=[];comparisons={}
    for group in GROUPS:
        path=P/(group+'-results.json')
        if path.exists():
            r=load(path);groups[group]=r;allrows+=r
    # Additional conditional-witness runs: remove the five rows already in tail.
    if (P/'plateau-witnesses-results.json').exists():
        existing={r['source'] for r in allrows};extra=[r for r in load(P/'plateau-witnesses-results.json') if r['source'] not in existing]
        groups['plateau-extra']=extra;allrows+=extra
    assert len({r['source'] for r in allrows})==len(allrows)
    assert all(r['valid'] and r['audit_relative_error']<1e-6 for r in allrows)
    for group,rows in groups.items():
        for cell,arm in sorted({(r['cell'],r['arm']) for r in rows}):
            rr=[r for r in rows if r['cell']==cell and r['arm']==arm]
            summaries.append(dict(group=group,cell=cell,arm=arm,n=len(rr),hits=sum(r['hit'] for r in rr),target=rr[0]['target'],
              **{key:stats(r[key] for r in rr if r.get(key) is not None) for key in ['cost','native_seconds','target_seconds','outers','accepts','rejects','pcg_per_outer','retry_fraction_native','score_init','max_raw_radius_ratio']},
              cap_hits=sum(r['cap_hit'] for r in rr),negcurv=sum(r['negcurv'] for r in rr)))
    for group in ['practical','root-practical','geodesic-practical']:
        if group not in groups:continue
        rr=groups[group];cc={}
        for arm in sorted({r['arm'] for r in rr}-{'off'}):
            cells=[]
            for cell in sorted({r['cell'] for r in rr}):
                ts=[[r['target_seconds'] for r in rr if r['cell']==cell and r['arm']==a and r['hit']] for a in ['off',arm]]
                assert all(len(v)==3 for v in ts)
                ratio=statistics.median(ts[1])/statistics.median(ts[0])
                verdict='faster' if max(ts[1])<min(ts[0]) else 'slower' if min(ts[1])>max(ts[0]) else 'overlap'
                cells.append(dict(cell=cell,control=stats(ts[0]),variant=stats(ts[1]),median_time_ratio=ratio,verdict=verdict))
            cc[arm]=dict(cells=cells,geometric_mean_ratio=math.exp(statistics.mean(math.log(c['median_time_ratio']) for c in cells)),
               faster=sum(c['verdict']=='faster' for c in cells),slower=sum(c['verdict']=='slower' for c in cells),overlap=sum(c['verdict']=='overlap' for c in cells))
        comparisons[group]=cc
    summary=dict(current_global_winner='frozen Eta2; no promotion from these global screens',native_run_count=len(allrows),groups={k:len(v) for k,v in groups.items()},
      cells=summaries,practical_comparisons=comparisons,maximum_endpoint_audit_error=max(r['audit_relative_error'] for r in allrows),
      limitation='N3 empirical disjoint ranges are descriptive, not confidence intervals; no pooling of separate fresh tail cohorts.')
    (P/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    columns=['stage','cell','scene','arm','rep','target','score_init','cost','hit','target_seconds','native_seconds','outers','accepts','rejects','pcg_per_outer','retry_fraction_native','max_raw_radius_ratio','negcurv','cap_hit','source']
    with (P/'metrics.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=columns,lineterminator='\n');w.writeheader()
        for r in allrows:w.writerow({k:r.get(k) for k in columns})
    sections=['# Wave-2 numerical ledger','Generated from the retained result files. All native endpoints were independently rescored on the original full objective. Different stages use fresh cohorts; do not pool their control hit counts.']
    for group in ['venice','final','root-tail','geodesic-tail','plateau-tail','plateau-extra']:
        ss=[s for s in summaries if s['group']==group]
        if not ss:continue
        rows=[]
        for s in ss:
            t=s['target_seconds'];rows.append([s['cell'],s['arm'],f"{s['hits']}/{s['n']}",fmt(s['cost']['median'],2),fmt(t['median'] if t else None,4),
              '—' if t is None else f"{t['min']:.4f}–{t['max']:.4f}",fmt(s['outers']['median'],1),fmt(s['rejects']['median'],1),fmt(s['pcg_per_outer']['median'] if s['pcg_per_outer'] else None,2),
              fmt(100*s['retry_fraction_native']['median'] if s['retry_fraction_native'] else None,2)])
        sections+=['\n## '+group,table(['Cell','Arm','Hits','Median final cost','Hit time s','Hit range s','Ou ters'.replace(' ',''),'Rejects','PCG/outer','Retry wall %'],rows)]
    sections+=['\n## All nine practical cells','Every cell has N3 per arm. Time ratios below1 favor the intervention. All target crossings, including regressions, are retained.']
    for group,arms in comparisons.items():
        for arm,a in arms.items():
            sections+=['\n### '+group+' / '+arm,
             f"Geometric mean time ratio **{a['geometric_mean_ratio']:.4f}**; {a['faster']} disjoint faster, {a['slower']} disjoint slower, {a['overlap']} overlapping.",
             table(['Cell','Control median s [range]','Variant median s [range]','Time ratio','Observed ranges'],[
               [c['cell'],f"{c['control']['median']:.4f} [{c['control']['min']:.4f}, {c['control']['max']:.4f}]",f"{c['variant']['median']:.4f} [{c['variant']['min']:.4f}, {c['variant']['max']:.4f}]",f"{c['median_time_ratio']:.4f}",c['verdict']] for c in a['cells']])]
    sections+=['\n## Initial-score and numerical checks',table(['Cell','Initial score min','Initial score max'],[[cell,f"{min(r['score_init'] for r in allrows if r['cell']==cell):.12g}",f"{max(r['score_init'] for r in allrows if r['cell']==cell):.12g}"] for cell in sorted({r['cell'] for r in allrows})]),
      f"Maximum relative native-versus-independent endpoint cost error: {summary['maximum_endpoint_audit_error']:.3g}. `metrics.csv` contains all runs, native wall, outers, rejects, PCG/outer, retry fraction, initial score and archive source. Numeric/root solve attempts are separately identified in their traces; a root adjustment is not a nonlinear rejection."]
    (P/'NUMBERS.md').write_text('\n\n'.join(sections)+'\n')
    figdir=P/'figures';figdir.mkdir(exist_ok=True)
    fig,axes=plt.subplots(3,1,figsize=(11,12),layout='constrained')
    for ax,(group,arms) in zip(axes,comparisons.items()):
        for arm,a in arms.items():ax.plot(range(9),[c['median_time_ratio'] for c in a['cells']],marker='o',label=LABELS.get(arm,arm))
        ax.axhline(1,color='black',lw=1);ax.set_xticks(range(9),[c['cell'] for c in next(iter(arms.values()))['cells']],rotation=30,ha='right');ax.set_ylabel('Time / matched Eta2');ax.set_title(group+' (N=3 per cell; lower is faster)');ax.legend();ax.grid(alpha=.2)
    for ext in ['png','pdf']:fig.savefig(figdir/('practical_time_ratios.'+ext),dpi=160)
    plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained')
    for rep in range(3):
        for arm,color in [('off','#31688e'),('accurate','#d1495b')]:
            folder=P/'composition'/f'trajectory-{arm}-{rep}'
            if not (folder/'decomposition.json').exists():continue
            rr=load(folder/'decomposition.json');x=[r['attempt'] for r in rr]
            axes[0,rep].plot(x,[r['raw_radius_ratio'] if r['raw_radius_ratio'] is not None else np.nan for r in rr],color=color,label=arm)
            axes[1,rep].plot(x,[r['metadata']['lambda']*r['metadata']['radius']**2 if r['metadata']['radius']>0 else np.nan for r in rr],color=color,label=arm)
        axes[0,rep].set_yscale('log');axes[0,rep].axhline(2,color='black',lw=.8,ls='--');axes[0,rep].set_title('Venice52 diagnostic repetition '+str(rep));axes[0,rep].set_ylabel('Raw camera norm / radius');axes[0,rep].legend()
        axes[1,rep].set_yscale('log');axes[1,rep].set_ylabel('lambda × radius²');axes[1,rep].set_xlabel('Attempt (includes retries)')
    for ext in ['png','pdf']:fig.savefig(figdir/('venice_controller_trajectories.'+ext),dpi=160)
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
    for ax,group in zip(axes,['venice','geodesic-tail']):
        rr=groups[group];rr=[r for r in rr if r['scene']=='venice-52'];arms=['off','forcing_reject','accurate_reference'] if group=='venice' else ['off','geodesic']
        for color,arm in zip(['#31688e','#35b779','#d1495b'],arms):
            for i,r in enumerate([r for r in rr if r['arm']==arm]):
                with (P/r['source']/'curve.csv').open() as f:c=list(csv.DictReader(line for line in f if not line.startswith('#')))
                ax.plot([float(v['wall_s']) for v in c],[float(v['cost']) for v in c],color=color,alpha=.55,label=LABELS.get(arm,arm) if i==0 else None)
        ax.axhline(243740.27,color='black',ls='--',lw=1,label='registered target');ax.set_ylim(240000,275000);ax.set_xlabel('Native seconds (telemetry charged)');ax.set_ylabel('Full objective');ax.legend();ax.grid(alpha=.2)
    axes[0].set_title('Opening attribution, all five repetitions');axes[1].set_title('Native geodesic, all five repetitions')
    fig.suptitle('Venice52 convergence: objective tail view')
    for ext in ['png','pdf']:fig.savefig(figdir/('venice_convergence.'+ext),dpi=160)
    plt.close(fig)
    print('REPORT',len(allrows),'native rows',summary['groups'],flush=True)
if __name__=='__main__':main()
