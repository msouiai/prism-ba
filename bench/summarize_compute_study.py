#!/usr/bin/env python3
"""Summarize the bounded progressive-depth, batching and replay studies."""
import argparse,json,pathlib,re,statistics

def median(rows,key):return statistics.median(r[key] for r in rows)
def load(root):
 rows=[]
 for p in root.glob('*.json'):
  r=json.loads(p.read_text())
  if isinstance(r,dict) and 'scene' in r and 'status' in r:rows.append(r)
 return rows

def main():
 p=argparse.ArgumentParser();p.add_argument('--workspace',type=pathlib.Path,default=pathlib.Path('/workspace'));p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();w=a.workspace
 groups={key:load(w/path) for key,path in {
  'depth':'prism-progressive/depth-screen','large':'prism-progressive/large-screen',
  'probe':'prism-progressive/probe-final-screen','probe_large':'prism-progressive/probe-final-large',
  'probe_v1':'prism-progressive/probe-screen','probe_large_v1':'prism-progressive/probe-large',
  'batch':'prism-batch/nonlinear','replay':'prism-replay/screen'}.items()}
 lines=['# Multi-shift compute investigation: implementation and results','',
 '2026-09-07. All changes remain opt-in; the broad benchmark queue stays paused. '
 'These are bounded exploratory comparisons, not a publication verdict or a new Caspar comparison.','',
 '## 1. Progressive Krylov depth','',
 '`OCA_PROGRESSIVE_DEPTH=1` checks the central shifted residual against the existing '
 'Eisenstat–Walker target. At its first crossing, it scores all current shifts that were '
 'not already scored at that depth. It stops the sweep only if a finite accepted candidate '
 'reduces true cost by more than `max(1e-4, 10*ftol)` relative. Otherwise, it continues the '
 'existing CG ladder. Curvature checks, true-cost acceptance, alpha search and the existing '
 'post-sweep Armijo safeguard remain in place. It does not impose a fixed depth cap or add '
 'an early backtracking probe. This changes both scoring coverage and the work policy.','',
 'Initial prototype (V1). Three contrasting smaller scenes: 60 outer iterations, N=2 per arm, same frozen binary, '
 'rotating arm order, serial GPU. Large transfer: final-4585, 20 outers, N=1. Each process '
 'has a 60-second cap after acquiring the GPU lock. All use Config A, cached factors, '
 'multi-RHS scoring and diagonal norm optimization; backtracking has eight probes.','',
 '| Scene | Arm | N | Seconds, median | Final cost, median | Matvecs | Retries | Total scored |',
 '|---|---|---:|---:|---:|---:|---:|---:|']
 results={}
 for group in ['depth','large']:
  for scene in sorted({r['scene'] for r in groups[group]}):
   rows=[r for r in groups[group] if r['scene']==scene and r['status']=='ok'];out={}
   for arm in ['single','multi','progressive']:
    rr=[r for r in rows if r['arm']==arm]
    if not rr:continue
    out[arm]={k:median(rr,k) for k in ['seconds','cost','matvecs','rejects','total_scored']}
    x=out[arm];lines.append(f"| {scene} | {arm} | {len(rr)} | {x['seconds']:.3f} | {x['cost']:,.2f} | {x['matvecs']:g} | {x['rejects']:g} | {x['total_scored']:g} |")
   results[scene]=out
 lines+=['','Relative to existing multi-shift, progressive depth is faster on all three small '
 'screens and has equal or lower median endpoint cost. N=2 does not resolve a formal '
 'speed verdict; Venice baseline variation is substantial. Guarded single shift remains '
 'competitive and is often fastest at looser quality targets. The large run takes longer '
 'at a fixed outer budget but reaches a lower endpoint, so compare cost-matched times too.','',
 '### Quality bands','',
 'For this exploratory table only, the reference is the lowest median endpoint cost among '
 'the three arms on that scene. Targets are 1%, 3%, 5% above that reference. Values are '
 'median first recorded outer-boundary crossing times when every repeat reaches the target; '
 '`reached x/N` retains failures to reach within the cap. These retrospective references '
 'are not certified optima.','',
 '| Scene | Arm | Within 1% (s) | Within 3% (s) | Within 5% (s) |','|---|---|---:|---:|---:|']
 bands={}
 for group in ['depth','large']:
  for scene in sorted({r['scene'] for r in groups[group]}):
   rows=[r for r in groups[group] if r['scene']==scene and r['status']=='ok'];ref=min(x['cost'] for x in results[scene].values());bands[scene]={'reference':ref,'arms':{}}
   for arm in ['single','multi','progressive']:
    rr=[r for r in rows if r['arm']==arm];cells=[];bands[scene]['arms'][arm]={}
    for band in [.01,.03,.05]:
     times=[]
     for r in rr:
      hits=[float(t['wall_s']) for t in r['trace'] if float(t['cost'])<=ref*(1+band)]
      times.append(min(hits) if hits else None)
     bands[scene]['arms'][arm][str(band)]=times
     cells.append(f'{statistics.median(times):.3f}' if all(t is not None for t in times) else f'reached {sum(t is not None for t in times)}/{len(times)}')
    lines.append('| '+scene+' | '+arm+' | '+' | '.join(cells)+' |')
 large={r['arm']:r for r in groups['large'] if r['status']=='ok'}
 if set(large)>={'multi','progressive'}:
  target=large['multi']['cost'];times={arm:min(float(t['wall_s']) for t in large[arm]['trace'] if float(t['cost'])<=target*(1+1e-9)) for arm in ['multi','progressive']}
  lines+=['',f"Large cost-matched check: progressive reaches the existing multi-shift endpoint ({target:,.2f}) in {times['progressive']:.3f}s versus {times['multi']:.3f}s ({100*(1-times['progressive']/times['multi']):.1f}% sooner). N=1; this is not an independently CPU-audited endpoint."]
 lines+=['','### Isolating scoring from early stopping','',
 '`OCA_PROGRESSIVE_DEPTH=2` performs the same central-convergence scoring probe but '
 'continues the sweep. The following separate frozen-binary cohort uses N=1 per arm '
 'with the same 60/20 outer caps. It isolates the early-stop intervention; do not pool '
 'these timings into the earlier N=2 medians. This corrected V2 skips a redundant '
 'terminal menu when its exact candidates were already scored by the probe. The earlier '
 'V1 probe-only ablation is retained under `probe-screen` / `probe-large`, and is '
 'included in total experimental work but not pooled into this table.','',
 '| Scene | Arm | Seconds | Final cost | Matvecs | Retries |','|---|---|---:|---:|---:|---:|']
 for group in ['probe','probe_large']:
  for r in sorted(groups[group],key=lambda r:(r['scene'],r['arm'])):
   if r['status']=='ok':lines.append(f"| {r['scene']} | {r['arm']} | {r['seconds']:.3f} | {r['cost']:,.2f} | {r['matvecs']} | {r['rejects']} |")
 lines+=['','The corrected small-case ablation supports useful early stopping: Ladybug has fewer retries and lower cost; Dubrovnik trades 0.0047% higher cost for less work; Venice wall is effectively tied while its endpoint is lower. The large case still uses more work and reaches lower cost. N=1 prevents a definitive speed claim.','','## 2. Batched full-cost evaluation','',
 '`OCA_BATCH_COST=1` retains existing multi-RHS back-substitution inputs, materializes '
 'candidate states, and evaluates a full menu in one kernel with one host result transfer. '
 'The kernel shares observation indices and measurements across candidates; fp64 projection '
 'arithmetic and block reductions are retained. Back-substitution and retraction still run '
 'per candidate, and prepared steps are copied into the existing selection path. Thus this '
 'is a tested cost-batching prototype, not complete fusion of the entire candidate tail.','',
 '`OCA_BATCH_COST_CHECK=1` compares identical prepared states with the original evaluator. '
 'All observed cost errors were below 5e-16 relative. It checks finite/nonfinite agreement '
 'and ordering for candidate separations larger than 1e-10 relative; nearly tied ordering '
 'is not certified. For timing, each fixed menu is evaluated six times by each path in '
 'alternating order, using CUDA events; the first repeat is excluded below.','',
 '| Scene | Sequential costs, ms/menu | Batched costs, ms/menu |','|---|---:|---:|']
 batch_fixed={}
 for path in sorted((w/'prism-batch').glob('*.log')):
  txt=path.read_text();matches=re.findall(r'BATCH_TIME rep=(\d+) batch=(\d+) candidates=\d+ ms=([\d.e+-]+)',txt)
  if matches:
   v={arm:statistics.median(float(t) for rep,b,t in matches if b==arm and int(rep)>0) for arm in ['0','1']};batch_fixed[path.stem]=v
   lines.append(f"| {path.stem} | {v['0']:.3f} | {v['1']:.3f} |")
 lines+=['','The large fixed-menu cost timing is essentially unchanged. That is a reason to defer '
 'a larger fusion rewrite: current cost batching has no demonstrated large-case payoff. '
 'The earlier phase profile already bounded the whole candidate phase at about 13% of wall.','',
 '| Dubrovnik-173, 40 outers, N=2 | Seconds, median | Final cost, median |','|---|---:|---:|']
 for arm in ['multi','batch']:
  rr=[r for r in groups['batch'] if r['arm']==arm and r['status']=='ok']
  if rr:lines.append(f"| {arm} | {median(rr,'seconds'):.3f} | {median(rr,'cost'):,.2f} |")
 lines+=['','The nonlinear batch screen is effectively tied in median wall time; its small '
 'trajectory difference must not be presented as an execution speedup. No batching default changed.','',
 '## 3. Synchronization profile and exact state/controller replay','',
 'Nsight Systems, Dubrovnik-173, five outers: `MFPass1` and `MFPass2` together consume '
 '59.6% of GPU kernel time. cuBLAS dot/reduction kernels consume approximately 0.4%. '
 'The trace confirms frequent host transfers/synchronizations, but host API wait duration '
 'overlaps GPU execution and is not independently removable time. This profile does not '
 'justify a large device-side CG rewrite yet. Device scalar recurrences and freezing '
 'converged shifted systems remain deferred; no current production-depth nonfinite failure '
 'was observed.','',
 'The implemented checkpoint saves exact camera rotation matrices, translations, intrinsics, '
 'points and controller history: lambda, pre-retry lambda, point damping/ratchet, previous '
 'RHS norm, accept/reject streaks, stopping counters, confirmation flag and cost history. '
 'Derived assembly/factors are rebuilt. It supports only the plain fp64 unshared L2 '
 'diagonal configuration and rejects unsupported environment flags or mismatched settings. '
 'The runner additionally pins original input, binary and checkpoint SHA-256. Same binary '
 'and architecture are required; this is research replay, not a general persistence format.','',
 'A load/save roundtrip reproduced the checkpoint bytes exactly. On both scenes the first '
 'resumed attempt matched the uninterrupted run at logged precision, excluding elapsed '
 'time. Six-step endpoint differences were 0.0192% on Ladybug and 0.0000443% on Dubrovnik: '
 'exact restoration does not make subsequent GPU atomic reductions deterministic.','',
 'The table below starts both policies from the **same first-confirmation checkpoint** and '
 'preserves the disabled-backtracking flag. Each rollout has at most 20 additional outers, '
 'N=2, with alternating policy order. Counts exclude the saved prefix; solver wall includes '
 'checkpoint loading/setup while the CSV clock starts after restoration.','',
 '| Scene | Policy | Seconds, median | Final cost, median | Rollout retries | Rollout matvecs | Rollout rescues | Rearm events |',
 '|---|---|---:|---:|---:|---:|---:|---:|']
 for scene in sorted({r['scene'] for r in groups['replay']}):
  for arm in ['original','rearm']:
   rr=[r for r in groups['replay'] if r['scene']==scene and re.fullmatch(arm+r'-[12]',r['arm']) and r['status']=='ok']
   if rr:lines.append(f"| {scene} | {arm} | {median(rr,'seconds'):.3f} | {median(rr,'cost'):,.2f} | {median(rr,'rollout_rejects'):g} | {median(rr,'rollout_matvecs'):g} | {median(rr,'rollout_rescues'):g} | {median(rr,'rearms'):g} |")
 lines+=['','Ladybug validates the mechanism: retry suppression is large, with about 0.10% higher '
 'endpoint cost over this short rollout. Dubrovnik never rearms within the budget, so '
 'its between-run differences cannot be attributed to the policy. There is no two-scene '
 'activation consensus in this checkpoint test. All replay Armijo and rearming eligibility '
 'trace checks pass.','',
 '## Validation and limits','',
 '* CUDA CLI and core library builds pass. Python compilation and `git diff --check` pass.',
 '* Compute Sanitizer reports zero errors for the small combined progressive/batch diagnostic.',
 '* True central shifted residuals agree with the recurrence within the declared 1e-5 RHS-relative diagnostic tolerance on Ladybug-49, Dubrovnik-173 and Ladybug-1197.',
 '* Checkpoint bytes roundtrip exactly; changed-policy loads fail as expected; replay traces pass Armijo/confirmation checks.',
 '* Cold-start timed initial objectives are independently checked in fp64. Replay restores the identical saved state and verifies its GPU objective; checkpoint and final endpoints have no new independent CPU audit. No fresh Caspar run was performed.',
 '* N=1/N=2 and short caps are exploratory. Default settings are unchanged; source and reports are local and uncommitted.',
 '* Broad study coordinators remain paused. No scene-specific mixture is presented as one universal configuration.','',
 '## Artifacts and reproduction','',
 '* Source: `gpu/oca_cuda.cu`, `gpu/replay_checkpoint.h`.',
 '* Runners: `bench/progressive_screen.py`, `bench/depth_probe_screen.py`, `bench/replay_screen.py`; all accept `--binary` and `--out`.',
 '* Frozen binaries, source snapshots, manifests and logs: `/workspace/prism-progressive`, `/workspace/prism-batch`, `/workspace/prism-sync`, `/workspace/prism-replay`.',
 '* Replay capture: `OCA_REPLAY_SAVE=<file> OCA_REPLAY_AT=confirm OCA_REPLAY_STEPS=6`.',
 '* Replay rollout: `OCA_REPLAY_LOAD=<file> OCA_REPLAY_STEPS=20`, optionally `OCA_BACKTRACK_REARM=1`, with the same original input and solver settings.',
 '* Resume the broad queue only after choosing a fixed policy and a larger validation budget.','']
 timed=[]
 for key in ['depth','large','probe','probe_large','probe_v1','probe_large_v1','batch']:timed.extend(groups[key])
 timed.extend(r for r in groups['replay'] if re.fullmatch(r'(original|rearm)-[12]',r['arm']))
 summary=dict(groups=groups,medians=results,quality_bands=bands,fixed_batch_ms=batch_fixed,timed_runs=len(timed),failed_runs=sum(r['status']!='ok' for r in timed),solver_seconds=sum(r.get('seconds',0) for r in timed))
 lines.insert(4,f"Timed work: {summary['timed_runs']} runs, {summary['failed_runs']} failures, {summary['solver_seconds']/60:.2f} cumulative solver minutes. Diagnostic, profiling and capture runs are separate.\n")
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text('\n'.join(lines));(w/'prism-progressive/compute-results.json').write_text(json.dumps(summary,indent=2)+'\n')
 print(json.dumps({k:summary[k] for k in ['timed_runs','failed_runs','solver_seconds']}))
if __name__=='__main__':main()
