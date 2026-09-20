#!/usr/bin/env python3
"""Write final tables from verified raw records; no ratios for censored cells."""
import pathlib,json,statistics
ROOT=pathlib.Path('/workspace/prism-fresh-tr-caspar');REPO=pathlib.Path(__file__).resolve().parents[1]
def main():
 s=json.loads((ROOT/'summary.json').read_text());v=json.loads((ROOT/'verification.json').read_text());rows=json.loads((ROOT/'results.json').read_text());assert s['completed']==s['planned']==45 and v['runs']==45
 names={'tr':'PRISM TR FP64','caspar64':'Caspar FP64','caspar32':'Caspar FP32'};lines=['# Fresh paired PRISM TR versus Caspar FP64 and FP32','', 'Three fresh runs per arm on five original BAL scenes, including three large scenes up to 28.99 million observations. All arms use the same frozen quality targets. Full settings and timing scopes are in the [protocol](fresh_tr_caspar_protocol.md).','', '| Scene | PRISM TR FP64 | Caspar FP64 | Caspar FP32 | Winner |','|---|---:|---:|---:|---|']
 def cell(x):
  if x['median_crossing'] is not None:return f"{x['median_crossing']:.3f} s ({x['hits']}/3)"
  if x['hits']>0:return f"{x['hits']}/3 certified; {x['range'][0]:.3f}–{x['range'][1]:.3f} s on successes"
  return f"Miss ({x['hits']}/3)" if x['failures']==0 else f"{x['hits']}/3 hits; {x['failures']} failures"
 winners={}
 for scene,arms in s['scenes'].items():
  valid={a:x['median_crossing'] for a,x in arms.items() if x['median_crossing'] is not None}
  winner=min(valid,key=valid.get) if valid else None;winners[scene]=winner
  lines.append('| '+scene+' | '+' | '.join(cell(arms[a]) for a in names)+' | '+(names[winner] if winner else 'None reaches target consistently')+' |')
 lines+=['','Complete cells show median **native time to the same quality target**, not normalized application latency. The winner column selects the fastest arm with 3/3 certified hits; a faster partially successful arm is reported separately. “Miss” means the target was not certified within that scene’s budget; it is not an observed time-to-target. Budgets are 4 s for Trafalgar/Dubrovnik, 12 s for Final1936, and 20 s for Final4585/Final13682.','',f"Certified targets: **PRISM {v['hits']['tr']}/15; Caspar FP64 {v['hits']['caspar64']}/15; Caspar FP32 {v['hits']['caspar32']}/15**.",'','## Interpretation','']
 for scene,arms in s['scenes'].items():
  winner=winners[scene]
  if not winner:continue
  w=arms[winner]['median_crossing'];other=[]
  for a in names:
   if a==winner:continue
   t=arms[a]['median_crossing']
   other.append(f"{t/w:.2f}× faster than {names[a]}" if t is not None else f"{names[a]} does not reach the target consistently")
  lines.append(f"- **{scene}: {names[winner]} wins**; "+'; '.join(other)+'.')
 lines+=['','There is no universal winner. These scenes are selected and only three repeats are available. FP32 is a substantive baseline: qualifying FP32 endpoints are judged on the same original-observation objective, so its wins cannot be dismissed merely because the arithmetic is less precise. This comparison does not demonstrate algorithmic novelty or broad superiority.','', '## Repeats, endpoint quality and timing scope','', '| Scene | Arm | Successful crossing range | Median audited endpoint | Median native return | Median process wall |','|---|---|---:|---:|---:|---:|']
 for scene,arms in s['scenes'].items():
  for a,x in arms.items():
   ran=x['range'];r=f'{ran[0]:.3f}–{ran[1]:.3f} s' if ran else '—'
   endpoint=f"{x['median_endpoint']:.6f}" if x['median_endpoint'] is not None else '—'
   ret=f"{x['median_native']:.3f} s" if x['median_native'] is not None else '—'
   lines.append(f"| {scene} | {names[a]} | {r} | {endpoint} | {ret} | {x['median_process_wall']:.3f} s |")
 lines+=['','Native time includes PRISM solver-local initialization but excludes its CLI upload; Caspar excludes graph setup. Process wall includes different internal CPU audit scopes and is not a normalized end-to-end comparison. Independent Python endpoint audits are outside both clocks. Comparing raw endpoint costs across successful runs is also not a fixed-budget quality comparison, since these runs stop when their target is reached.','', 'For missed targets, audited endpoint excess over target is:','']
 for scene,arms in s['scenes'].items():
  for a,x in arms.items():
   if x['hits']<3 and x['median_over_target_fraction'] is not None:lines.append(f"- {scene}, {names[a]}: median **{100*x['median_over_target_fraction']:.3f}% above target**.")
 overruns=[r['seconds']-r['cap'] for r in rows if r.get('seconds') is not None]
 lines += ['',f"Native caps are checked at solver boundaries. The largest return-time overshoot is **{max(overruns):.3f} s**; all spent native work remains in the records. Hits still require a qualifying crossing at or before the requested cap. No speedup is inferred by dividing a cap by a successful solver’s time.",'','## FP32 and independent verification','',f"All **{v['audited_endpoints']} exported endpoints** pass the original-observation CPU audit; maximum disagreement with the driver's CPU score (or PRISM report) is **{v['max_reported_cpu_audit_error']:.3g}**. There are **{sum(v['uncertified_native_hits'].values())} uncertified native hits** and **{len(v['failures'])} process/audit failures**."]
 fp=[r for r in rows if r['arm']=='caspar32'];gap=max(r['native_cpu_gap'] for r in fp);igap=max(r['initial_cpu_gap'] for r in fp)
 lines += ['',f"FP32's final native score differs from the independently audited original-observation score by up to **{100*gap:.5f}%**. Its largest CPU-audited initial-cost difference from the original double input is **{100*igap:.5f}%**. These are precision/representation effects, separate from auditor agreement. Certification uses the audited endpoint, not the optimistic native value. Every fresh Caspar run logs and verifies its FP32 or FP64 precision.", '', f"The verifier checks all three arms occupy each paired-run position once per scene, frozen binary/source/tooling/data hashes, original input and endpoint costs, target certification, and **{v['accepted_tr_feasibility_checks']}** accepted TR feasibility/model-ratio decisions. Caspar generated-code provenance is pinned to COLMAP commit `{v['precision_proof']}`; the solver code is statically linked into the recorded executables. This is the standalone backend driver with COLMAP-default solver settings, not a full COLMAP reconstruction run.", '', f"Total measured work: **{s['native_seconds']:.3f} native solve seconds**, **{s['process_seconds']:.3f} subprocess wall seconds**, across 45 runs. CPU audit time outside the subprocess is additional. No parameter retuning, input modification or replacement reruns occurred within the primary comparison. The separately labelled stopping-margin follow-up below does not replace any primary result.", '', '## Reproduction and artifacts','', '`bench/fresh_tr_caspar.py` runs the frozen study and resumes only already-completed records. `bench/summarize_fresh_tr_caspar.py`, `bench/verify_fresh_tr_caspar.py`, and `bench/write_fresh_tr_caspar_report.py` reproduce the summary, verification and this report.', '', 'All protocols, copied driver sources, precision proof, executable/input hashes, run manifests, logs, CSVs, matrix states, per-run JSON, `summary.json` and `verification.json` are retained under `/workspace/prism-fresh-tr-caspar/`. Solver binaries, production defaults and older paused jobs are unchanged.']
 guard_file=ROOT/'fp32-stop-guard/verification.json'
 if guard_file.exists():
  g=json.loads(guard_file.read_text());gr=json.loads((ROOT/'fp32-stop-guard/results.json').read_text())
  failed=next(r for r in rows if r['scene']=='final-13682' and r.get('uncertified_native_hit'))
  section=['','## Separate FP32 stopping-margin follow-up','',
   f"The third unmodified FP32 largest-scene run stopped natively at **{failed['crossing']:.3f} s**, reporting score **{failed['native_cost']:.0f}**. Its independently audited cost was **{failed['cost']:.6f}**, above the effective target **{failed['target']:.6f}** by **{100*failed['endpoint_over_target_fraction']:.5f}%**. It remains a failure of the primary certification criterion; the successful FP32 times above are not averaged with this optimistic stop.",'',
   'After retaining that failure, three additional FP32 runs on Final13682 used one predeclared adjustment: a native stopping threshold 0.1% below the original effective target. The executable, solver settings, input, 20-second cap and original audited certification target stayed the same. This margin is an empirical screening aid, not a proven error bound or a setting validated on every scene.', '',
   f"The follow-up certified **{g['hits']}/3 targets**, with median native crossing **{g['median_crossing']:.3f} s** and range **{g['crossing_range'][0]:.3f}–{g['crossing_range'][1]:.3f} s**. All three endpoints were independently re-audited. This is a supplementary FP32-only check, not a replacement paired comparison or evidence that a stricter threshold itself improves speed; floating-point trajectories varied between runs.", '',
   f"Additional work: **{g['native_seconds']:.3f} native seconds**, **{g['process_seconds']:.3f} subprocess seconds**. Raw records and frozen amendment are in `/workspace/prism-fresh-tr-caspar/fp32-stop-guard/`; scripts are `bench/caspar_fp32_stop_guard.py` and `bench/verify_fp32_stop_guard.py`."]
  lines+=section
 (REPO/'docs/fresh_tr_caspar_results.md').write_text('\n'.join(lines)+'\n')
 print(REPO/'docs/fresh_tr_caspar_results.md')
if __name__=='__main__':main()
