#!/usr/bin/env python3
"""Audited complete-trajectory policy-selection report and largest-scene curves."""
import json, math, pathlib, re, statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from rl_damping_trajectory import ROOT,LARGE_TARGET

REPO=pathlib.Path('/workspace/prism-ba')
LABELS={'baseline':'Prism incumbent','feedback':'Trajectory-selected feedback','opening-2':'Opening ×2',
        'caspar32':'Caspar FP32','caspar64':'Caspar FP64'}
COLORS={'baseline':'#63758b','feedback':'#16856f','opening-2':'#d88a32','caspar32':'#2d80c2','caspar64':'#925daf'}

def timing(c):
    if c['hits']!=c['n']:return f"MISS ({c['hits']}/{c['n']}); solve {c['seconds']['median']:.3f} s"
    t=c['target_seconds'];return f"{t['median']:.3f} [{t['min']:.3f}, {t['max']:.3f}]"

def main():
    selection=json.loads((ROOT/'selection.json').read_text())
    transfer=json.loads((ROOT/'transfer-summary.json').read_text())
    large=json.loads((ROOT/'large-summary.json').read_text())
    lr=json.loads((ROOT/'large-rows.json').read_text());assert len(lr)==15
    diag=json.loads((ROOT/'large-policy-diagnostic.json').read_text())
    verdict={};ratios=[];reliable=True
    for scene,lam in dict.fromkeys((c['scene'],c['lambda0']) for c in transfer):
        cells={c['arm']:c for c in transfer if c['scene']==scene and c['lambda0']==lam}
        b,f=cells['baseline'],cells['feedback']
        ok=b['hits']==f['hits']==3
        ratio=b['target_seconds']['median']/f['target_seconds']['median'] if ok else None
        verdict[f'{scene}/{lam}']=dict(feedback_speedup=ratio,baseline_hits=b['hits'],feedback_hits=f['hits'])
        if ratio is not None:ratios.append(ratio)
        else:reliable=False
    lc={c['arm']:c for c in large};assert all(c['n']==3 for c in large)
    winner=min([a for a,c in lc.items() if c['hits']==3],key=lambda a:lc[a]['target_seconds']['median'])
    large_ratio=lc['baseline']['target_seconds']['median']/lc['feedback']['target_seconds']['median'] if lc['baseline']['hits']==lc['feedback']['hits']==3 else None
    heldout=sum(v['loss']-v['baseline_loss'] for v in selection['family_holdout'].values())/len(selection['family_holdout'])
    promote=reliable and len(ratios)==6 and min(ratios)>=1/1.05 and statistics.median(ratios)>=1.10 and heldout<0 and large_ratio is not None and large_ratio>=1/1.05
    report=dict(selected_feedback=selection['selected_feedback'],transfer=verdict,large_winner=winner,
                large_feedback_speedup=large_ratio,median_transfer_speedup=statistics.median(ratios) if ratios else None,
                family_heldout_relative_loss=heldout,promote=promote,
                large_active_actions=sum(d['action']!=0 for d in diag['actions']))
    report['large_algorithm_winner']='baseline' if winner=='feedback' and report['large_active_actions']==0 else winner
    prism_runs=[json.loads(p.read_text()) for p in (ROOT/'runs').glob('*/result.json')]
    caspar_runs=[json.loads(p.read_text()) for p in (ROOT/'caspar').glob('*.result.json')]
    extra=json.loads((ROOT/'abandoned-collector-audit.json').read_text())
    metrics=dict(audited_endpoints=len(prism_runs)+len(caspar_runs)+1,
        native_seconds=sum(r['seconds'] for r in prism_runs+caspar_runs)+extra['native_seconds'],
        max_audit_error=max([r['audit_error'] for r in prism_runs+caspar_runs]+[extra['audit_error']]),
        primary_target_runs=69,primary_hits=sum(r['hit'] for r in json.loads((ROOT/'transfer-rows.json').read_text())+lr))
    (ROOT/'study-metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
    (ROOT/'verdict.json').write_text(json.dumps(report,indent=2)+'\n')
    curves=[]
    for r in lr:
        if r['arm'].startswith('caspar'):
            text=pathlib.Path(r['artifact']+'.log').read_text()
            initial=float(re.search(r'^INITIAL score=(\S+)',text,re.M)[1])
            points=[(0.,initial)]+[(float(t),float(c)) for c,t in re.findall(r'TRACE iter=\d+ cost=(\S+) seconds=(\S+)',text)]
        else:
            raw=json.loads((ROOT/'runs'/r['name']/'result.json').read_text());csv=raw['trace']
            if r['hit']:
                shift=r['target_seconds']-csv[-1]['wall_s']
                assert shift>=0 and abs(csv[-1]['cost']-raw['native_cost'])<1e-6*max(1,raw['native_cost'])
                points=[(0.,csv[0]['cost'])]+[(x['wall_s']+shift,x['cost']) for x in csv if x['iter']>0]
            else:points=[(0.,csv[0]['cost'])] # No unsupported setup-clock alignment for misses.
        end=r['target_seconds'] if r['hit'] else r['seconds']
        if points[-1][0]<end:points.append((end,points[-1][1]))
        assert all(math.isfinite(t) and math.isfinite(c) and t>=0 and c>0 for t,c in points)
        assert all(b[0]>=a[0] and b[1]<=a[1]*(1+1e-7) for a,b in zip(points,points[1:]))
        curves.append(dict(arm=r['arm'],rep=r['rep'],points=points,end=end,audit_cost=r['audit_cost'],hit=r['hit']))
    (ROOT/'large-curves.json').write_text(json.dumps(curves,indent=2)+'\n')
    fig,axes=plt.subplots(1,2,figsize=(12,4.6))
    for arm in LABELS:
        runs=[c for c in curves if c['arm']==arm]
        med=sorted(runs,key=lambda c:c['end'])[1]
        for c in runs:
            xs,ys=zip(*c['points']);ys=[v/1e6 for v in ys]
            for ax in axes:
                label='Prism feedback (0 interventions)' if arm=='feedback' and report['large_active_actions']==0 else LABELS[arm]
                ax.step(xs,ys,where='post',color=COLORS[arm],alpha=1 if c is med else .22,
                        linewidth=2.2 if c is med else .8,linestyle='--' if arm=='baseline' else '-',
                        zorder=4 if arm=='baseline' else 3,label=label if c is med else None)
                ax.scatter([c['end']],[c['audit_cost']/1e6],color=COLORS[arm],marker='D',s=24 if c is med else 10,alpha=1 if c is med else .25)
    for ax in axes:
        ax.axhline(LARGE_TARGET/1e6,color='#222',linestyle='--',linewidth=1,label='Fixed target')
        ax.set_xlabel('Native solve time (seconds)');ax.set_ylabel('L2 cost (millions)')
        ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.15)
    axes[0].set_yscale('log');axes[0].set_title('Full convergence');axes[0].legend(fontsize=8)
    axes[1].set_ylim(24,60);axes[1].set_title('Near useful-quality target')
    fig.suptitle('Final-13682: frozen complete-trajectory feedback vs incumbent and Caspar\nN=3 per arm; bold = actual median-time run; diamonds = audited endpoints')
    fig.tight_layout();folder=REPO/'docs/figures/convergence';folder.mkdir(exist_ok=True)
    for ext in ['png','svg','pdf']:fig.savefig(folder/f'final13682_trajectory_policy.{ext}',dpi=170)
    plt.close(fig)
    lines=['# Complete-trajectory damping-policy search','',
      '**Verdict: '+('candidate passes this bounded transfer gate; broader deployment validation remains necessary.' if promote else 'retain the incumbent; no general promotion.')+'**','',
      f"Selected feedback policy: **{selection['selected_feedback']}**. Selection uses complete target-terminated training episodes, including every repeated intervention and fallback. This is finite direct policy search over eight small feedback controllers, not SAC/PPO or a fitted value network. The baseline remains a selection option, and opening-2 is an additional fixed comparator.",'',
      '## Largest BAL scene: fresh comparison','',
      'Final-13682 has 13,682 cameras, 4,456,117 points, and 28,987,644 observations. It is excluded from training and policy selection. Fixed historical target: **27,591,576.557625167**, initial Prism lambda0.1,20-second native cap,600-outer/attempt cap,N=3. All arms use SIMPLE_RADIAL with k2 fixed to zero; cost is half the sum of squared pixel residuals on the original observations. Same host 2237c6528e79 / RTX 2000 Ada.','',
      '| Algorithm | Hits | Target time: median [min, max] s | Audited endpoint cost | Outers | Rejects |',
      '|---|---:|---:|---:|---:|---:|']
    for arm in LABELS:
        c=lc[arm];lines.append(f"| {LABELS[arm]} | {c['hits']}/3 | {timing(c)} | {c['audit_cost']['median']:.3f} | {c['outers']['median']:.0f} | {c['rejects']['median']:.0f} |")
    lines+=['',f"The fastest median on this scene is {LABELS[winner]}. Feedback/incumbent speedup: {large_ratio:.4f}x." if large_ratio else 'The feedback arm does not retain all baseline hits; no equal-quality speedup is assigned.','']
    for arm in ['baseline','feedback']:
        for ref in ['caspar32','caspar64']:
            if lc[arm]['hits']==lc[ref]['hits']==3:
                speedup=lc[ref]['target_seconds']['median']/lc[arm]['target_seconds']['median']
                lines.append(f"{LABELS[arm]} versus {LABELS[ref]}: {speedup:.3f}x at the common target.")
    lines+=['','![Largest-scene convergence](figures/convergence/final13682_trajectory_policy.png)','',
      f"The separate mechanism trace applies {report['large_active_actions']} nonzero policy actions. Logged decisions: "+', '.join(f"outer{d['outer']}={d['action']:+d}" for d in diag['actions'])+'. This diagnostic is excluded from timing medians. '+('The feedback policy abstains throughout: its near-baseline timing does not establish a learned acceleration.' if report['large_active_actions']==0 else 'The policy actively changes damping; the complete-solve comparison includes the consequences.'),'',
      'Curves are causal staircases of recorded costs; no interpolated crossing. Prism CSV times are shifted to the adjacent terminal TARGET event to include local setup. Caspar uses native TRACE/runtime clocks. Graph setup is excluded for Caspar and reported in raw rows; loading, export and CPU audits are excluded for both. Internal curve points are not individually rescored; final diamonds are independent original-observation FP64 audits. FP32 uses the predeclared 0.1% inward native threshold. Curves stop at recorded endpoints, not eventual convergence.','',
      '## Frozen transfer panel','',
      '| Scene | Initial lambda | Arm | Hits | Target seconds: median [min, max] | Cost | Matvecs |',
      '|---|---:|---|---:|---:|---:|---:|']
    for c in transfer:
        lines.append(f"| {c['scene']} | {c['lambda0']} | {c['arm']} | {c['hits']}/3 | {timing(c)} | {c['audit_cost']['median']:.3f} | {c['matvecs']['median']:.0f} |")
    lines+=['','Targets and arms are frozen before these outcomes. Both initial lambdas are evaluated to expose configuration dependence rather than silently switch to a favorable setting. These scenes have been seen in prior research and are not pristine recordings.','',
      '## Training returns and family checks','',
      '180 complete training episodes: three families × two initial lambdas × ten configurations × three repeats. Three reference endpoints define 1%-tolerant training targets. The 32 initial trials at tighter targets were abandoned and retained separately; the correction was made after seeing development outcomes, before any transfer results. See the dated protocol amendment.','',
      '| Policy | Mean penalized log-time loss (lower better) |','|---|---:|']
    for arm,score in sorted(selection['scores'].items(),key=lambda x:x[1]):lines.append(f'| {arm} | {score:+.6f} |')
    lines+=['',f"The full-data training choice including baseline is {selection['training_choice']}. The best nonbaseline feedback policy is still carried to transfer for diagnosis. Loss uses matched baseline timing as denominator; misses receive a 4×cap penalty for training only, never a reported target time or speedup.",'',
      '| Omitted training family | Policy selected using other families | Held-out log loss | Baseline log loss |',
      '|---|---|---:|---:|']
    for family,c in selection['family_holdout'].items():lines.append(f"| {family} | {c['selected']} | {c['loss']:+.6f} | {c['baseline_loss']:+.6f} |")
    lines+=['',
      'The optimized quantity is J(theta) = mean_task mean_repeat log(T_theta / median_repeat T_baseline), with the declared terminal miss penalty. The same theta controls every decision within an episode. This directly includes the consequences of repeated actions and the runtime of policy inference. It does not rely on a critic fitted to isolated interventions.','',
      'For an intervention budget B, sum_k |a_k| <= B with a_k in {-1,0,+1}; the raw multiplicative corrections therefore have product between 10^(-B) and 10^B before clipping. The cooldown also prevents consecutive nonzero corrections. This bounds the added damping interventions, not regret against a counterfactual baseline trajectory: accepted geometry and subsequent baseline radius/lambda updates can differ.','',
      'Fallback preserves the incumbent acceptance and numerical safeguards and stops further interventions after poor agreement, tiny progress, rejection or repair. It does not restore the counterfactual baseline geometry or guarantee baseline speed. Budget and cooldown prevent indefinite repeated damping increases. Policies are selected from full closed-loop outcomes rather than one-action baseline continuations.','',
      '## Verification and artifacts','',
      '- N=3 old-binary/new-off/zero-policy compatibility: equal work counts and costs within GPU numerical repeatability. Host tests cover intervention budget, cooldown, support abstention, permanent fallback including exhausted rejected outers, and rejection of unsupported replay.',
      '- All claimed hits require independent original-observation FP64 endpoint audits. Frozen binary, policy and dataset hashes, commands, target thresholds, caps and complete raw traces are retained.',
      f"- {metrics['audited_endpoints']} independently audited endpoints in total, including the abandoned development trials and one completed solver run whose collector was interrupted. That extra run is audited separately and excluded from fitting/headline timing. Maximum relative audit discrepancy {metrics['max_audit_error']:.3g}. Total native solver time {metrics['native_seconds']:.3f} seconds, below the 900-second study ceiling. Primary transfer/large target hits: {metrics['primary_hits']}/69.",
      '- [Protocol and disclosed training correction](rl_damping_trajectory_protocol.md). Code: `gpu/rl_damping.h`, `gpu/test_rl_episode.cc`, `bench/rl_damping_trajectory.py`, `bench/report_rl_damping_trajectory.py`.',
      '- Full raw evidence: `/tmp/prism-rl-damping-trajectory/`; persistent compact package: `/workspace/prism-rl-damping-trajectory/`. No production defaults changed.',
      '', 'N=3 describes repeat spread. A small, correlated research panel does not establish broad generalization or RL novelty.']
    text='\n'.join(lines)+'\n';(ROOT/'RESULTS.md').write_text(text);(REPO/'docs/rl_damping_trajectory_results.md').write_text(text)
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
