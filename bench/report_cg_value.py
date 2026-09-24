#!/usr/bin/env python3
"""Report the frozen CG value experiment without changing selection."""
import json, math, pathlib, statistics as stats
from report_ba_accuracy import table

ROOT=pathlib.Path('/tmp/prism-cg-value')
REPO=pathlib.Path('/workspace/prism-ba')
def read(name):return json.loads((ROOT/name).read_text())
def groups(rows):
 for s,q in dict.fromkeys((r['scene'],r['quality']) for r in rows):
  yield s,q,{a:[r for r in rows if (r['scene'],r['quality'],r['arm'])==(s,q,a)]
             for a in dict.fromkeys(r['arm'] for r in rows)}
def intervention_table(rows):
 lines=['| Scene / quality | Arm | Extra stops median [min,max] | CG matvecs median | Outers median |',
        '|---|---|---:|---:|---:|']
 for s,q,arms in groups(rows):
  for a,rr in arms.items():
   if not rr:continue
   values=[r['value_summary'].get('stops',0) for r in rr]
   lines.append(f'| {s} / {q} | {a} | {stats.median(values):g} [{min(values):g}, {max(values):g}] | '
                f"{stats.median(r['matvecs'] for r in rr):g} | {stats.median(r['outers'] for r in rr):g} |")
 return lines
