#!/usr/bin/env python3
import json,math,pathlib,statistics
from report_ba_accuracy import table
ROOT=pathlib.Path('/tmp/prism-reference-forcing');REPO=pathlib.Path('/workspace/prism-ba')
def read(n):return json.loads((ROOT/n).read_text())
def main():
 sel=read('selection.json');v=read('transfer-verdict.json');large=(ROOT/'large-verdict.json').exists()
 tr=read('train-rows.json');stress=read('stress-rows.json');transfer=read('transfer-rows.json')
 runs=[json.loads(p.read_text()) for p in (ROOT/'runs').glob('*/result.json')]
 metrics=dict(runs=len(runs),native_seconds=sum(r['seconds'] for r in runs),maximum_audit_error=max(r['audit_error'] for r in runs),
  transfer_hits=sum(r['hit'] for r in transfer),transfer_runs=len(transfer),smoke=read('smoke.json'))
 diagnostic=[r for r in runs if r['name'].startswith('diagnostic-')]
 metrics.update(diagnostic_runs=len(diagnostic),diagnostic_native_seconds=sum(r['seconds'] for r in diagnostic))
 (ROOT/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
 lv=read('large-verdict.json') if large else None
 promoted=v['extend'] and large and lv['extend']
 verdict=dict(selected=sel['selected'],transfer=v,large=lv,champion_retained=not promoted,
  status='candidate passes the registered medium and largest gates' if promoted else 'current sustained eta2 champion retained')
 (ROOT/'verdict.json').write_text(json.dumps(verdict,indent=2)+'\n')
 lines=['# Fixed-reference reduced-gradient forcing','', '**Verdict: '+verdict['status']+'.**','',
  'Selected rule: `'+sel['selected']+'`. The selection used only lambda 0.1 development tasks; high-damping stress outcomes were excluded.','',
  '## What was implemented','',
  'The forcing ratio compares reduced gradients at two geometries while holding the reference damping and camera metric fixed:',
  '','```','b(x,lambda) = bc(x) - W(x) [V(x)+lambda Dp(x)]^-1 bp(x)',
  'q = ||E_old b(x_new,lambda_old)|| / ||E_old b(x_old,lambda_old)||',
  'eta = clip(1.8 q^2, 1e-12, 0.5)','```','',
  'The stored denominator, damping and E come from the accepted attempt before its geometry update. The next numerator uses the new geometry with that old damping/E. Geometry-dependent point diagonals retain the solver trace-based floor. The safeguarded candidate additionally applies the EW-style previous-eta floor. History advances only on acceptance and forcing is held through retries; numeric repair permanently switches control back to the champion formula on the current trajectory.','',
  'The point factor and reduced RHS are recomputed at reference damping, then the actual point factors are restored. Existing Rf,uu,corr,w and cached R0f are reused. The only added GPU buffer is E_old: 72*ncam bytes (985104 bytes on Final13682). No new observation-sized or point-factor buffer is allocated. Native timing includes the extra kernels, synchronization and anchor copies. CG matvec counts omit this additional work; probe timing is reported separately.','',
  '## Verification','',
  f"N3 parent/new champion/passive/current-RHS-verification smoke tests preserve work counts and endpoint costs within 1e-7. Maximum GPU reconstructed/current RHS norm discrepancy: {metrics['smoke']['maximum_gpu_identity_error']:.3g}.",'',
  'The CPU example changes the ordinary reduced norm ratio to 1.075642 solely by changing damping at fixed geometry; the reference ratio stays 1. With the prescribed geometry change, it becomes 1.1. CPU tests also check accepted-only anchors, metric consistency, retry idempotence and repair fallback. These verify the measurement, not a convergence theorem.','',
  '## Development at the deployment initialization','',
  'N3 on Ladybug598, Dubrovnik356 and Venice89, lambda 0.1, unchanged fixed targets. Champion=sustained eta2; probe=extra reference work with champion decisions; reduced-ew2=the preceding safeguarded reduced-RHS control; reference/reference-safe=new candidates.','']+table(tr)
 lines+=['','| Arm | Penalized development score (higher is better) |','|---|---:|']
 for a,x in sel['log_losses'].items():lines.append(f'| {a} | {math.exp(-x):.4f} |')
 lines+=['','A missed run receives 4*cap during selection. Penalty-derived scores are not measured speedups when misses occur. Both candidate definitions were frozen before measurement; selection chooses one without fitting parameters.','',
  '## Separate high-damping stress test','',
  'Dubrovnik356 lambda 10; these results do not enter selection.','']+table(stress)
 lines+=['',
  'The unchanged champion itself is variable at lambda 10: 1/3 target hits, versus 2/3 for passive probing and 3/3 for reference-safe. A hit-only median must not be called an aggregate speedup here. Comparing champion/probe repeat0, cost differences start at roughly machine precision and grow: about 6e-9 relative by outer 11 and 1.4e-6 by outer 15. The early damping sequence agrees. This is consistent with roundoff-sensitive trajectories; these few runs do not establish a robust stress speedup. No numeric repair disabled the passive controller.','']
 if (ROOT/'restoration-verification.json').exists():
  d=read('restoration-verification.json');assert d['passed'] and len(d['runs'])==3
  lines += [f"A separate post-study diagnostic checked Rf, factor-status flags, the actual reduced RHS and camera metric byte-for-byte before/after every probe: {sum(r['checks'] for r in d['runs'])} checks across N3 stress runs passed. Current-RHS norm reconstruction also passed. These instrumented runs use a separate binary, include host snapshots, and are excluded from all selection and speed comparisons. This rules out corruption of those restored/preserved arrays on the checked trajectories, not every possible numerical interaction.",'']
 lines+=['## Frozen transfer','',
  'Initial lambda 0.1, N3 per cell. Both prior targets on Trafalgar126 and Final1936; prior primary target on Muell146. The tighter Muell target was excluded prospectively because every preceding arm missed it in all 12s repeats. It is not counted as a success here. These scenes were excluded from this controller selection but are familiar research data, not pristine population holdouts.','']+table(transfer)
 lines+=['','| Task | Speedup (champion time / selected time) |','|---|---:|']
 for task,value in v['speedups'].items():lines.append(f'| {task} | '+(f'{value:.4f}x' if value is not None else 'No ratio: target miss')+' |')
 lines+=['','Geometric speedup: '+(f"{v['geometric_speedup']:.4f}x." if v['geometric_speedup'] is not None else 'withheld because of a target miss.'),
  '', '## Passive probe overhead','',
  '| Scene / quality | Champion median seconds | Probe median seconds | Probe/champion | Reference probes | Probe kernel/restoration seconds |',
  '|---|---:|---:|---:|---:|---:|']
 for s,q in dict.fromkeys((r['scene'],r['quality']) for r in transfer):
  cs={a:[r for r in transfer if r['scene']==s and r['quality']==q and r['arm']==a] for a in ['champion','probe']}
  ok=all(r['hit'] for rr in cs.values() for r in rr)
  if ok:
   b=statistics.median(r['target_seconds'] for r in cs['champion']);pr=statistics.median(r['target_seconds'] for r in cs['probe'])
   count=statistics.median(r['reference_summary'].get('queries',0) for r in cs['probe']);tm=statistics.median(r['reference_summary'].get('probe_seconds',0) for r in cs['probe'])
   lines.append(f'| {s} / {q} | {b:.4f} | {pr:.4f} | {pr/b:.4f} | {count:g} | {tm:.4f} |')
  else:lines.append(f'| {s} / {q} | — | — | Target miss | — | — |')
 lines+=['','Probe timers include reference kernels, factor restoration and synchronization, but omit the separately charged anchor copies. Passive total-time differences also contain timing and GPU summation variation; they are not exact isolated kernel costs.','']
 if large:lines+=['## Largest-scene transfer','',json.dumps(lv),'']+table(read('large-rows.json'))
 else:lines+=['The largest extension was skipped because the registered transfer gate failed. No fresh Caspar runs or new Caspar speedup claims are made.']
 lines+=['','## Interpretation and reproducibility','',
  'The selected controller is 8.4% slower geometrically over the five transfer settings. All 60 transfer runs hit their registered targets. The sole selected-rule win is tighter Trafalgar: 11 to 10 outers and 455 to 381 CG matvecs, giving 1.143x speedup. On Final1936 the outer counts are unchanged, but matvecs rise 16 to 20 at the primary target and 33 to 48 at the tighter target. Its passive probe alone costs roughly 10-12% in total time; the active controller adds still more linear work. Muell stays at 16 outers with 980 to 989 matvecs and about 4% more time. These observations separate measurement overhead from worse forcing decisions.','',
  'Do not optimize the probe alone and assume the controller will win: Final1936 remains slower than passive probing, and Venice development needs 30 rather than 25 outers despite fewer CG matvecs. A useful next hypothesis is to estimate the marginal value of another linear iteration from quantities already produced by CG and model acceptance. Any such rule needs a separately registered comparison against the same champion and fixed targets.','',
  'Holding damping/E fixed removes their direct change from the history ratio. It does not prove that the resulting ratio predicts the value of another CG iteration or the best nonlinear trajectory. Changed forcing can alter later outer counts. Any improvement must exceed its own reference-measurement cost and must be assessed at each quality target.','',
  'This is an experimental adaptation of inexact-solve forcing. [Adaptive forcing is established prior art](https://users.wpi.edu/~walker/Papers/forcing_terms%2CSISC_17%2C1996%2C16-32.pdf); implementation and timing evidence alone do not establish novelty. No global convergence claim is made for guarded, clipped, mixed-precision BA.','',
  f"{metrics['runs']} original-observation FP64 endpoint audits, including {metrics['diagnostic_runs']} post-study diagnostics; maximum relative discrepancy {metrics['maximum_audit_error']:.3g}; {metrics['native_seconds']:.3f} native solver seconds (diagnostics account for {metrics['diagnostic_native_seconds']:.3f}s). Transfer hits {metrics['transfer_hits']}/{metrics['transfer_runs']}. Same RTX2000 Ada host2237c6528e79. SIMPLE_RADIAL,k2fixed0, half-sum squared original pixel residuals. A hit requires an actual TARGET event within cap and an audited endpoint <=target. No interpolation; loading/export/audit excluded.",'',
  '[Registered protocol](reference_forcing_protocol.md). Source: `gpu/reference_forcing.h`, `bench/build_reference_forcing.py`, `bench/reference_forcing_study.py`, `bench/report_reference_forcing.py`, `bench/verify_reference_restoration.py`. Frozen binaries, headers, code hashes, logs, traces and endpoints: `/tmp/prism-reference-forcing/`. Durable compact source/binary/trace package: `/workspace/prism-reference-forcing-evidence.tar.xz` (raw endpoints remain under /tmp). Production defaults unchanged.']
 text='\n'.join(lines)+'\n';(ROOT/'RESULTS.md').write_text(text);(REPO/'docs/reference_forcing_results.md').write_text(text)
 print(json.dumps(dict(verdict=verdict,metrics=metrics),indent=2))
if __name__=='__main__':main()
