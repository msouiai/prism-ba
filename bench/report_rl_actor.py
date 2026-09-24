#!/usr/bin/env python3
"""Audited report for learned damping/forcing and reward variants."""
import json,math,pathlib,statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=pathlib.Path('/tmp/prism-rl-actor');REPO=pathlib.Path('/workspace/prism-ba')
LABELS={'baseline':'Prism incumbent','lambda-time':'RL damping / time reward',
        'joint-time':'RL damping + CG / time reward','joint-rate':'RL damping + CG / gain-rate reward',
        'fixed-eta2':'Fixed CG tolerance ×2'}
COLORS={'baseline':'#26364a','lambda-time':'#9564aa','joint-time':'#00866b','joint-rate':'#cf6941','fixed-eta2':'#377cb3'}
def read(name):return json.loads((ROOT/name).read_text())
def put(name,obj):(ROOT/name).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
def fmt(c):
    if c['hits']!=c['n']:return f"MISS {c['hits']}/{c['n']}; solve {c['seconds']['median']:.3f}s"
    v=c['target_seconds'];return f"{v['median']:.3f} [{v['min']:.3f}, {v['max']:.3f}]"
def compare(cells,labels=LABELS):
    ratios={a:[] for a in labels if a!='baseline'};tasks={}
    for scene,lam in dict.fromkeys((c['scene'],c['lambda0']) for c in cells):
        cs={c['arm']:c for c in cells if c['scene']==scene and c['lambda0']==lam};b=cs['baseline'];task={}
        for a in ratios:
            if a not in cs:continue
            c=cs[a];ok=b['hits']==b['n'] and c['hits']==c['n'] and min(b['n'],c['n'])>=3
            v=b['target_seconds']['median']/c['target_seconds']['median'] if ok else None
            ratios[a].append(v);task[a]=dict(speedup=v,hits=c['hits'])
        tasks[f'{scene}/{lam}']=task
    geo={a:math.exp(statistics.mean(math.log(v) for v in vs)) if vs and all(v is not None for v in vs) else None for a,vs in ratios.items()}
    return tasks,ratios,geo