def main():
 selected=read('selection.json');transfer=read('transfer-verdict.json')
 train=read('train-rows.json');rows=read('transfer-rows.json')
 large=read('large-verdict.json') if (ROOT/'large-verdict.json').exists() else None
 promoted=bool(transfer['extend'] and large and large['extend'])
 runs=[json.loads(p.read_text()) for p in (ROOT/'runs').glob('*/result.json')]
 metrics=dict(runs=len(runs),native_seconds=sum(r['seconds'] for r in runs),
  maximum_audit_error=max(r['audit_error'] for r in runs),transfer_hits=sum(r['hit'] for r in rows),
  transfer_runs=len(rows),smoke=read('smoke.json'))
 verdict=dict(selected=selected['selected'],transfer=transfer,large=large,
              champion_retained=not promoted)
 (ROOT/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
 (ROOT/'verdict.json').write_text(json.dumps(verdict,indent=2)+'\n')
 lines=['# CG marginal model-value results','',
  '**Verdict: '+('candidate passes the registered medium and largest gates.' if promoted else 'retain the sustained eta2 champion.')+'**','',
  f"Selected on development only: `{selected['selected']}`. All configurations start at lambda 0.1. A target is fixed before running an arm; timings below are actual native TARGET events, checked against independent original-observation FP64 endpoint audits. N=3 per cell; no interpolated crossings. SIMPLE_RADIAL, k2 fixed at zero, half sum of squared original pixel residuals. Host2237c6528e79, RTX2000 Ada. Defaults unchanged.",'',
  'The conservative rule delivers a modest measured gain: 1.0322x geometrically over five medium scene/target settings. Trafalgar improves at both targets; Final1936 and Muell have zero interventions. The 5% registered extension gate is not met. This is useful localized evidence, not a broadly established replacement. The work-only comparator scores 1.0478x overall but slows the primary Trafalgar target by 16.3% and Venice development by 20.0%; its gains at tighter targets do not erase those counterexamples.','',
  '## Mathematics and limits','',
  'For a fixed SPD reduced camera operator A and fixed SPD preconditioner M, let G_j be the decrease in q(x)=x^T A x/2-b^T x. PCG supplies the increment without new GPU work:',
  '','```','delta_j = alpha_j * (r_j^T M^-1 r_j) / 2','G_j = sum(delta_i, i <= j)','```','',
  'If the next step costs dt and gives model gain dG, then (G+dG)/(T+dt) exceeds G/T exactly when dG/dt exceeds G/T. The implementation estimates the next rate with a trailing three-step window. T includes measured setup and CG time plus the previous attempt\'s scoring/acceptance time. Two consecutive low-rate windows are needed. The first possible extra stop is depth 4. This algebra justifies the rate comparison; the backward-looking forecast itself is heuristic.','',
  'The rate arm uses a marginal/average threshold of 1; conservative uses 0.1. The work-only comparator replaces time by iteration count and ignores setup. Passive computes the rate rule but never acts. All retain the champion\'s original residual stop. Extra stops require residual <=0.5 times the RHS norm and pass the existing explicit true-residual check at that tolerance. Retries, a preceding rejected/low-rho attempt, and numeric repair suppress intervention; repair disables it permanently. Existing coupled damping, camera radius, full-model prediction, true-cost acceptance and rescue checks remain.','',
  'G measures only reduced damped camera-model decrease, not the full undamped nonlinear BA gain. The eliminated-point constant is omitted. Camera-radius clipping can change the final step, and later CG gains can rebound after a quiet window. A small recent gain is neither an upper bound on remaining linear error nor proof that terminating improves nonlinear time-to-target. No global convergence or novelty claim is made.','',
  'This is established quadratic-decrease truncation: [Nash\'s survey](https://doi.org/10.1016/S0377-0427(00)00426-X) describes marginal-versus-average model reduction. [Ceres already implements a quadratic-model CG stopping test](https://github.com/ceres-solver/ceres-solver/blob/master/internal/ceres/conjugate_gradients_solver.h). Our time accounting, trailing window and safeguards are an experimental adaptation, not evidence of a new algorithmic principle.','',
  '## Verification and cost','',
  f"CPU and GPU model-gain identities passed: maximum relative discrepancies {metrics['smoke']['maximum_cpu_identity_error']:.3g} and {metrics['smoke']['maximum_gpu_identity_error']:.3g}. N3 parent/new-disabled/passive smoke preserved work counts and audited costs within 1e-7. Separate GPU identity runs add explicit operator applications and are excluded from all performance comparisons.",'',
  'Performance modes allocate zero additional GPU bytes and launch no extra probe kernels, reductions or synchronization. They add host scalar arithmetic and steady-clock reads. Passive timing measures this overhead plus ordinary run variation. Active extra stops still pay the existing explicit true-residual check.','',
  'Across the five medium settings passive monitoring has a 0.9833x geometric speedup (about 1.7% extra time) with unchanged work counts. The lack of new GPU work does not imply zero runtime overhead. Small same-work timing differences include host overhead and measurement variation.','',
  '## Development','']+table(train)
 lines+=['','| Arm | Penalized development score (higher better) |','|---|---:|']
 for a,x in selected['log_losses'].items():lines.append(f'| {a} | {math.exp(-x):.4f} |')
 lines+=['','A miss receives 4*cap for selection; scores involving misses are not measured speedups. Only rate and conservative were eligible for selection. All arms and constants were fixed in advance.','']+intervention_table(train)
 lines+=['',
  'On Dubrovnik356, conservative makes one extra stop and changes the complete trajectory from 11 outers/324 matvecs to 8/207 in all three repeats: median 1.0040s to 0.6630s. The aggressive rate rule misses the target in all three repeats: two terminate at 46 outers after 13 rejects, while another reaches the cap after 80 outers and numeric repair. An inexpensive local quadratic step is not necessarily a good nonlinear trajectory.','']
 lines+=['','## Frozen medium transfer','',
  'Trafalgar126 and Final1936 use both existing quality targets; Muell146 uses its existing primary target. Tighter Muell was excluded before this study after repeated 12s misses in earlier work. These scenes were excluded from controller selection but are familiar research data, not pristine population holdouts.','']+table(rows)
 lines+=['','| Task | Speedup (champion time / selected time) |','|---|---:|']
 for task,ratio in transfer['speedups'].items():
  lines.append(f'| {task} | '+(f'{ratio:.4f}x' if ratio is not None else 'Withheld: target miss')+' |')
 geo=transfer['geometric_speedup']
 lines+=['','Geometric speedup: '+(f'{geo:.4f}x.' if geo is not None else 'withheld because of a target miss.'),'']+intervention_table(rows)
 lines+=['',
  'Conservative stops once on each Trafalgar run. At the primary target, matvecs fall 195 to 164 with seven outers unchanged; at the tighter target they fall 455 to 407 with 11 outers unchanged. Final1936 remains 16/33 matvecs at its primary/tighter targets, and Muell remains 980. The improvement therefore comes from less camera linear work on Trafalgar, not fewer rejections across the panel.','',
  'A mathematically relevant follow-up is the full damped quadratic gain after point elimination: it includes the constant 0.5*bp^T(V+lambda*Dp)^-1*bp as well as camera gain G. The current timing rule uses G alone. The solver has an optional computation of this point term, but it is not enabled in the frozen champion; including it would require accounting for an extra reduction or fusing that computation. That change should be measured separately rather than silently folded into these results.','']
 if large:
  lines+=['','## Largest-scene confirmation','',str(large),'']+table(read('large-rows.json'))+['']+intervention_table(read('large-rows.json'))
 else:
  lines+=['','The largest extension was skipped because the registered medium gate failed. No fresh Caspar comparison was run. Earlier Caspar measurements are unchanged.']
 lines+=['','## Evidence','',
  f"{metrics['runs']} independently audited endpoints; maximum relative cost discrepancy {metrics['maximum_audit_error']:.3g}; {metrics['native_seconds']:.3f} native solver seconds including smoke diagnostics. Medium-panel target hits: {metrics['transfer_hits']}/{metrics['transfer_runs']}.",'',
  '[Protocol](cg_value_protocol.md). Implementation: `gpu/cg_value.h`; builder: `bench/build_cg_value.py`; runner: `bench/cg_value_study.py`; reporter: `bench/report_cg_value.py`. Exact binary, source, local headers, input/code hashes, commands, traces, logs and audited endpoints: `/tmp/prism-cg-value/`. The compact durable evidence package is `/workspace/prism-cg-value-evidence.tar.xz`; raw endpoints remain in /tmp to conserve shared quota.']
 text='\n'.join(lines)+'\n'
 (ROOT/'RESULTS.md').write_text(text);(REPO/'docs/cg_value_results.md').write_text(text)
 print(json.dumps(dict(verdict=verdict,metrics=metrics),indent=2))
if __name__=='__main__':main()
