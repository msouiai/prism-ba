#!/usr/bin/env python3
import csv,json,re,warnings
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr
from grid_common import P,write,sha
FEATURES=['cost5','cost3','cost10','rho5','reject5','clip5']
def corr(rows,feature):
    pairs=[(r[feature],r['cost']) for r in rows if r.get(feature) is not None]
    if len(pairs)<3 or len(set(a for a,b in pairs))<2 or len(set(b for a,b in pairs))<2:return dict(n=len(pairs),rho=None)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore');c=spearmanr(*np.array(pairs).T)
    return dict(n=len(pairs),rho=float(c.statistic),p=float(c.pvalue))
def features(row):
    folder=P/row['source'];logs=(folder/'stdout.log').read_text()
    attr=[{k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',m)} for m in re.findall(r'^ATTR_RADIUS (.*)$',logs,re.M)]
    curves={int(r['iter']):float(r['cost']) for r in csv.DictReader(x for x in (folder/'curve.csv').read_text().splitlines() if not x.startswith('#'))}
    accepted=sorted(set(int(a['o']) for a in attr if a['accept']==1))
    r=dict(row)
    for k in [3,5,10]:r['cost'+str(k)]=curves.get(accepted[k-1]+1) if len(accepted)>=k else None
    if len(accepted)>=5:
        eligible=[a for a in attr if a['o']<=accepted[4]]
        r['rho5']=float(np.mean([a['rho'] for a in eligible if a['accept']==1]))
        r['reject5']=sum(a['accept']==0 for a in eligible)
        ratios=[a['raw_norm']/max(a['norm'],1e-300) for a in eligible]
        r['clip5']=float(np.median(ratios))
    else:
        for k in FEATURES[3:]:r[k]=None
    return r
def qualify(v):
    a,b,c=(v[x]['rho'] for x in ['full','first','second'])
    return v['full']['n']>=16 and all(x is not None and abs(x)>=.4 for x in [a,b,c]) and a*b>0 and b*c>0
def main():
    source=json.loads((P/'predictor-results.json').read_text());assert len(source)==40 and all(r['valid'] for r in source)
    rows=[features(r) for r in source];result={}
    for scene in ['ladybug-1197','final-3068']:
        rr=sorted([r for r in rows if r['scene']==scene],key=lambda r:r['rep']);assert [r['rep'] for r in rr]==list(range(20))
        ff={f:dict(full=corr(rr,f),first=corr(rr[:10],f),second=corr(rr[10:],f)) for f in FEATURES}
        for v in ff.values():v['passes']=qualify(v)
        selected='cost5' if ff['cost5']['passes'] else None
        if selected is None:
            candidates=[f for f in FEATURES[1:] if ff[f]['first']['rho'] is not None and abs(ff[f]['first']['rho'])>=.4]
            if candidates:
                chosen=max(candidates,key=lambda f:abs(ff[f]['first']['rho']))
                if ff[chosen]['passes']:selected=chosen
            else:chosen=None
        else:chosen=None
        result[scene]=dict(features=ff,selected=selected,training_selected_alternative=chosen,
          endpoint_median=float(np.median([r['cost'] for r in rr])),endpoint_range=[min(r['cost'] for r in rr),max(r['cost'] for r in rr)],
          native_total=sum(r['native_seconds'] for r in rr),score_init_range=[min(r['score_init'] for r in rr),max(r['score_init'] for r in rr)])
    summary=dict(protocol_sha256=sha(P/'PROTOCOL_05_PRETEST.md'),scenes=result,racing_gate=all(r['selected'] is not None for r in result.values()))
    write(P/'predictor-analysis.json',summary);write(P/'predictor-feature-rows.json',rows)
    lines=['# Brief 5: early-trajectory predictor pre-test','',
      'Forty fresh full-budget frozen Eta2 runs, twenty per scene. Every endpoint passed the independent original-observation FP64 audit. No input, damping, forcing or stopping-policy tuning. These repeated atomics-order executions are not controllable RNG seeds.','',
      '| Scene | Feature | Full rho | First-half rho | Held-out-half rho | Registered gate |','|---|---|---:|---:|---:|---|']
    fmt=lambda x:'undefined' if x is None else f'{x:+.3f}'
    for sc,s in result.items():
        for f,v in s['features'].items():lines.append(f"| {sc} | {f} | {fmt(v['full']['rho'])} | {fmt(v['first']['rho'])} | {fmt(v['second']['rho'])} | {v['passes']} |")
    lines+=['',f"Both-scene racing gate: **{summary['racing_gate']}**. Selection follows the committed first-half/held-out-half rule; all alternatives and ties remain visible.",'',
      'Costs at accepted outer3/5/10 are native trace readings; final cost is independently audited. A raw full-cohort correlation by itself is not the registered decision. This cohort is a predictor screen, not a measured racing benefit or a time-to-target comparison. A failed gate does not refute front-loaded accuracy, which is a separate intervention.']
    (P/'PREDICTOR_FINDINGS.md').write_text('\n'.join(lines)+'\n')
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,3,figsize=(12,6),constrained_layout=True)
    for i,scene in enumerate(result):
        rr=[r for r in rows if r['scene']==scene]
        for j,k in enumerate([3,5,10]):
            ax=axes[i,j];valid=[r for r in rr if r['cost'+str(k)] is not None]
            ax.scatter([r['cost'+str(k)] for r in valid],[r['cost'] for r in valid],c=[r['rep'] for r in valid],cmap='viridis')
            ax.set(xlabel=f'Cost after accepted outer {k}',ylabel='Audited endpoint cost',title=f"{scene}; rho={fmt(result[scene]['features']['cost'+str(k)]['full']['rho'])}")
            ax.ticklabel_format(axis='both',style='sci',scilimits=(0,0))
    dest=P/'figures';dest.mkdir(exist_ok=True);fig.savefig(dest/'opening_predictor.png',dpi=170);fig.savefig(dest/'opening_predictor.pdf');plt.close(fig)
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
