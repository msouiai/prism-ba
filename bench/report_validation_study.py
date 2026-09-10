#!/usr/bin/env python3
"""Live report for CPU-audited fixed-policy validation."""
import argparse,json,pathlib,statistics,math
from validation_study import read_rows,ARMS,SCENES,med

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,default=pathlib.Path('/workspace/prism-validation'));p.add_argument('--output',type=pathlib.Path,default=pathlib.Path('/workspace/prism-ba/docs/fixed_policy_validation.md'));a=p.parse_args();root=a.root
 development=read_rows(root/'ablation');budget_rows=read_rows(root/'budgets');rows=development+budget_rows;good=[r for r in rows if r['status']=='ok'];failed=[r for r in rows if r['status']!='ok']
 selection=json.loads((root/'selection.json').read_text()) if (root/'selection.json').exists() else None
 lines=['# Fixed-policy validation against Caspar FP32','',
 f"2026-09-07. Completed {len(rows)}/96 planned timed runs ({len(development)}/24 development, {len(budget_rows)}/72 budget/transfer), {len(failed)} failures. Cumulative native solver time: {sum(r.get('seconds',0) for r in rows)/60:.2f} minutes. Input parsing, state exports, CPU audits and separate smoke tests are additional.",'',
 'All settings and the selection rule were fixed in `/workspace/prism-validation/PROTOCOL.md` before the development runs. The broad queue remains paused. All GPU runs use the same lock; N=3 per cell, rotating order. Batching is off. SIMPLE_RADIAL, per-camera f/k1, k2=0, original BAL observations.','',
 '## Four-way development ablation','',
 '60 outer iterations per run on Ladybug-1197 and Dubrovnik-173. Costs below are independent CPU FP64 scores of exported final matrix states.','',
 '| Scene | Policy | N | Median seconds [range] | Median CPU cost [range] | Median retries | Median matvecs | Rearms across runs |',
 '|---|---|---:|---|---|---:|---:|---|']
 for scene in ['ladybug-1197','dubrovnik-173']:
  for arm in ARMS:
   rr=[r for r in development if r['scene']==scene and r['arm']==arm and r['status']=='ok']
   if not rr:continue
   lines.append(f"| {scene} | {arm} | {len(rr)} | {med(rr,'seconds'):.3f} [{min(r['seconds'] for r in rr):.3f}, {max(r['seconds'] for r in rr):.3f}] | {med(rr,'cost'):,.2f} [{min(r['cost'] for r in rr):,.2f}, {max(r['cost'] for r in rr):,.2f}] | {med(rr,'rejects'):g} | {med(rr,'matvecs'):g} | {', '.join(str(r['rearms']) for r in sorted(rr,key=lambda r:r['rep']))} |")
 lines+=['','Activation matters: in this 60-outer screen, none of the six combined runs rearms. Those runs therefore exercise the progressive policy without an active rearming intervention; their differences from progressive alone are not evidence of policy interference. Rearming alone activates on Ladybug but not Dubrovnik, so the Dubrovnik differences cannot be attributed to rearming.','','### Frozen selection','',
 'Eligibility: all runs pass their CPU audit and the median endpoint is within 3% of the best median on **both** development scenes. Rank by geometric mean of runtime normalized to existing multi-shift on each scene. Within 3% of the fastest geometric mean, prefer fewer enabled changes; progressive precedes rearm for equal complexity. This rule allows small quality regressions and selects one policy for all subsequent scenes.','']
 if selection:
  lines+=[f"Selected: **{selection['selected']}**, flags `{json.dumps(selection['flags'],sort_keys=True)}`. Selection saved before any new budget/transfer results.",'',
   '| Eligible policy | Normalized geometric-mean runtime |','|---|---:|']
  for arm,v in selection['normalized_geomean_runtime'].items():lines.append(f'| {arm} | {v:.4f} |')
 else:lines+=['Selection pending until all 24 development cells pass.']
 lines+=['','### Development time-to-quality','',
 'Reference: lowest median CPU endpoint among the four development arms per scene. Times are PRISM FP64 trace crossings with all untraced solve overhead charged before the crossing. Endpoints are independently audited; intermediate states are not each exported. `x/3 reached` retains runs that fail to cross under the outer cap.','',
 '| Scene | Policy | Within 1% (s) | Within 3% (s) | Within 5% (s) |','|---|---|---|---|']
 for scene in ['ladybug-1197','dubrovnik-173']:
  sr=[r for r in development if r['scene']==scene and r['status']=='ok']
  if len(sr)!=12:continue
  ref=min(med([r for r in sr if r['arm']==arm],'cost') for arm in ARMS)
  for arm in ARMS:
   rr=[r for r in sr if r['arm']==arm];cells=[]
   for band in [.01,.03,.05]:
    ts=[]
    for r in rr:
     offset=max(0,r['seconds']-float(r['trace'][-1]['wall_s']))
     hits=[float(t['wall_s'])+offset for t in r['trace'] if float(t['cost'])<=ref*(1+band)]
     ts.append(min(hits) if hits else None)
    cells.append(f'{statistics.median(ts):.3f}' if all(t is not None for t in ts) else f"{sum(t is not None for t in ts)}/3 reached")
   lines.append('| '+scene+' | '+arm+' | '+' | '.join(cells)+' |')
 lines+=['','## Fixed wall-budget comparison and transfer','',
 'Fresh runs of the selected fixed policy, guarded single shift and Caspar FP32 default parameters. The outer cap is raised to 100,000 so the time budget or existing convergence criterion controls stopping. Both solvers check the budget before committing an outer candidate and before starting the next attempt. A candidate completed after the deadline is discarded. Returned endpoints therefore receive no benefit from an unfinished over-budget iteration; actual process return can exceed the target by that attempt and cleanup. These are budget-eligible state comparisons, not hard real-time return guarantees.','',
 'Clocks are native solve clocks: file parsing, output and audits excluded. Caspar graph setup is separate, while PRISM solver allocations remain in its solve clock. This is not an equal end-to-end latency comparison. Existing convergence exits remain enabled.','',
 'Transfer uses final-3068 and final-4585 without retuning after selection. Both have appeared earlier in the investigation, so they are not globally unseen benchmarks.','',
 '| Scene | Budget (s) | Method | N | Median CPU cost [range] | Median actual solve (s) | Max overshoot (s) |',
 '|---|---:|---|---:|---|---:|---:|']
 for scene,bs in SCENES.items():
  for budget in bs:
   for arm in ['selected','single','caspar32']:
    rr=[r for r in budget_rows if r['scene']==scene and r['budget']==budget and r['arm']==arm and r['status']=='ok']
    if not rr:continue
    lines.append(f"| {scene} | {budget} | {arm} | {len(rr)} | {med(rr,'cost'):,.2f} [{min(r['cost'] for r in rr):,.2f}, {max(r['cost'] for r in rr):,.2f}] | {med(rr,'seconds'):.3f} | {max(r['overshoot_seconds'] for r in rr):.3f} |")
 if (a.output.parent/'fixed_policy_budget_comparison.png').exists():
  lines+=['','![CPU-checked budget comparison](fixed_policy_budget_comparison.png)','']
 lines+=['','### Equal-budget endpoint differences','',
 'Negative percentages favor the selected PRISM policy; these compare CPU-checked median costs at the same declared budget.','',
 '| Scene | Budget (s) | Selected vs Caspar | Selected vs guarded single |','|---|---:|---:|---:|']
 comparisons=[]
 for scene,bs in SCENES.items():
  for budget in bs:
   cells={arm:[r for r in budget_rows if r['scene']==scene and r['budget']==budget and r['arm']==arm and r['status']=='ok'] for arm in ['selected','single','caspar32']}
   if not all(len(v)==3 for v in cells.values()):continue
   cs={arm:med(rr,'cost') for arm,rr in cells.items()};vs_c=100*(cs['selected']/cs['caspar32']-1);vs_s=100*(cs['selected']/cs['single']-1)
   lines.append(f'| {scene} | {budget} | {vs_c:+.3f}% | {vs_s:+.3f}% |');comparisons.append(dict(scene=scene,budget=budget,vs_caspar_pct=vs_c,vs_single_pct=vs_s,costs=cs))
 if len(budget_rows)==72:
  lines+=['','### Interpretation','',
   'The selected fixed policy has lower median external cost than Caspar in seven of eight budget cells; the exception is Dubrovnik at 1s, where the difference is only about 0.04%. Guarded single shift is strongest in the short budgets on the small/medium cases. Multi-shift has a useful advantage on final-3068 at 8s and on the large case, but its 15s large advantage over guarded single is under 1%. These results do not support a universal multi-shift win.',
   '', 'The 1%, 3%, 5% bands expose variability: a median endpoint does not guarantee all three runs are within 1%. The range bars and the all-repeats criterion below retain that uncertainty. Rearming does not activate in the short transfer runs, so their gains are not evidence of its incremental benefit. The signed projection guard and FP32 sensitivity described below prevent a matched-algorithm superiority claim.']
 lines+=['','### CPU-checked time-to-quality bounds','',
 'For each scene, reference cost is the lowest median checked endpoint across methods and budgets in this fresh grid. Each cell is the earliest **tested budget** where all three repeats finish within the stated band. It is a discrete upper bound, not an exact first-crossing time. A dash means no tested budget qualifies. Native Caspar FP32 traces are retained for diagnosis but are not used to certify FP64 crossings.','',
 '| Scene | Method | Reference cost | Within 1% by (s) | Within 3% by (s) | Within 5% by (s) |','|---|---|---:|---|---|---|']
 quality=[]
 for scene,bs in SCENES.items():
  sr=[r for r in budget_rows if r['scene']==scene and r['status']=='ok']
  if len(sr)!=18:continue
  ref=min(med([r for r in sr if r['arm']==arm and r['budget']==b],'cost') for arm in ['selected','single','caspar32'] for b in bs)
  for arm in ['selected','single','caspar32']:
   times=[]
   for band in [.01,.03,.05]:
    hits=[b for b in bs if all(r['cost']<=ref*(1+band) for r in sr if r['arm']==arm and r['budget']==b)]
    times.append(min(hits) if hits else None)
   quality.append(dict(scene=scene,arm=arm,reference=ref,budgets=times));lines.append(f"| {scene} | {arm} | {ref:,.2f} | "+' | '.join(str(t) if t else '—' for t in times)+' |')
 prism=[r for r in good if r['arm']!='caspar32'];caspar=[r for r in good if r['arm']=='caspar32']
 lines+=['','## Audit and numerical limits','',
 f"PRISM endpoints audited: {len(prism)}. Maximum relative difference between exported-state CPU objective and reported GPU objective: {max((r.get('audit_relerr',0) for r in prism),default=0):.3g}. The CPU checker evaluates every original observation, including negative depths, using the saved rotation matrices/points/intrinsics; it does not consume GPU residuals. Export occurs outside the solve timer.",'',
 'Caspar endpoints use its independent CPU FP64 scorer against original double observations. Caspar state, arithmetic and pixel storage remain FP32; initial quantization is measured rather than silently calling the initial states identical. The generated Caspar projection also uses `z + copysign(1e-6, z)`, while the common audit and PRISM use plain `z`. Thus native objective differences near zero depth are not solely floating-point rounding. These are practical implementation comparisons under a common external metric, not matched-precision/matched-internal-objective ablations.','',
 '| Scene | Max initial quantization gap | Max native-vs-CPU final cost gap |','|---|---:|---:|']
 for scene in SCENES:
  rr=[r for r in caspar if r['scene']==scene]
  if rr:lines.append(f"| {scene} | {max(r['initial_quantization_relerr'] for r in rr):.3g} | {max(r['native_final_relerr'] for r in rr):.3g} |")
 epsilon_file=root/'epsilon-audit/results.json'
 if epsilon_file.exists():
  lines+=['','### Projection-guard diagnostic','',
   'The generated Caspar score kernel uses a signed 1e-6 depth guard. Two additional N=1 diagnostics rescore the same returned FP32 states on the CPU with and without that guard, always against original observations. They are separate from the 96 timed runs. Matching the guard reduces but does not eliminate the native/CPU discrepancy; the native path still evaluates in FP32 with different arithmetic/reduction order.','',
   '| Scene | CPU plain-z cost | CPU guarded-z cost | Native FP32 cost | Native/guarded gap |','|---|---:|---:|---:|---:|']
  for r in json.loads(epsilon_file.read_text()):
   lines.append(f"| {r['scene']} | {r['raw_final']:,.2f} | {r['guarded_final']:,.2f} | {r['native_final']:,.2f} | {100*r['native_vs_guarded_relerr']:.3f}% |")
  lines+=['','On Ladybug, the raw original initial cost is about 45.43M, while the returned FP32 initial state scores 178.87M under plain-z projection and 45.71M with the guard. This is a material numerical sensitivity, not an identical-start claim. The table above remains a common external objective comparison; matched precision and projection are needed before attributing its advantages solely to a novel algorithm. Source: the retained `caspar-score-kernel.cu` in the artifact directory; see the signed denominator operation before projection.']
 lines+=['','## Reproduction','',
 '* Protocol, frozen binaries, source snapshots, exact commands, exported states, logs and JSON: `/workspace/prism-validation`.',
 '* `bench/validation_study.py ablation --binary <frozen>`; `select`; then `budgets --binary <frozen> --caspar <frozen>`.',
 '* Independent checker: `bench/audit_prism_state.py <original BAL> <exported state> --reported <GPU cost>`.',
 '* `bench/report_validation_study.py` regenerates this report from retained results.',
 '* New opt-in hooks: PRISM `OCA_MAX_SECONDS` and `--state_out`; Caspar `CASPAR_MAX_SECONDS` in the build-local instrumented solver. Neither upstream checkout nor algorithm defaults are changed.',
 '* Results are local/uncommitted. The broad queue stays paused. This small N=3 investigation does not prove universal superiority, establish novelty by itself, or supply a publication verdict.','']
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text('\n'.join(lines))
 result=dict(completed=len(rows),failures=len(failed),solver_seconds=sum(r.get('seconds',0) for r in rows),selection=selection,comparisons=comparisons,quality=quality,max_prism_audit_error=max((r.get('audit_relerr',0) for r in prism),default=0))
 (root/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['completed','failures','solver_seconds','max_prism_audit_error']}))
if __name__=='__main__':main()