def main():
    transfer=read('transfer-summary.json');large=read('large-summary.json');cells=transfer+large
    tasks,ratios,geo=compare(cells);_,_,train_geo=compare(read('training-eval-summary.json'))
    winners={'baseline':1.,**{a:g for a,g in geo.items() if g is not None}};best=max(winners,key=winners.get)
    promising=[a for a,g in geo.items() if g is not None and g>=1.1 and min(ratios[a])>=1/1.1]
    stochastic=read('stochastic-summary.json');stoch_labels={a:v for a,v in LABELS.items() if a!='fixed-eta2'}
    stoch_labels['untrained-joint']='Untrained joint sampler'
    stasks,sratios,sgeo=compare(stochastic,stoch_labels)
    spromising=[a for a,g in sgeo.items() if g is not None and g>=1.1 and min(sratios[a])>=1/1.1]
    verdict=dict(best_point_estimate=best,geometric_mean_speedup=geo,training_geometric_mean_speedup=train_geo,
        tasks=tasks,promising=promising,incumbent_retained=not promising,
        caveat='Only one fitted training seed per actor. N=3 describes fixed-policy solver repeats, not retraining stability. A promising candidate needs confirmation before default promotion.')
    verdict['stochastic']=dict(tasks=stasks,geometric_mean_speedup=sgeo,promising=spromising)
    verdict['incumbent_retained']=not(promising or spromising)
    put('verdict.json',verdict)
    runs=[json.loads(p.read_text()) for p in (ROOT/'runs').glob('*/result.json')]
    primary=read('transfer-rows.json')+read('large-rows.json')+read('stochastic-rows.json')
    metrics=dict(audited_endpoints=len(runs),native_seconds=sum(r['seconds'] for r in runs),
        maximum_audit_error=max(r['audit_error'] for r in runs),primary_runs=len(primary),primary_hits=sum(r['hit'] for r in primary),
        training_episodes=288)
    put('study-metrics.json',metrics)
    diagnostics=[]
    for d in read('transfer-diagnostics.json')+read('large-diagnostics.json'):
        ev=[e for e in d['events'] if e['type']=='actor']
        diagnostics.append(dict(scene=d['scene'],lambda0=d['lambda0'],arm=d['arm'],
            nonzero_requests=sum(e['action']!=0 for e in ev),
            decisions=[dict(outer=e['outer'],action=e['action'],probabilities=e['probabilities']) for e in ev]))
    put('diagnostic-summary.json',diagnostics)
    folder=ROOT/'figures';folder.mkdir(exist_ok=True)
    fig,ax=plt.subplots(figsize=(8,4.6));learning=read('learning-metrics.json')
    for a in ['lambda-time','joint-time','joint-rate']:
        rs=[r for r in learning if r['experiment']==a]
        ax.plot([r['batch']+1 for r in rs],[r['geometric_relative_time'] for r in rs],marker='o',color=COLORS[a],label=LABELS[a])
    ax.axhline(1,color=COLORS['baseline'],linestyle='--',label='Measured reference')
    ax.set_xlabel('Policy-gradient update');ax.set_ylabel('Geometric relative training time\n(miss penalties included; lower is better)')
    ax.set_title('Exploratory training scores — changing policies, 12 tasks/update')
    ax.legend(fontsize=8);ax.grid(alpha=.15);fig.tight_layout()
    for ext in ['png','svg']:fig.savefig(folder/f'actor_training.{ext}',dpi=150)
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4.5));lr=read('large-rows.json')
    for a in LABELS:
        rs=[r for r in lr if r['arm']==a];median=sorted(rs,key=lambda r:r['target_seconds'] if r['hit'] else r['seconds'])[1]
        for r in rs:
            raw=read('runs/'+r['name']+'/result.json');tr=raw['trace'];shift=r['target_seconds']-tr[-1]['wall_s'] if r['hit'] else 0
            assert shift>=0
            xs=[0]+[p['wall_s']+shift for p in tr if p['iter']>0];ys=[tr[0]['cost']/1e6]+[p['cost']/1e6 for p in tr if p['iter']>0]
            for ax in axes:
                ax.step(xs,ys,where='post',color=COLORS[a],alpha=1 if r is median else .2,
                    linewidth=2 if r is median else .7,linestyle='--' if a=='baseline' else '-',
                    zorder=5 if a=='baseline' else 3,label=LABELS[a] if r is median else None)
                ax.scatter([r['target_seconds'] if r['hit'] else tr[-1]['wall_s']],[r['audit_cost']/1e6],color=COLORS[a],s=18,alpha=1 if r is median else .2)
    for ax in axes:
        ax.axhline(27591576.557625167/1e6,color='black',linestyle=':',label='Fixed target');ax.grid(alpha=.15)
        ax.set_xlabel('Native solve time (s)');ax.set_ylabel('L2 cost (millions)');ax.spines[['top','right']].set_visible(False)
    axes[0].set_yscale('log');axes[0].legend(fontsize=8);axes[0].set_title('Recorded trajectory')
    axes[1].set_ylim(24,60);axes[1].set_title('Near fixed target')
    fig.suptitle('Final-13682 — learned damping/CG controls and reward ablation\nN=3; bold = actual median-time run; points = audited endpoints')
    fig.tight_layout()
    for ext in ['png','svg','pdf']:fig.savefig(folder/f'final13682_rl_actor.{ext}',dpi=150)
    plt.close(fig)
    lines=['# Learned damping/CG control and reward comparison','',
        '**Verdict: '+('candidate(s) pass the bounded pilot gate and require confirmation: '+', '.join(promising+['sampled '+a for a in spromising]) if promising or spromising else 'retain the incumbent; no general learned-policy promotion.')+'**','',
        f"Best aggregate point estimate: {LABELS[best]}. All results use host2237c6528e79 / RTX2000 Ada. These are new matched comparisons; previous Caspar timings are not pooled with them.",'',
        '## What was tested','',
        'Three on-policy REINFORCE actors with linear logits on20 bounded nonlinear/history features: damping-only with a time reward (60 parameters), joint damping/CG accuracy with a time reward (100), and the same joint action space with a summed gain-rate reward (100). This is fitted stochastic-policy learning, not a threshold grid or SAC/PPO. Eight updates ×12 tasks =96 episodes per actor. Final weights are frozen, then evaluated greedily.','',
        'Lambda corrections are factors1/2 or2, with baseline always available. Joint actors can halve/double the forcing tolerance for one outer, capped at.5. At most3 nonzero actions, an idle boundary between them, temporary abstention after bad agreement/rejection and permanent abstention after numerical repair. Incumbent true-objective acceptance, radius guard, rescue and residual verification remain in force. A fixed eta×2 comparator separates learning from a useful constant setting.','',
        '## Greedy policies: fresh time-to-target results','',
        '| Scene | Initial lambda | Arm | Hits | Seconds: median[min,max] | Audited cost | Outers | Rejects | Matvecs |',
        '|---|---:|---|---:|---:|---:|---:|---:|---:|']
    for scene,lam in dict.fromkeys((c['scene'],c['lambda0']) for c in cells):
        cs={c['arm']:c for c in cells if c['scene']==scene and c['lambda0']==lam}
        for a in LABELS:
            c=cs[a];lines.append(f"| {scene} | {lam} | {LABELS[a]} | {c['hits']}/{c['n']} | {fmt(c)} | {c['audit_cost']['median']:.3f} | {c['outers']['median']:.0f} | {c['rejects']['median']:.0f} | {c['matvecs']['median']:.0f} |")
    lines+=['','| Arm | Geometric mean speedup, five transfer tasks | Training-task speedup, greedy N=3 |','|---|---:|---:|']
    for a in list(LABELS)[1:]:
        g=geo[a];tg=train_geo[a]
        lines.append(f"| {LABELS[a]} | "+(f'{g:.4f}x' if g is not None else 'Not assigned: target miss')+' | '+(f'{tg:.4f}x' if tg is not None else 'Not assigned / not evaluated')+' |')
    lines+=['','Targets/caps are unchanged from the preceding curvature comparison. Final13682:13,682 cameras,4,456,117 points,28,987,644 observations; target27,591,576.557625167, cap20s. All use original observations, SIMPLE_RADIAL/k2=0, half-sum squared pixel error. Muell lambda.1 and10 are related settings, not independent scenes. Native clocks include policy/features/solver work, exclude input loading, state export and CPU audit.','',
        '![Largest-scene convergence](figures/convergence/final13682_rl_actor.png)','',
        'Curves are recorded-cost staircases; no interpolated target crossing. Successful CSV clocks are aligned to adjacent terminal TARGET events by a constant setup offset; intermediate alignment is approximate. Misses retain CSV clocks. Table target times come directly from TARGET events and require an independent endpoint audit. No eventual-convergence claims are made from these target-terminated curves.','',
        '## Frozen stochastic policies: separate matched comparison','',
        'Before any transfer result was read, a registered training-side amendment added sampling evaluation: all three greedy actors chose baseline on the collected training states. Preserve those greedy results and test the trained stochastic behavior against a fresh baseline and an untrained five-action sampler. Medium tasks use N=5 and Final13682 uses N=3, seeds910000+repeat, with logging off. This panel is not pooled with the greedy timings. The untrained joint sampler matches the joint actors action space; it is not a matched untrained control for the damping-only actor.','',
        '| Scene | Initial lambda | Sampling arm | Hits | Seconds: median[min,max] | Audited cost | Outers | Rejects | Matvecs |',
        '|---|---:|---|---:|---:|---:|---:|---:|---:|']
    for scene,lam in dict.fromkeys((c['scene'],c['lambda0']) for c in stochastic):
        cs={c['arm']:c for c in stochastic if c['scene']==scene and c['lambda0']==lam}
        for a in stoch_labels:
            c=cs[a];lines.append(f"| {scene} | {lam} | {stoch_labels[a]} | {c['hits']}/{c['n']} | {fmt(c)} | {c['audit_cost']['median']:.3f} | {c['outers']['median']:.0f} | {c['rejects']['median']:.0f} | {c['matvecs']['median']:.0f} |")
    lines+=['','| Sampling arm | Geometric mean speedup vs this panel baseline |','|---|---:|']
    for a,g in sgeo.items():lines.append(f"| {stoch_labels[a]} | "+(f'{g:.4f}x' if g is not None else 'Not assigned: target miss')+' |')
    lines+=['','Sampling distributions include action randomness as well as GPU numerical/timing variation. A better training reward is not necessarily a faster sampled deployment. Original and amended protocols, timing of the amendment and hashes are preserved in the evidence.','',
        '## Reward and training evidence','',
        'The time actor receives negative remaining native seconds divided by a measured task reference, plus remaining capped progress as a potential term. Failure receives an additional4×cap/reference penalty. The potential telescopes to a constant across absorbing trajectories and preserves the underlying time objective; it does not create new information. Training optimizes expected normalized time, whereas the reporting aggregate is geometric mean median speedup.','',
        'The gain-rate actor sums per-outer normalized gain divided by normalized duration. This is intentionally a different objective: splitting an unchanged constant-rate trajectory into two steps can double that reward. Total capped gain alone is also insufficient: it equals1 for every successful solve. The implementation tests both statements and the softmax gradient.','',
        'Training logs include per-action probabilities/features and native timestamps. A ridge value baseline uses only earlier batches; current samples do not fit their own baselines. Greedy deployment differs from exploratory training. Per-action training logging adds overhead absent in performance runs; this bounded pilot does not claim to estimate deployment rewards without that instrumentation difference.','',
        '![Exploratory training](figures/convergence/actor_training.png)','',
        'Training uses six scenes (Ladybug49/598,Dubrovnik88/356,Venice52/89), each at lambda.1 and10. Three added small-scene targets are frozen from eight-outer parent reference endpoints; the other targets are inherited unchanged. All twelve reference tasks hit reliably. Transfer families are excluded from this fit but are familiar from prior research. There is one fitted training seed per actor: N=3 solver repeats do not establish retraining stability.','',
        '## Separate mechanism traces','',
        '| Scene | Initial lambda | Actor | Nonzero requests | Eligible decision sequence |','|---|---:|---|---:|---|']
    amap={0:'base',1:'lambda/2',2:'lambda*2',3:'eta/2',4:'eta*2'}
    for d in diagnostics:lines.append(f"| {d['scene']} | {d['lambda0']} | {d['arm']} | {d['nonzero_requests']} | "+', '.join(f"{v['outer']}:{amap[v['action']]}" for v in d['decisions'])+' |')
    lines+=['','These labeled diagnostics are excluded from timing medians. A requested eta change can saturate at its cap; request counts are not proof of effective changes. Forced abstentions and cooldowns do not sample a policy action. Full probabilities and feature histories are retained.','',
        '## Verification and artifacts','',
        f"{metrics['audited_endpoints']} original-observation FP64 endpoint audits; maximum relative native/audit discrepancy {metrics['maximum_audit_error']:.3g}. Native solver total {metrics['native_seconds']:.3f}s; primary target hits {metrics['primary_hits']}/{metrics['primary_runs']}. Calibration, fitting, greedy training evaluations and diagnostics are separate from the75 greedy and115 stochastic primary repeats.",'',
        'Host checks cover softmax finite differences, Python/C++ probabilities, potential telescoping, failure handling, gain-rate partition counterexample, forcing bounds, action mapping, budget/cooldown, repeated-outer idempotence and repair abstention. N=3 parent/new-off/zero-actor smoke runs preserve work counts and costs within1e-7 GPU numerical repeatability.','',
        '- [Registered protocol](rl_actor_protocol.md), [research and reward derivations](rl_reward_control_research.md), [preceding curvature results](rl_curvature_results.md).',
        '- Code: `gpu/rl_actor.h`, `gpu/test_rl_actor.cc`, `bench/build_rl_actor.py`, `bench/rl_actor_study.py`, `bench/test_rl_actor.py`, `bench/report_rl_actor.py`, `bench/audit_rl_rewards.py`.',
        '- Raw frozen build, policy snapshots, seeds, gradient/value data, manifests, traces and endpoints: `/tmp/prism-rl-actor/`. Durable reports/package: `/workspace/prism-rl-actor/`. No production defaults or new Caspar binaries changed.']
    text='\n'.join(lines)+'\n';(ROOT/'RESULTS.md').write_text(text);(REPO/'docs/rl_actor_results.md').write_text(text)
    print(json.dumps(verdict,indent=2))
if __name__=='__main__':main()
