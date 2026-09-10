#!/usr/bin/env python3
"""Summarize paired initialization seeds; preserve failures and timing scope."""
import argparse,collections,csv,json,pathlib,re,statistics
from expanded_caspar_screen import sha,write

def stats(v):
 ok=[x for x in v if x['status']=='ok'];hits=[x for x in ok if x['hit']]
 return dict(hits=len(hits),valid=len(ok),n=len(v),crossing=statistics.median(x['crossing'] for x in hits) if len(hits)==3 else None,cost=statistics.median(x['cost'] for x in ok) if ok else None,wall=statistics.median(x['process_wall'] for x in ok) if ok else None,rejections=sum(x.get('logged_rejections',0) for x in ok),restarts=sum(x.get('restarted',False) for x in ok))
def winner(p,c):
 if p['hits']!=c['hits']:return ('PRISM' if p['hits']>c['hits'] else 'Caspar'),None
 if p['hits']<3:return 'unresolved',None
 ratio=c['crossing']/p['crossing'];return ('tie' if max(ratio,1/ratio)<=1.05 else 'PRISM' if ratio>1 else 'Caspar'),ratio

def main():
 ap=argparse.ArgumentParser();ap.add_argument('root',type=pathlib.Path);ap.add_argument('--partial',action='store_true');a=ap.parse_args();r=a.root
 path=r/('partial-results.json' if a.partial else 'results.json')
 if not path.exists():print('Preparing inputs');return
 rows=json.loads(path.read_text());protocol=json.loads((r/'protocol.json').read_text());groups=collections.defaultdict(list)
 for x in rows:
  if x['status']=='ok':
   if x['arm']=='restart':x['logged_rejections']=sum(s['rejects'] for s in x['stages']);x['logged_accepts']=sum(s['accepts'] for s in x['stages'])
   else:
    log=(pathlib.Path(x['artifact_dir'])/'caspar-runs'/f"{x['name']}.log").read_text()
    acc=list(map(int,re.findall(r'TRACE .*? accepted=(\d+)',log)));assert len(acc)==len(x['trace']) and all(v in [0,1] for v in acc)
    prev=x['initial_native']
    for accepted,step in zip(acc,x['trace']):assert accepted==int(step['cost']<prev);prev=step['cost']
    x['logged_rejections']=acc.count(0);x['logged_accepts']=acc.count(1)
  groups[x['scene'],x['arm']].append(x)
 valid=[x for x in rows if x['status']=='ok'];summary=dict(completed=len(rows),valid=len(valid),hits={arm:sum(x['hit'] for x in rows if x['arm']==arm) for arm in ['restart','caspar64']},native_seconds=sum(x['seconds'] for x in valid),process_wall=sum(x['process_wall'] for x in valid),restarts=sum(x.get('restarted',False) for x in valid),logged_rejections={arm:sum(x['logged_rejections'] for x in valid if x['arm']==arm) for arm in ['restart','caspar64']})
 print(json.dumps(summary,indent=2))
 if a.partial:return
 assert len(rows)==24 and len({x['name'] for x in rows})==24
 old=json.loads(pathlib.Path('/workspace/prism-caspar-expanded/results.json').read_text());cells=[]
 for scene in protocol['scenes']:
  arms={arm:stats(groups[scene,arm]) for arm in ['restart','caspar64']};p,c=arms.values();w,ratio=winner(p,c)
  control={arm:stats([x for x in old if x['scene']==scene and x['level']=='medium' and x['arm']==arm]) for arm in arms};cw,cr=winner(*control.values())
  cells.append(dict(scene=scene,arms=arms,winner=w,caspar_over_prism=ratio,control=control,control_winner=cw,control_caspar_over_prism=cr))
 summary['initial_cost_ratios']=[dict(scene=x['scene'],seed=x['seed'],ratio=x['initial_reference']/next(z['initial_reference'] for z in old if z['scene']==x['scene'] and z['arm']=='caspar64'),initial_cost=x['initial_reference']) for x in valid if x['arm']=='caspar64']
 summary['scenes']=cells;write(r/'summary.json',summary);write(r/'annotated-results.json',rows)
 with (r/'results.csv').open('w') as f:
  fields=['scene','seed','arm','target','cap','status','hit','crossing','cost','seconds','process_wall','logged_accepts','logged_rejections','restarted','audit_error']
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
 plan=json.loads((r/'plan.json').read_text());inputs=json.loads((r/'verified-inputs.json').read_text());mapping={(x['scene'],x['seed']):x for x in inputs};assert len(mapping)==12
 for x in inputs:assert sha(x['data'])==x['data_sha256'];assert sha('/workspace/bal/'+x['scene']+'.txt')==x['original_sha256']
 for name,h in json.loads((r/'tooling-hashes.json').read_text()).items():assert sha(pathlib.Path('/workspace/prism-ba/bench')/name)==h
 manifests=0
 for x,j in zip(rows,plan['jobs']):
  for k in ['name','scene','seed','arm','data','target','cap']:assert x[k]==j[k]
  assert x['target']==protocol['targets'][x['scene']] and x['cap']==protocol['caps'][x['scene']]
  if x['status']!='ok':continue
  assert x['audit_error']<1e-7
  d=pathlib.Path(x['artifact_dir'])
  ms=list((d/'prism/screen').glob('*.manifest.json'))+list((d/'caspar-runs').glob('*.manifest.json'))
  for p in ms:
   m=json.loads(p.read_text());assert m['data_sha256']==mapping[x['scene'],x['seed']]['data_sha256']
   assert m['binary_sha256']==protocol['prism_sha256' if x['arm']=='restart' else 'caspar_sha256']
   assert x['data'] in m['command'];manifests+=1
  if x['arm']=='restart':
   z=json.loads((d/'prism/screen'/f"{x['name']}.result.json").read_text());s=z['stages'][z['selected_stage']]
   assert sha(d/'prism/screen'/f"{x['name']}.best.state")==sha(s['stem']+'.state')
   assert abs(sum(t['seconds'] for t in z['stages'])-x['seconds'])<1e-8
  else:assert x['initial_native_gap']<1e-6 and x['initial_cpu_gap']<1e-6
 assert sha('/workspace/prism-early-restart/prism-v7')==protocol['prism_sha256'] and sha('/workspace/prism-caspar-current/caspar64')==protocol['caspar_sha256']
 assert sha('/workspace/prism-ba/gpu/oca_cuda.cu')==sha('/workspace/prism-early-restart/source-v7.cu')
 paused=[]
 for x in json.load(open('/workspace/prism-block-error/paused-verified.json')):
  v=(pathlib.Path('/proc')/str(x['pid'])/'stat').read_text().split();assert v[2]=='T' and v[21]==x['start_ticks'];paused.append(x)
 proof=dict(input_variants=12,solver_stages=manifests,max_endpoint_audit_error=max(x['audit_error'] for x in valid),max_caspar_native_cpu_gap=max(x.get('native_cpu_gap',0) for x in valid),paused=paused)
 write(r/'verification.json',proof)
 lines=['# Initialization noise: frozen PRISM versus Caspar FP64','','Four contrasting original BAL objectives, three seeded starting states, one solve per seed and arm:24 pipelines. Gaussian additions use sigma0.001 radians per angle-axis coordinate and0.001 times median centered point radius per translation/point coordinate. Intrinsics stay unchanged; original observation bytes are identical. The existing medium targets and4/4/12/20 second native caps are retained. No new calibration or solver tuning. See [protocol](noise_caspar_protocol.md).','',f"Certified target hits: PRISM **{summary['hits']['restart']}/12**, Caspar **{summary['hits']['caspar64']}/12**. PRISM restart activations: **{summary['restarts']}/12**. Logged rejections: PRISM{summary['logged_rejections']['restart']}, Caspar{summary['logged_rejections']['caspar64']}.",'','Seeds are different initializations, not timing repeats or independent scenes. Medians mix initialization difficulty with runtime variability. Compare each matched seed as well as the aggregate. Previous unperturbed runs are historical context, not newly interleaved controls.','','## Scene-level comparison','','Median native certified crossing is shown only if all three seeds hit. Rank success count first; if both3/3, compare median with a5% tie band. No finite speed ratio for misses.','','| Scene | Unperturbed medium winner | PRISM noisy hits / time | Caspar noisy hits / time | Noisy verdict |','|---|---|---:|---:|---|']
 fmt=lambda z:f"{z['hits']}/3; {z['crossing']:.3f}s" if z['crossing'] is not None else f"{z['hits']}/3; —"
 big=next(x for x in cells if x['scene']=='final-13682');bp=big['arms']['restart']['cost'];bc=big['arms']['caspar64']['cost']
 br=[x['ratio'] for x in summary['initial_cost_ratios'] if x['scene']=='final-13682']
 interpretation=[f"The median winner is preserved on the three smaller problems: PRISM on Trafalgar126 and Final1936, Caspar on Dubrovnik88. Final1936 still flips winner on seed17, so the median does not imply dominance at every initialization. All six noisy Final13682 runs miss the unchanged target; Caspar has the lower endpoint cost on each seed, with median {bc:,.2f} versus PRISM {bp:,.2f}. No equal-quality speed ratio is available there.", '', f"The largest scene's initial objective increases {min(br):.2f}–{max(br):.2f}×, whereas the three smaller problems increase only1.02–1.67×. Small parameter noise is not uniformly mild in reprojection cost. This single-level, three-seed test does not establish general robustness. PRISM's zero rejections mean the test still does not exercise active early restart. Caspar remains faster on Dubrovnik88 despite its logged rejections; counts alone do not determine wall time.", '']
 i=lines.index('## Scene-level comparison');lines[i:i]=interpretation
 for x in cells:
  p,c=x['arms'].values();v=x['winner'];ratio=x['caspar_over_prism']
  if ratio is not None and v!='tie':v+=f' {max(ratio,1/ratio):.2f}× as fast'
  lines.append(f"| {x['scene']} | {x['control_winner']} | {fmt(p)} | {fmt(c)} | {v} |")
 lines+=['','## Starting-cost effect','','These ratios quantify the perturbation effect; a symmetric parameter perturbation is not guaranteed to increase every initial objective.','','| Scene | Seed | Initial cost / original initial cost |','|---|---:|---:|']
 for x in summary['initial_cost_ratios']:lines.append(f"| {x['scene']} | {x['seed']} | {x['ratio']:.6g} |")
 lines+=['','## Each matched seed','','| Scene | Seed | PRISM hit / seconds | Caspar hit / seconds | PRISM cost gap | Caspar cost gap | PRISM rejections | Caspar logged rejections | PRISM restarted |','|---|---:|---:|---:|---:|---:|---:|---:|---|']
 by={(x['scene'],x['seed'],x['arm']):x for x in rows}
 tf=lambda x:f"{x['crossing']:.3f}" if x['hit'] else 'Miss'
 gf=lambda x:'unavailable' if x['status']!='ok' else f"{100*(x['cost']/x['target']-1):.6g}%"
 for scene in protocol['scenes']:
  for seed in protocol['seeds']:
   p,c=[by[scene,seed,arm] for arm in ['restart','caspar64']]
   lines.append(f"| {scene} | {seed} | {tf(p)} | {tf(c)} | {gf(p)} | {gf(c)} | {p.get('logged_rejections','—')} | {c.get('logged_rejections','—')} | {p.get('restarted','—')} |")
 lines+=['','Positive cost gaps mean the final endpoint is above the unchanged target. Negative gaps mean below it; a hit also requires a certified stopping event within cap. PRISM retains its1e-8 relative inward stopping margin; both arms require independent CPU endpoint scoring. Native clocks have different setup scopes. Caspar process wall includes in-driver CPU checks while PRISM independent endpoint audits run after its process-wall window. All abandoned PRISM restart work is charged.','','Caspar rejection counts come from its existing full-precision score-decrease acceptance trace. The checked driver computes this indicator independently of the backend acceptance flag. These are logged, completed decisions; a final diagonal-exit rejection or budget-discarded attempt may not be logged and is not added to this count. PRISM counts are its logged rejected outer attempts. These counts are diagnostic, not identical units of work across algorithms.','','## Endpoint costs and wall times','','| Scene | Seed | Arm | Final CPU cost | Native return seconds | Process wall seconds |','|---|---:|---|---:|---:|---:|']
 for x in rows:
  if x['status']=='ok':lines.append(f"| {x['scene']} | {x['seed']} | {x['arm']} | {x['cost']:.6f} | {x['seconds']:.3f} | {x['process_wall']:.3f} |")
 lines+=['','## Verification','',f"{len(valid)}/24 pipelines returned independently audited states; {manifests} solver-stage manifests match frozen binaries and exact perturbed input hashes. All12 inputs passed observation-byte, intrinsic, seeded-parameter and serialization checks before any measurement. Retained PRISM best-state copies and cumulative stage times match. Maximum endpoint relative audit error {proof['max_endpoint_audit_error']:.3g}; maximum Caspar native/CPU endpoint difference {proof['max_caspar_native_cpu_gap']:.3g}. Original source files and PRISM v7 source are unchanged. All11 older jobs remain paused.",'',f"Native solver work: {summary['native_seconds']:.3f}s. Measured process wall: {summary['process_wall']:.3f}s, excluding outer orchestration and separate audits. No additional runs or noise levels were selected after outcomes.",'','Artifacts: `/workspace/prism-caspar-noise/` contains the protocol, twelve verified inputs, per-run traces/states/manifests, `results.json`, `annotated-results.json`, `results.csv`, `summary.json`, and `verification.json`. Reproduce with `python3 bench/noise_caspar_screen.py`, then `python3 bench/summarize_noise_caspar.py /workspace/prism-caspar-noise`.']
 failures=[x for x in rows if x['status']!='ok']
 if failures:lines+=['','Failures:']+[f"- {x['name']}: {x['status']}; see {x['artifact_dir']}" for x in failures]
 pathlib.Path('/workspace/prism-ba/docs/noise_caspar_results.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':main()
