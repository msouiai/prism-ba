#!/usr/bin/env python3
"""Report registered curvature feature ablation without counting aliases twice."""
import json,math,pathlib,statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=pathlib.Path('/tmp/prism-rl-curvature');REPO=pathlib.Path('/workspace/prism-ba')
LABELS={'baseline':'Prism incumbent','old-cap-2':'Previous CG-cap policy',
        'selected-plain':'Selected without curvature','selected-curv':'Selected with curvature',
        'deterministic':'Fixed curvature rule'}

def read(name):return json.loads((ROOT/name).read_text())
def put(name,obj):(ROOT/name).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
def timing(c):
    if c['hits']!=c['n']:return f"MISS ({c['hits']}/{c['n']}); solve {c['seconds']['median']:.3f}s"
    v=c['target_seconds'];return f"{v['median']:.3f} [{v['min']:.3f}, {v['max']:.3f}]"
def expand(phase):
    cs=read(phase+'-summary.json');aliases=read(phase+'-aliases.json')
    for alias,original in aliases.items():
        cs += [dict(c,arm=alias,alias_of=original) for c in list(cs) if c['arm']==original]
    return cs

def main():
    sel=read('selection.json');transfer=expand('transfer');large=expand('large');allcells=transfer+large
    report={};allratios={a:[] for a in LABELS if a!='baseline'}
    for scene,lam in dict.fromkeys((c['scene'],c['lambda0']) for c in allcells):
        cs={c['arm']:c for c in allcells if c['scene']==scene and c['lambda0']==lam};base=cs['baseline']
        entry={}
        for arm in allratios:
            c=cs[arm];ok=c['hits']==base['hits']==3
            ratio=base['target_seconds']['median']/c['target_seconds']['median'] if ok else None
            allratios[arm].append(ratio);entry[arm]=dict(speedup=ratio,hits=c['hits'],alias_of=c.get('alias_of'))
        report[f'{scene}/{lam}']=entry
    geom={a:math.exp(statistics.mean(math.log(v) for v in vs)) if all(v is not None for v in vs) else None for a,vs in allratios.items()}
    family={k:statistics.mean(v['loss']-v['baseline_loss'] for v in s['family_holdout'].values()) for k,s in sel['selection'].items()}
    ratios=allratios['selected-curv'];promote=(all(v is not None for v in ratios) and min(ratios)>=1/1.05 and geom['selected-curv']>=1.10 and family['curv']<0)
    verdict=dict(promote=promote,selected=sel['selection'],tasks=report,geometric_mean_speedup=geom,
        family_holdout_relative_loss=family,incumbent_retained=not promote)
    put('verdict.json',verdict)
    raws=[json.loads(p.read_text()) for p in (ROOT/'runs').glob('*/result.json')]
    primary=read('transfer-rows.json')+read('large-rows.json')
    metrics=dict(audited_endpoints=len(raws),native_seconds=sum(r['seconds'] for r in raws),
        max_audit_error=max(r['audit_error'] for r in raws),primary_runs=len(primary),primary_hits=sum(r['hit'] for r in primary))
    put('study-metrics.json',metrics)
    diagnostics=[]
    for r in read('transfer-diagnostics.json')+read('large-diagnostics.json'):
        curvature={e['outer']:e for e in r['events'] if e['type']=='curvature'}
        ds=[]
        for e in r['events']:
            if e['type']!='decision':continue
            c=curvature[e['outer']]
            ds.append(dict(outer=e['outer'],action=e['action'],rho=e['features'][2],
                raw_radius_ratio=10**e['features'][4],quad_alpha=c['quad_alpha'],condition=c['condition'],
                spectrum_valid=c['spectrum_valid'],depth=c['depth'],fallback=c['fallback']))
        diagnostics.append(dict(scene=r['scene'],lambda0=r['lambda0'],actions=sum(bool(d['action']) for d in ds),decisions=ds))
    put('diagnostic-summary.json',diagnostics)
    # Align the CSV clock to its adjacent terminal TARGET event for plotting;
    # target times in tables come directly from that event, never this curve.
    lr=read('large-rows.json');fig,axes=plt.subplots(1,2,figsize=(12,4.4))
    colors={'baseline':'#26364a','old-cap-2':'#9c6b23','selected-plain':'#7b57a6','selected-curv':'#00866b','deterministic':'#ce6143'}
    for arm in dict.fromkeys(r['arm'] for r in lr):
        rs=[r for r in lr if r['arm']==arm]
        median=sorted(rs,key=lambda r:r['target_seconds'] if r['hit'] else r['seconds'])[1]
        for r in rs:
            raw=read('runs/'+r['name']+'/result.json');tr=raw['trace']
            shift=r['target_seconds']-tr[-1]['wall_s'] if r['hit'] else 0
            assert shift>=0
            xs=[0]+[x['wall_s']+shift for x in tr if x['iter']>0]
            ys=[tr[0]['cost']/1e6]+[x['cost']/1e6 for x in tr if x['iter']>0]
            for ax in axes:
                ax.step(xs,ys,where='post',color=colors[arm],linewidth=2 if r is median else .7,
                    alpha=1 if r is median else .2,linestyle='--' if arm=='baseline' else '-',
                    zorder=5 if arm=='baseline' else 3,label=LABELS[arm] if r is median else None)
                ax.scatter([r['target_seconds'] if r['hit'] else r['seconds']],[r['audit_cost']/1e6],
                    color=colors[arm],s=18,alpha=1 if r is median else .2)
    for ax in axes:
        ax.axhline(27591576.557625167/1e6,color='black',linestyle=':',label='Fixed target')
        ax.set_xlabel('Native solve time (s)');ax.set_ylabel('L2 cost (millions)');ax.grid(alpha=.15)
        ax.spines[['top','right']].set_visible(False)
    axes[0].set_yscale('log');axes[0].legend(fontsize=8);axes[0].set_title('Recorded full trajectory')
    axes[1].set_ylim(24,60);axes[1].set_title('Near fixed target')
    fig.suptitle('Final-13682 — curvature damping ablation, N=3\nBold = actual median-time run; points = independently audited endpoints')
    fig.tight_layout();folder=ROOT/'figures';folder.mkdir(exist_ok=True)
    for ext in ['png','svg','pdf']:fig.savefig(folder/f'final13682_curvature_policy.{ext}',dpi=150)
    plt.close(fig)
    lines=['# Curvature-informed damping policy results','',
        '**Verdict: '+('candidate passes this bounded pilot gate; broader validation still needed.' if promote else 'retain the incumbent; no general curvature-policy promotion.')+'**','',
        'Finite direct policy search over four controllers per feature class, using complete target-terminated episodes. This is not SAC/PPO or a fitted neural network. All new timings use the same host (2237c6528e79, RTX 2000 Ada) and binary; no production defaults changed.','',
        '## What changed','',
        'The isolated build exposes the full-step GN directional minimizer `-g^T d / ||Jd||^2`, its prior value, and Ritz extrema/condition estimates reconstructed from existing PCG scalars. It adds no GPU matrix products, reductions or observation passes. CPU feature extraction and policy decisions are inside the native target clock. These are previous-outer observations; they cannot anticipate unseen curvature at the next state.','',
        'PCG features describe the preconditioned damped Schur operator, not the true nonlinear Hessian. Spectral estimates are disabled below four CG steps or after invalid recurrence; every CG attempt resets the recurrence. Missing weak directions and finite-precision loss of orthogonality limit their interpretation. Directional alpha describes the actual scored step, which can have been shortened by the radius guard or rescue, so it is not an isolated measurement of excessive lambda.','',
        '## Fresh time-to-target transfer','',
        '| Scene | Initial lambda | Arm | Hits | Seconds: median [min, max] | Audited final cost | Outers | Rejects | Matvecs |',
        '|---|---:|---|---:|---:|---:|---:|---:|---:|']
    for scene,lam in dict.fromkeys((c['scene'],c['lambda0']) for c in allcells):
        cs={c['arm']:c for c in allcells if c['scene']==scene and c['lambda0']==lam}
        for arm in LABELS:
            c=cs[arm];alias=f" (same samples as {c['alias_of']})" if c.get('alias_of') else ''
            lines.append(f"| {scene} | {lam} | {LABELS[arm]}{alias} | {c['hits']}/{c['n']} | {timing(c)} | {c['audit_cost']['median']:.3f} | {c['outers']['median']:.0f} | {c['rejects']['median']:.0f} | {c['matvecs']['median']:.0f} |")
    lines+=['','All targets and caps are unchanged from the registered protocol. Final-13682 has 13,682 cameras, 4,456,117 points and 28,987,644 observations; target 27,591,576.557625167, cap20s. Original observations, SIMPLE_RADIAL/k2=0, half-sum squared pixel errors. Native timing excludes loading, endpoint export and CPU audit. N=3 describes repeat spread, not population confidence. Prior research already used these scenes; they are excluded from this policy fit but are not pristine unseen datasets.','',
        '| Controller | Geometric mean speedup vs incumbent, all five tasks |','|---|---:|']
    for arm,g in geom.items():lines.append(f"| {LABELS[arm]} | {g:.4f}x |" if g is not None else f"| {LABELS[arm]} | Not assigned: a target missed |")
    lines+=['','![Final-13682 curvature ablation](figures/convergence/final13682_curvature_policy.png)','',
        'Plot uses causal staircases. For hits, CSV clocks are aligned to the adjacent terminal TARGET event with a constant offset to include setup; intermediate alignment is approximate because the final feature summary follows the last CSV row. Reported target times come directly from TARGET events, never from interpolating or shifting a crossing. Intermediate costs are native; final points are CPU FP64 audits. Bold traces are real median-time runs. Aliased policies are drawn once. These are target-terminated trajectories, not runs to eventual convergence.','',
        '## Training and family transfer','',
        '162 full episodes: three families, two initial lambdas, nine arms, three repeats. Both feature classes collect the same telemetry during training; only feature access differs. Four candidate templates per class share action size, budget, cooldown and fallback. Primary transfer disables JSON logging. The deterministic comparator was fixed before training.','',
        '| Policy | Mean penalized log-time loss (lower better) |','|---|---:|']
    for a,v in sorted(sel['scores'].items(),key=lambda av:av[1]):lines.append(f'| {a} | {v:+.6f} |')
    for kind,s in sel['selection'].items():
        lines+=['',f"{kind}: training choice including baseline **{s['training_choice']}**; best nonbaseline carried to transfer **{s['selected']}**. Frozen policy SHA256 `{s['policy_sha256']}`.",'',
            '| Omitted family | Choice from other families | Held-family loss minus baseline |','|---|---|---:|']
        for fam,c in s['family_holdout'].items():lines.append(f"| {fam} | {c['selected']} | {c['loss']-c['baseline_loss']:+.6f} |")
    lines+=['','Training loss includes a 4×cap penalty for misses; it is never reported as a measured time to target. The best nonbaseline controller is evaluated for diagnosis even when baseline wins selection. Training outcomes do not override transfer evidence.','',
        '## Mechanism diagnostics (excluded from timing medians)','',
        '| Scene | Initial lambda | Nonzero actions | Decision sequence |','|---|---:|---:|---|']
    for d in diagnostics:lines.append(f"| {d['scene']} | {d['lambda0']} | {d['actions']} | "+', '.join(f"{v['outer']}:{v['action']:+d}" for v in d['decisions'])+' |')
    lines+=['','Full causal decision features (rho, alpha, spectral condition/mask, previous raw camera norm/radius and fallback) are in `diagnostic-summary.json`. A zero-action timing difference is instrumentation or measurement variation, not learned acceleration.','',
        '## Validation and reproducibility','',
        '- Host tests independently compare the reconstructed full PCG Ritz spectrum with a dense preconditioned eigensystem; also cover invalid/short recurrences, reset, budget, cooldown, curvature veto and rejected-outer fallback.',
        '- N=3 parent/new-off/collection-only smoke runs have identical outers/rejects/matvecs and endpoint costs within 1e-7 numerical repeatability. Recorded slope and curvature reconstruct the incumbent model prediction.',
        f"- {metrics['audited_endpoints']} independently audited endpoints; maximum relative native/audit discrepancy {metrics['max_audit_error']:.3g}. Total native solver time {metrics['native_seconds']:.3f}s. Primary transfer/large hits {metrics['primary_hits']}/{metrics['primary_runs']}. Aliases do not add samples.",
        '- [Registered protocol](rl_curvature_protocol.md) and [feature derivations and limitations](rl_curvature_math.md). Source: `gpu/rl_curvature.h`, `gpu/test_rl_curvature.cc`, `bench/build_rl_curvature.py`, `bench/rl_curvature_study.py`, `bench/report_rl_curvature.py`.',
        '- Raw frozen build, policies, manifests, traces and exported endpoints: `/tmp/prism-rl-curvature`. Small durable package: `/workspace/prism-rl-curvature`. No production default changes or new Caspar runs.',
        '- [Previous fresh Caspar comparison](rl_damping_trajectory_results.md) remains separate historical context; its timings are not pooled with this pilot.']
    text='\n'.join(lines)+'\n';(ROOT/'RESULTS.md').write_text(text);(REPO/'docs/rl_curvature_results.md').write_text(text)
    print(json.dumps(verdict,indent=2))

if __name__=='__main__':main()
