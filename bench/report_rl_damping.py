#!/usr/bin/env python3
"""Publish immutable pilot evidence and small repeated time-to-target figure."""
import json, pathlib, statistics, hashlib, shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from rl_damping_pilot import ROOT,sha

REPO=pathlib.Path('/workspace/prism-ba')

def main():
    a=json.loads((ROOT/'analysis.json').read_text());v=json.loads((ROOT/'validation-summary.json').read_text())
    records=[json.loads(p.read_text()) for p in (ROOT/'runs').glob('*/result.json')]
    valid=[r for r in records if 'audit_error' in r]
    scenes=['trafalgar-126','final-1936','muell-gba146'];arms=['baseline','learned','work-rule']
    labels=['Guarded Prism','Learned damping','CG-cap rule'];colors=['#65758b','#287ca8','#d99734']
    fig,axes=plt.subplots(1,3,figsize=(11,3.8))
    for ax,scene in zip(axes,scenes):
        cells=v['scenes'][scene]
        for i,arm in enumerate(arms):
            t=cells[arm]['target_seconds'];med=t['median'];ax.bar(i,med,color=colors[i],width=.65)
            ax.errorbar(i,med,yerr=[[med-t['min']],[t['max']-med]],color='#222',capsize=4,fmt='none')
            ax.text(i,t['max']*1.035,f'{med:.3f}s',ha='center',fontsize=9)
        ax.set_xticks(range(3),labels,rotation=15,ha='right',fontsize=8)
        ax.set_title(scene);ax.set_ylabel('Native time to fixed target (s)');ax.set_ylim(0,max(cells[x]['target_seconds']['max'] for x in arms)*1.2)
        ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    fig.suptitle('Damping-control pilot: N=3 medians and min–max; every arm hit 3/3',fontsize=12)
    fig.tight_layout()
    figures=REPO/'docs/figures/rl_damping';figures.mkdir(parents=True,exist_ok=True)
    for ext in ['png','svg']:fig.savefig(figures/f'time_to_target.{ext}',dpi=160)
    plt.close(fig)
    lines=['# RL damping pilot results — 2026-09-09','',
      '**Verdict: retain the guarded Prism incumbent.** The frozen rollout-trained damping controller improves two BAL transfer checks but regresses on the production scan. All target hits and endpoint audits pass; the learned policy fails the predeclared 10% panel promotion threshold. No fresh Caspar extension was triggered.','',
      'This is a completed rollout-guided policy-improvement pilot, not a completed SAC/PPO training study. A small regularized value model was fitted to branched multi-step returns, then deployed to make repeated decisions. No claim that RL is necessary, novel, or generally faster follows from this result.','',
      '## Complete-solve comparison','',
      'Same binary, flags, original data and explicitly `--lam0 0.1`; N=3 rotated serial runs on host 2237c6528e79 / RTX 2000 Ada. Targets are fixed historical useful-quality thresholds; model fitting uses none of these three scenes. They have been used in earlier research and are not pristine unseen recordings. Feature extraction and policy inference are included in native timing; detailed policy logging is disabled.','',
      '| Scene | Arm | Hits | Target time, median [min, max] s | Accepted outers, median | Rejects, median | Matvecs, median | Audited final cost, median |',
      '|---|---|---:|---:|---:|---:|---:|---:|']
    for scene in scenes:
        for arm in arms:
            c=v['scenes'][scene][arm];t=c['target_seconds']
            lines.append(f"| {scene} | {arm} | {c['hits']}/3 | {t['median']:.3f} [{t['min']:.3f}, {t['max']:.3f}] | {c['outers']['median']:.0f} | {c['rejects']['median']:.0f} | {c['matvecs']['median']:.0f} | {c['audit_cost']['median']:.3f} |")
    lines+=['','| Scene | Learned time change versus baseline | Work-rule time change |','|---|---:|---:|']
    for scene in scenes:
        c=v['scenes'][scene];b=c['baseline']['target_seconds']['median']
        lines.append(f"| {scene} | {100*(c['learned']['target_seconds']['median']/b-1):+.1f}% | {100*(c['work-rule']['target_seconds']['median']/b-1):+.1f}% |")
    lines+=['',
      'The learned policy is 1.082x faster on Trafalgar and 1.135x faster on Final-1936, but takes 1.188x as long on Muell. On the latter, it increases matvecs from 1,065 to 1,353 and accepted outers from 16 to 17. Its median scene speedup is 1.082x, below the frozen 1.10x threshold. All nine learned runs meet their target, so this is a speed/transfer failure rather than a quality failure. Small final-cost differences within the registered tolerance are not counted as regressions.','',
      'The simple work rule cancels one decade of the nominal lambda decrease when the previous CG solve reaches its depth cap. It reduces Muell matvecs to 1,016 and target time by 4.9%, while leaving the work counts on the other two scenes unchanged. That is a useful deterministic reference, but it also misses the panel promotion threshold.','',
      'The previous 4.220 s Muell champion result used initial lambda 10. The current table is an internally matched comparison at lambda 0.1 and does not replace that older configuration in the external winner ledger.','',
      '![Repeated target times](figures/rl_damping/time_to_target.png)','',
      '## What was learned','',
      'After each accepted step, the controller chooses a factor 0.1, 1, or 10 relative to the baseline next lambda, clipped to the existing numerical floor and ceiling. Camera and point damping remain coupled. Radius updates, true-objective acceptance, retry escalation, linear tolerances, precision and stopping rules remain the baseline implementation. Action zero leaves damping arithmetic untouched.','',
      'The model uses 16 scalar features over four outer steps (64 inputs): damping/floor, model agreement, relative progress, camera-step/radius ratio, RHS norm, forcing tolerance, CG depth fraction, rejection/repair counts, normalized cost and scene size, acceptance and action history. A regularized linear action-value model needs only a few kilobytes and no new GPU kernels. The first intervention occurs after the first accepted step.','',
      'Training data: 24 complete checkpoints, eight each from Ladybug-49, Dubrovnik-88 and Venice-52. Three actions x three repeats x four-outer continuations gives 216 branched rollouts. Each comparison uses a shared elapsed-time horizon and the integral of the right-continuous accepted-cost curve, normalized by initial checkpoint cost and duration. A future accepted cost is never credited before its solve time. This development reward captures short-horizon progress; it is not identical to final time-to-target reward.','',
      '| Training family | Checkpoints with non-baseline advantage beyond baseline repeat spread | Hindsight best actions (-1 / 0 / +1) |','|---|---:|---:|']
    for scene in ['ladybug-49','dubrovnik-88','venice-52']:
        cells=[x for x in a['cells'] if x['scene']==scene]
        counts=[sum(x['best']==i for x in cells) for i in [-1,0,1]]
        lines.append(f"| {scene} | {sum(x['signal'] for x in cells)}/8 | {' / '.join(map(str,counts))} |")
    lines+=['',
      'Thirteen of 24 checkpoints clear that development signal gate. These are correlated states and the comparison is selected in hindsight; the count is not a statistical significance claim. Leaving one whole family out gives normalized AUC improvements of +0.008690 on Ladybug, +0.019053 on Dubrovnik, and -0.019179 on Venice (positive is better). Mean +0.002855 beats the train-selected constant action (-0.006393) and the simple cap rule (0), satisfying the provisional gate for the frozen final test. The Venice reversal was disclosed before testing.','',
      '## Why transfer failed on Muell','',
      'The largest previous CG depth in any training observation/history is **32 of 128** (normalized fraction 0.25). Muell later operates repeatedly at 128. Thus the initial small-scene dataset did not cover the expensive-linear-solve regime motivating this research. The simple cap rule is inactive at every training decision for the same reason. This is a measured coverage gap, not proof that it is the sole cause of the regression.','',
      'The frozen policy initially lowers damping on all three transfer scenes. Muell subsequently receives repeated upward corrections and still accumulates more Krylov work. A four-outer rollout return does not directly teach the consequences of repeated interventions throughout a long polishing phase. Geometry/controller distribution shift and the development reward horizon both need investigation.','',
      'The next bounded training experiment should include true late checkpoints with deep CG from training-only medium problems, compare longer/budgeted continuation returns, and evaluate a policy that can abstain outside its training support. Any abstention rule must be frozen on development data and validated afresh. Muell has now served as a failure diagnostic and cannot be relabelled an untouched test. Also compare a simple faster opening-decay schedule to establish whether learning contributes beyond selecting two or three early reductions.','',
      '## Implementation and verification','',
      '- Added an isolated builder and `gpu/rl_damping.h`; production solver defaults were not changed. Legacy menu-learning hooks are not used by this single-shift controller.',
      '- Extended accepted-boundary replay for the champion: geometry, radius, LM state, persistent numerical floor/rebuild count, stopping/history state, PCG counters and policy history. Derived assembly is rebuilt; cache reuse modes outside the verified scope are rejected.',
      '- Original binary, derivative off, and action-zero checks use three repeats each. All require 112 matvecs; endpoint differences stay within ordinary numerical repeatability.',
      '- Three restored continuations agree with the continuous trajectory in cost, lambda, rho, model prediction, CG work, rejects and repairs within the declared tolerance. A separate repaired Ladybug-1723 checkpoint restores floor, radius, lambda and all history features exactly. An incompatible checkpoint configuration is rejected.',
      '- Nonzero-action smoke tests verify actual decade changes. Exported C++ inference agrees with Python for all 24 observed feature vectors.',
      '- Three host tests check causal reward integration, rejection-time accounting, and independence of held-out predictions from held-out labels.',
      f'- {len(valid)} independently audited solver endpoints; maximum relative solver/audit disagreement {max(x["audit_error"] for x in valid):.3g}. One additional deliberate configuration-mismatch run fails as expected.',
      f'- Total native solver time across the pilot and verification: {sum(x["seconds"] for x in valid):.3f} s, within the 600 s ceiling. Summed subprocess wall time: {sum(x["wall_seconds"] for x in records):.1f} s; compilation and Python-side input parsing/audits are additional.',
      '',
      '## Artifacts','',
      '- [Research and prior art](rl_damping_research.md), [frozen pilot protocol](rl_damping_pilot_protocol.md).',
      '- Code: `bench/build_rl_damping.py`, `gpu/rl_damping.h`, `bench/rl_damping_pilot.py`, `bench/validate_rl_damping.py`, `bench/test_rl_damping_pilot.py`, `bench/report_rl_damping.py`.',
      '- Full local working evidence: `/tmp/prism-rl-damping/`, including checkpoints and all exported endpoint states. Persistent compact evidence package: `/workspace/prism-rl-damping/`.',
      '- Frozen policy SHA-256: `'+sha(ROOT/'policy.txt')+'`. Binary/source/header hashes and exact commands are in the build and run manifests.',
      '',
      'The published conclusion is a mixed, reproducible pilot result. Guarded Prism remains the general incumbent; no new RL-versus-Caspar speed claim is made.']
    report='\n'.join(lines)+'\n'
    (REPO/'docs/rl_damping_results.md').write_text(report)
    (ROOT/'RESULTS.md').write_text(report)
    index={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'runs').glob('*/endpoint.state')}
    (ROOT/'endpoint_state_sha256.json').write_text(json.dumps(index,indent=2)+'\n')
    print(REPO/'docs/rl_damping_results.md')

if __name__=='__main__':main()
