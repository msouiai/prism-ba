#!/usr/bin/env python3
"""Summarize the extended pilot without overwriting first-pilot evidence."""
import json, pathlib, statistics
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from rl_damping_extended import ROOT,SCENES
from rl_damping_pilot import sha

def main():
    a=json.loads((ROOT/'analysis.json').read_text())
    v=json.loads((ROOT/'validation-summary.json').read_text())
    arms=['baseline','old-learned','extended-learned','opening-2','work-rule']
    labels=['Guarded','First learned','Extended learned','Opening ×2','CG-cap rule']
    colors=['#697a91','#aa7788','#207dae','#369477','#c78d39']
    records=[json.loads(p.read_text()) for p in (ROOT/'runs').glob('*/result.json')]
    ratios={arm:[] for arm in arms}
    winners={}
    for scene,cs in v['scenes'].items():
        for arm in arms:
            c=cs[arm];assert c['n']==3
            if c['hits']==3:ratios[arm].append(cs['baseline']['target_seconds']['median']/c['target_seconds']['median'])
        winners[scene]=min([arm for arm in arms if cs[arm]['hits']==3],key=lambda arm:cs[arm]['target_seconds']['median'])
    promote={}
    for arm in arms[1:]:
        rs=ratios[arm]
        promote[arm]=len(rs)==len(SCENES) and statistics.median(rs)>=1.10 and min(rs)>=1/1.05
        if arm=='extended-learned':promote[arm]=promote[arm] and a['mean_advantage']>0
        if arm=='old-learned':promote[arm]=False # Its prior failed transfer is retained.
    screen_promote=promote.copy()
    champion_rows=json.loads((ROOT/'champion-check-rows.json').read_text())
    champion={}
    for arm in ['baseline','opening-2']:
        rs=[r for r in champion_rows if r['arm']==arm];assert len(rs)==3
        c=dict(hits=sum(r['target_seconds'] is not None and r['audit_cost']<=SCENES['muell-gba146']['target'] for r in rs))
        for key in ['target_seconds','seconds','audit_cost','outers','rejects','matvecs']:
            vs=[r[key] for r in rs];c[key]=dict(median=statistics.median(vs),min=min(vs),max=max(vs))
        champion[arm]=c
    champion_change=champion['opening-2']['target_seconds']['median']/champion['baseline']['target_seconds']['median']-1
    if champion_change>.05:promote['opening-2']=False
    verdict=dict(winners_at_lambda_01=winners,speedups_at_lambda_01=ratios,screen_promote=screen_promote,
                 champion_check=champion,champion_opening_time_change=champion_change,promote=promote)
    (ROOT/'verdict.json').write_text(json.dumps(verdict,indent=2)+'\n')
    fig,axes=plt.subplots(1,3,figsize=(13,4.2))
    for ax,(scene,cs) in zip(axes,v['scenes'].items()):
        for i,arm in enumerate(arms):
            c=cs[arm];t=c.get('target_seconds',c['seconds']);m=t['median']
            ax.bar(i,m,color=colors[i],alpha=1 if c['hits']==3 else .4)
            ax.errorbar(i,m,yerr=[[m-t['min']],[t['max']-m]],fmt='none',color='#333',capsize=3)
            ax.text(i,t['max']*1.025,f'{m:.3f}'+(' MISS' if c['hits']<3 else ''),ha='center',fontsize=8)
        ax.set_xticks(range(len(arms)),labels,rotation=27,ha='right',fontsize=8)
        ax.set_title(scene);ax.set_ylabel('Target time; misses show budget time (s)')
        ax.set_ylim(0,max(c.get('target_seconds',c['seconds'])['max'] for c in cs.values())*1.2)
        ax.spines[['top','right']].set_visible(False)
    fig.suptitle('Extended damping pilot: N=3 medians and min–max, matched lambda 0.1')
    fig.tight_layout()
    repo=pathlib.Path('/workspace/prism-ba');figs=repo/'docs/figures/rl_damping';figs.mkdir(exist_ok=True)
    for ext in ['png','svg']:fig.savefig(figs/f'extended_time_to_target.{ext}',dpi=160)
    plt.close(fig)
    fig,ax=plt.subplots(figsize=(7.2,4))
    comparisons=[('Baseline\nλ₀=0.1',v['scenes']['muell-gba146']['baseline'],colors[0]),
                 ('Opening ×2\nλ₀=0.1',v['scenes']['muell-gba146']['opening-2'],colors[3]),
                 ('Baseline\nλ₀=10',champion['baseline'],colors[0]),
                 ('Opening ×2\nλ₀=10',champion['opening-2'],colors[3])]
    for i,(label,c,color) in enumerate(comparisons):
        t=c['target_seconds'];m=t['median'];ax.bar(i,m,color=color)
        ax.errorbar(i,m,yerr=[[m-t['min']],[t['max']-m]],fmt='none',color='#222',capsize=4)
        ax.text(i,t['max']+.08,f'{m:.3f}s',ha='center')
    ax.set_xticks(range(4),[x[0] for x in comparisons]);ax.set_ylabel('Native time to fixed target (s)')
    ax.set_title('Muell: opening decay helps at λ₀=0.1, hurts at λ₀=10\nN=3 per arm, median and min–max; all targets hit')
    ax.set_ylim(0,6);ax.spines[['top','right']].set_visible(False);fig.tight_layout()
    for ext in ['png','svg']:fig.savefig(figs/f'opening_initial_lambda.{ext}',dpi=160)
    plt.close(fig)
    lines=['# Extended learned-damping pilot','',
      '**Final decision: retain the incumbent.** Opening-2 passes the initial-lambda-0.1 screen, but regresses in the subsequent matched Muell check at the historical champion setting, initial lambda 10. The extended learned model fails family transfer and misses two targets. These results do not establish a new general winner.','',
      'The extended pilot adds deep-CG training checkpoints and twelve-outer returns, and compares learning against a fixed two-boundary opening decay. It is a rollout-trained linear controller, not a full on-policy RL experiment. All comparisons run on host 2237c6528e79 / RTX 2000 Ada, with identical solver flags and explicit initial lambda 0.1. Detailed policy logging is disabled in final timing; controller execution is included.','',
      '## Complete-solve results','',
      '| Scene | Arm | Hits | Native target seconds: median [min, max] | Ou ters | Rejects | Matvecs | Audited cost |',
      '|---|---|---:|---:|---:|---:|---:|---:|']
    for scene in SCENES:
        for arm in arms:
            c=v['scenes'][scene][arm];t=c.get('target_seconds',c['seconds'])
            label=('MISS; solve ' if c['hits']==0 else '')+f"{t['median']:.4f} [{t['min']:.4f}, {t['max']:.4f}]"
            lines.append(f"| {scene} | {arm} | {c['hits']}/3 | {label} | {c['outers']['median']:.0f} | {c['rejects']['median']:.0f} | {c['matvecs']['median']:.0f} | {c['audit_cost']['median']:.3f} |")
    lines+=['','| Scene | Current local winner | Time change vs matched baseline |','|---|---|---:|']
    for scene,arm in winners.items():
        cs=v['scenes'][scene];change=100*(cs[arm]['target_seconds']['median']/cs['baseline']['target_seconds']['median']-1)
        lines.append(f'| {scene} | {arm} | {change:+.1f}% |')
    lines+=['','![Repeated target times](figures/rl_damping/extended_time_to_target.png)','',
      'Targets were frozen at Trafalgar-126 = 105579.58394455544; Final-1936 = 5125687.352261469; Muell = 1946488.746262194. Native caps were 4, 8, and 12 seconds respectively. Small endpoint differences below the fixed threshold are not failures. These scenes have already been observed in research and are transfer diagnostics, not untouched test recordings.','',
      'The historical Muell champion at 4.220 s used initial lambda 10. The matched lambda-0.1 table does not supersede that external winner ledger, and contains no new Caspar measurements.','',
      '## Confirmatory check at the historical champion setting','',
      'After the initial panel, pre-register a six-run Muell check: same binary, target and 12-second cap, initial lambda 10, baseline versus opening-2, N=3 with alternating order. Neither controller is retuned. This directly tests the known starting-damping discrepancy instead of inferring an incumbent win from the lambda-0.1 panel.','',
      '| Arm, initial lambda 10 | Hits | Target seconds: median [min, max] | Outers | Rejects | Matvecs | Audited cost |',
      '|---|---:|---:|---:|---:|---:|---:|']
    for arm,c in champion.items():
        t=c['target_seconds'];lines.append(f"| {arm} | {c['hits']}/3 | {t['median']:.4f} [{t['min']:.4f}, {t['max']:.4f}] | {c['outers']['median']:.0f} | {c['rejects']['median']:.0f} | {c['matvecs']['median']:.0f} | {c['audit_cost']['median']:.3f} |")
    lines+=['',f"Opening-2 takes {100*champion_change:.1f}% more time at this setting. The work count increases from 927 to 1,180 matvecs and from 19 to 21 outers, with one reject instead of zero. The result is a convergence-speed regression despite all target hits. The fresh baseline median is {champion['baseline']['target_seconds']['median']:.3f} seconds; it also beats the 4.318-second opening-2 result at lambda 0.1. The panel improvement is therefore conditional on the starting configuration and does not replace the existing Muell champion.",'',
      '![Starting damping reverses the result](figures/rl_damping/opening_initial_lambda.png)','',
      '## Training and horizon evidence','',
      f"Twelve checkpoints, three actions, three repeats: 108 branches, up to twelve outers each. {a['deep_states']} decision states have previous CG depth >=64; maximum history depth is {a['max_history_depth']*128:.0f}/128, compared with 32/128 in the first pilot. {a['signals']}/12 states have a hindsight nonbaseline AUC improvement larger than the baseline repeat range. This is descriptive, not a significance test.",'',
      '| Scene / boundary | Prior CG | Common horizon s | Best action, 4-outer horizon | Best action, long horizon | Baseline AUC − best AUC |','|---|---:|---:|---:|---:|---:|']
    for c in a['cells']:
        auc=c['auc'];lines.append(f"| {c['scene']} / {c['k']} | {c['features'][7]*128:.0f} | {c['horizon']:.4f} | {c['short_best']:+d} | {c['best']:+d} | {auc['0']-auc[str(c['best'])]:.6g} |")
    lengths=[n for c in a['cells'] for n in c['continuation_outers']]
    lines+=['',f"Completed continuation lengths range {min(lengths)}–{max(lengths)} outers. The shared elapsed horizon is the shortest of each state's nine actual branch durations, so different states have different horizons. Four-outer comparisons above are rescored prefixes of these same trajectories, not extra GPU runs.",'',
      'Scouting selected four deep boundaries; the freshly captured Ladybug-598 boundary 18 had previous depth 1 rather than the scout’s 128. The actual saved features therefore contain three deep decision states, not four. All nine branches at each checkpoint restore identical feature histories, radius, numerical floor and baseline damping. The selection was not changed after observing branch outcomes.','',
      'Leave-one-whole-family-out normalized AUC advantages (positive is better): '+', '.join(f'{k} {val:+.7f}' for k,val in a['family_advantages'].items())+f"; mean {a['mean_advantage']:+.7f}.",'',
      'The objective is the integral of the causal, right-continuous accepted-cost curve divided by checkpoint cost and elapsed horizon. The current cost remains in the integral while the next step is being computed. Labels compare a single intervention followed by baseline continuation; deployment repeats interventions. Consequently, good branch labels do not guarantee good full-solve behavior. Late-state absolute normalized improvements can also be much smaller than opening improvements.','',
      'The fixed opening comparator multiplies the baseline next damping by 0.1 at boundaries 1 and 2, then yields to the unchanged guarded controller. The CG-cap rule cancels one decade of decay when previous CG depth reaches 128. All arms preserve the actual-objective acceptance, radius updates, numerical floor, and retry logic.','',
      '## Why the extended policy fails','',
      'A separate twelve-outer diagnostic on Final-1936 logs action +1 at every boundary 1–11. The baseline proposes lambda 0.025 each time; the policy changes it back to 0.25 each time. Thus repeated decisions cancel the intended LM damping decay. This trace is a mechanism diagnostic, not an additional timing repeat. In the N=3 timing experiment the controller spends 75 outers and about 8 seconds without reaching the target; baseline reaches it in four outers. Muell similarly uses a median 166 outers and 335 matvecs without hitting its target, versus baseline 16 outers and 1,065 matvecs with a hit.','',
      'For an unclipped damped step on a fixed quadratic, with positive damping metric D and error e relative to the minimizer, e_next = lambda (H + lambda D)^(-1) D e. In a D-scaled curvature eigendirection with eigenvalue mu, the error contraction factor is lambda/(mu + lambda). Holding damping high makes the linear system easier while retaining slow progress in weak-curvature directions. This local calculation explains the measured tradeoff; it is not a convergence proof for the nonlinear guarded implementation.','',
      'The teacher evaluates one correction followed by baseline continuation. Deployment repeatedly applies the approximate learned correction. The diagnostic exposes that mismatch directly: a transient action becomes persistent regularization. Three of twelve hindsight action choices also change between the short and long horizons. Rescoring the same states with four-outer returns gives a negative family-held-out mean advantage of -0.0137423, versus -0.0055200 with twelve-outer returns: the longer horizon reduces the offline loss but does not produce a useful policy.','',
      'The opening comparator avoids this measured failure by limiting its intervention to two boundaries. It reproduces the useful early work reduction without maintaining learned damping corrections during later convergence. Any further learning study should train/evaluate complete controller trajectories against time-to-target, include a baseline fallback, and beat this deterministic comparator. Merely adding more one-action AUC labels is not sufficient evidence for deployment.','',
      '## Verification and evidence','',
      '- Old derivative, new derivative off and opening=0 agree in work counts across N=3 and within numerical repeatability in cost. The opening schedule is verified from logged actions and effective damping ratios.',
      '- Host inference matches Python on all twelve final training feature vectors. Causal AUC, rejection-time accounting, and held-out-label isolation tests pass.',
      '- All 108 replay branches match the saved controller/history state exactly before intervention; see `branch-replay-audit.json`.',
      f"- {len(records)} audited endpoints; maximum relative independent FP64 audit discrepancy {max(r['audit_error'] for r in records):.3g}. Total native solve time {sum(r['seconds'] for r in records):.3f} seconds; process wall time {sum(r['wall_seconds'] for r in records):.1f} seconds, excluding compilation and Python audits.",
      '- Model SHA-256: `'+a['policy_sha256']+'`.',
      '- [Frozen protocol and pre-branch coverage amendment](rl_damping_extended_protocol.md). Source: `bench/rl_damping_extended.py`, `bench/report_rl_damping_extended.py`, `gpu/rl_damping.h`, existing isolated builder.',
      '- Raw runs/checkpoints/endpoints: `/tmp/prism-rl-damping-extended/`. Persistent compact evidence: `/workspace/prism-rl-damping-extended/`.',
      '', 'N=3 quantifies local repeat spread; three correlated research scenes cannot establish general superiority. Per-scene winners are descriptive and are not an automatically selected deployment policy.']
    report='\n'.join(lines).replace('Ou ters','Outers')+'\n'
    (ROOT/'RESULTS.md').write_text(report);(repo/'docs/rl_damping_extended_results.md').write_text(report)
    print(json.dumps(verdict,indent=2))

if __name__=='__main__':main()
