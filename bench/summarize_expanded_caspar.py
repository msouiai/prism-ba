#!/usr/bin/env python3
"""Summarize the frozen extension without treating repeats as independent scenes."""
import argparse,collections,csv,hashlib,json,math,pathlib,statistics
import numpy as np

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def med(v):return statistics.median(v) if v else None
def main():
 ap=argparse.ArgumentParser();ap.add_argument('root',type=pathlib.Path);ap.add_argument('--partial',action='store_true');args=ap.parse_args();r=args.root
 fn=r/('partial-results.json' if args.partial else 'results.json')
 if not fn.exists():print('Calibration ongoing');return
 rows=json.loads(fn.read_text());protocol=json.loads((r/'protocol.json').read_text());groups=collections.defaultdict(list)
 for x in rows:groups[x['scene'],x['level'],x['arm']].append(x)
 cells=[]
 for s in protocol['scenes']:
  for level in protocol['levels']:
   key=s['scene'];arms={}
   for a in ['restart','caspar64']:
    v=groups[key,level,a];ok=[x for x in v if x['status']=='ok'];hits=[x for x in ok if x['hit']]
    arms[a]=dict(completed=len(v),valid=len(ok),hits=len(hits),crossing=med([x['crossing'] for x in hits]) if len(hits)==3 else None,crossing_range=[min(x['crossing'] for x in hits),max(x['crossing'] for x in hits)] if hits else None,cost=med([x['cost'] for x in ok]),seconds=med([x['seconds'] for x in ok]),wall=med([x['process_wall'] for x in ok]),restarts=sum(x.get('restarted',False) for x in ok))
   p,c=arms.values();ratio=None
   if min(p['completed'],c['completed'])<3:winner='pending'
   elif p['hits']!=c['hits']:winner='PRISM' if p['hits']>c['hits'] else 'Caspar'
   elif p['hits']<3:winner='unresolved'
   else:
    ratio=c['crossing']/p['crossing'];winner='tie' if max(ratio,1/ratio)<=1.05 else 'PRISM' if ratio>1 else 'Caspar'
   v=groups[key,level,'restart']+groups[key,level,'caspar64']
   cells.append(dict(scene=key,family=key.split('-')[0],level=level,target=v[0]['target'] if v else None,cap=s['cap'],arms=arms,winner=winner,caspar_over_prism=ratio))
 counts=collections.Counter(x['winner'] for x in cells)
 valid=[x for x in rows if x['status']=='ok'];cal=json.loads((r/'calibration.json').read_text());cv=[x for x in cal if x['status']=='ok']
 summary=dict(planned=216,completed=len(rows),valid=len(valid),hits={a:sum(x['hit'] for x in rows if x['arm']==a) for a in ['restart','caspar64']},winners=dict(counts),restarts=sum(x.get('restarted',False) for x in valid),native_seconds=sum(x['seconds'] for x in valid),process_wall=sum(x['process_wall'] for x in valid),calibration_native_seconds=sum(x['seconds'] for x in cv),cells=cells)
 rng=np.random.default_rng(20260908);stability={}
 for level in protocol['levels']:
  eligible=[x for x in cells if x['level']==level and x['caspar_over_prism'] is not None]
  logs=np.array([math.log(x['caspar_over_prism']) for x in eligible]);n=len(logs)
  if n:
   boot=np.exp(logs[rng.integers(0,n,size=(10000,n))].mean(axis=1));leave={}
   for family in sorted({x['family'] for x in eligible}):
    z=[math.log(x['caspar_over_prism']) for x in eligible if x['family']!=family]
    if z:leave[family]=math.exp(statistics.mean(z))
   stability[level]=dict(eligible_scenes=n,geomean_caspar_over_prism=math.exp(float(logs.mean())),bootstrap_scene_interval95=np.quantile(boot,[.025,.975]).tolist(),leave_one_family_out=leave)
 summary['conditional_stability']=stability
 summary['by_level']={level:dict(hits={a:sum(x['hit'] for x in rows if x['level']==level and x['arm']==a) for a in ['restart','caspar64']},winners=dict(collections.Counter(x['winner'] for x in cells if x['level']==level))) for level in protocol['levels']}
 summary['by_family']={family:dict(scenes=len({x['scene'] for x in cells if x['family']==family}),winners=dict(collections.Counter(x['winner'] for x in cells if x['family']==family))) for family in sorted({x['family'] for x in cells})}
 summary['miss_diagnostics']={a:dict(late_crossings=sum(x['arm']==a and not x['hit'] and x.get('crossing') is not None and x['crossing']>x['cap'] for x in valid),endpoint_within_0_001_percent_of_target=sum(x['arm']==a and not x['hit'] and x['cost']<=x['target']*1.00001 for x in valid),endpoint_in_prism_safety_margin=sum(x['arm']==a and not x['hit'] and x['target']*(1-1e-8)<x['cost']<=x['target'] for x in valid)) for a in ['restart','caspar64']}
 (r/('partial-summary.json' if args.partial else 'summary.json')).write_text(json.dumps(summary,indent=2)+'\n')
 print(json.dumps({k:v for k,v in summary.items() if k not in ['cells','conditional_stability']},indent=2))
 if args.partial:return
 assert len(rows)==216
 with (r/'measurement-results.csv').open('w') as f:
  fields=['scene','level','target','cap','arm','rep','status','hit','crossing','cost','seconds','process_wall','restarted','audit_error','artifact_dir']
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
 plan=json.loads((r/'measurement-plan.json').read_text());assert {x['name'] for x in rows}=={x['name'] for x in plan['jobs']}
 byname={x['name']:x for x in rows}
 for j in plan['jobs']:
  x=byname[j['name']]
  for k in ['scene','level','target','cap','arm','rep']:assert x[k]==j[k],(j['name'],k)
  if j['anchor'] is not None:
   assert j['anchor']==min(z['cost'] for z in cv if z['scene']==j['scene'])
   assert j['target']==j['anchor']*protocol['levels'][j['level']]
 before=r/'measurement-plan-before-cpu-cache.json'
 if before.exists():
  old=json.loads(before.read_text());new=json.loads(json.dumps(plan))
  for j in new['jobs']:j.pop('cpu_cache',None)
  assert new==old
 data={s['scene']:s['data_sha256'] for s in protocol['scenes']}
 for scene,h in data.items():assert sha('/workspace/bal/'+scene+'.txt')==h
 assert sha('/workspace/prism-early-restart/prism-v7')==protocol['prism_sha256']
 assert sha('/workspace/prism-caspar-current/caspar64')==protocol['caspar_sha256']
 assert sha('/workspace/prism-ba/gpu/oca_cuda.cu')==sha('/workspace/prism-early-restart/source-v7.cu')
 manifests=0
 for x in valid+cv:
  assert x['audit_error']<1e-7
  dest=pathlib.Path(x['artifact_dir'])
  for f in list((dest/'prism/screen').glob('*.manifest.json'))+list((dest/'caspar-runs').glob('*.manifest.json')):
   m=json.loads(f.read_text());assert m['data_sha256']==data[x['scene']];assert m['binary_sha256']==protocol['prism_sha256'] if x['arm']=='restart' else m['binary_sha256']==protocol['caspar_sha256'];manifests+=1
  if x['arm']=='restart':
   d=json.loads((dest/'prism/screen'/f"{x['name']}.result.json").read_text());s=d['stages'][d['selected_stage']]
   assert sha(dest/'prism/screen'/f"{x['name']}.best.state")==sha(s['stem']+'.state')
   assert abs(sum(z['seconds'] for z in d['stages'])-x['seconds'])<1e-8
  else:
   assert x['initial_native_gap']<1e-6 and x['initial_cpu_gap']<1e-6
   assert all(b['cost']<=a['cost']+abs(a['cost'])*1e-12 for a,b in zip(x['trace'],x['trace'][1:]))
 for name,h in json.loads((r/'tooling-with-cache-hashes.json').read_text()).items():
  assert sha(pathlib.Path('/workspace/prism-ba/bench')/name)==h,(name,'tooling changed')
 cache_count=0
 for mpath in (r/'cpu-cache').glob('*/meta.json'):
  m=json.loads(mpath.read_text());assert m['data_sha256'] in data.values();assert sha(mpath.parent/'observations.npy')==m['array_sha256'];cache_count+=1
 paused=[]
 for x in json.load(open('/workspace/prism-block-error/paused-verified.json')):
  v=(pathlib.Path('/proc')/str(x['pid'])/'stat').read_text().split();assert v[2]=='T' and v[21]==x['start_ticks'];paused.append(x)
 proof=dict(cpu_caches_checked=cache_count,max_caspar_native_cpu_gap=max(x.get('native_cpu_gap',0) for x in valid+cv),manifests_checked=manifests,max_endpoint_audit_error=max(x['audit_error'] for x in valid+cv),max_caspar_initial_gap=max(max(x.get('initial_native_gap',0),x.get('initial_cpu_gap',0)) for x in valid+cv),paused=paused,measurement_stages=sum(len(x.get('stages',[None])) for x in valid),calibration_stages=sum(len(x.get('stages',[None])) for x in cv))
 (r/'verification.json').write_text(json.dumps(proof,indent=2)+'\n')
 lines=['# Expanded frozen PRISM versus Caspar FP64 comparison','','2026-09-08. Twelve additional local BAL problems; all local instances absent from the preceding nine-scene comparison. This is a local census extension, not independent random recordings. Related BAL variants can overlap. Earlier results use different target protocols and are not pooled into a single speed headline.','',f"Measurement target hits: **PRISM {summary['hits']['restart']}/108; Caspar FP64 {summary['hits']['caspar64']}/108**. Across 36 scene/target cells: PRISM wins {counts['PRISM']}, Caspar wins {counts['Caspar']}, and {counts['unresolved']} are unresolved. These cells are not independent scenes.",'','## Protocol','','Both solvers, settings and original inputs are frozen. PRISM v7 is the early-restart candidate with point safeguard and compact FP64 storage. Caspar is the previously precision-verified FP64 COLMAP-generated backend with unchanged driver defaults; it is not full COLMAP reconstruction. Both optimize the same SIMPLE_RADIAL objective, k2 zero, original observations. Every valid endpoint is independently CPU-audited.','','One equal-budget calibration run per arm and scene establishes reference = minimum audited endpoint across both arms. Calibration runs do not enter measured timings. Three frozen targets are reference ×1.02 (loose), ×1.005 (medium), ×1.0 (tight). References are short-budget outcomes, not known optima, and can reflect a lucky calibration trajectory. No threshold was adjusted after measurement.','','Three repeats per arm/target; seeded scene and target permutation, alternating arm order. Native caps by observation count: <1M four seconds, <3M eight, <6M twelve, otherwise twenty. Process safety timeout180 seconds accommodates data loading/export. Calibration failures remain visible and mark an arm unavailable; measurement failures are retained without retries. Full machine-readable protocol and raw runs are under `/workspace/prism-caspar-expanded/`.','','## All time-to-quality results','','Times are median native certified stopping-event crossings, shown only when all three repeats hit. Rank hit count first; both3/3 then compare median. Within5% is a descriptive tie. Equal partial success is unresolved. No finite speed ratio for capped misses.','','| Scene | Level / target | PRISM hits; seconds | Caspar hits; seconds | Verdict |','|---|---|---:|---:|---|']
 interpretation=["PRISM's clearest advantage is loose/medium target reachability under these short budgets. PRISM reaches all three repeats on11/12 loose targets and10/12 medium targets, but0/12 tight targets; Caspar reaches7/12,4/12,and1/12 respectively. Tight-target consistency is weak, and references essentially equal to the best pilot endpoint can make certification sensitive to timing and roundoff. Of the nine scene/target cells both methods hit3/3, PRISM is faster in five and Caspar in four. The conditional speed intervals below include parity, and removing a family can reverse the aggregate direction. These results do not establish a general average speed advantage.", '', "The largest problem, Final13682, favors Caspar:8/9 certified hits versus PRISM0/9. PRISM's median tight-run endpoint cost is about11.8% higher. Caspar's one tight miss is only about2e-14 relative above the reference. Ladybug49's PRISM tight misses are also tiny in objective. Zero PRISM restarts occurred, so this batch evaluates fixed-five behavior and does not demonstrate an active recovery benefit.", '', '[Performance profiles](figures/expanded_caspar_profiles.png) · [PDF](figures/expanded_caspar_profiles.pdf)', '']
 i=lines.index('## Protocol');lines[i:i]=interpretation
 overview=['## Results by target level','','| Level | PRISM certified hits | Caspar certified hits | PRISM wins | Caspar wins | Ties | Unresolved |','|---|---:|---:|---:|---:|---:|---:|']
 for level,z in summary['by_level'].items():
  w=z['winners'];overview.append(f"| {level} | {z['hits']['restart']}/36 | {z['hits']['caspar64']}/36 | {w.get('PRISM',0)} | {w.get('Caspar',0)} | {w.get('tie',0)} | {w.get('unresolved',0)} |")
 overview+=['','## Scene family summary','','Wins are scene/target cells, combining speed when both consistently hit and reliability otherwise. Related problem variants within a family are not independent recordings.','','| Family | Problems | PRISM wins | Caspar wins | Ties | Unresolved |','|---|---:|---:|---:|---:|---:|']
 for family,z in summary['by_family'].items():
  w=z['winners'];overview.append(f"| {family} | {z['scenes']} | {w.get('PRISM',0)} | {w.get('Caspar',0)} | {w.get('tie',0)} | {w.get('unresolved',0)} |")
 overview+=['']
 i=lines.index('## All time-to-quality results');lines[i:i]=overview
 for x in cells:
  p,c=x['arms'].values();fmt=lambda z:f"{z['hits']}/3; {z['crossing']:.3f}" if z['crossing'] is not None else f"{z['hits']}/3; —"
  ratio=x['caspar_over_prism'];verdict=x['winner']
  if ratio is not None and verdict!='tie':verdict+=f" {max(ratio,1/ratio):.2f}× as fast"
  elif ratio is None and verdict in ['PRISM','Caspar']:verdict+=' (reliability)'
  lines.append(f"| {x['scene']} | {x['level']} / {x['target']:.10g} | {fmt(p)} | {fmt(c)} | {verdict} |")
 lines+=['','## Size of target misses','','The frozen PRISM hook certifies only objective <= target*(1-1e-8), an inward rounding safety margin. Caspar uses its nominal native threshold followed by the CPU endpoint check. This conservative asymmetry can matter for tight references essentially equal to a calibration endpoint. A PRISM state can meet the nominal CPU target without emitting a target-stop event; such a run remains an uncertified miss here. Do not interpret these borderline misses as objective inferiority or claim the stopping event is the mathematical earliest nominal threshold crossing. No solver hooks or thresholds were changed after outcomes.','','A strict miss can be numerically tiny or caused by a boundary crossing just after the cap. Report its size before interpreting it as a quality failure. Gaps below use missed runs only. Positive means worse objective than target; negative means the returned endpoint meets the nominal target without a certified stopping event, for example because of the safety margin. No late crossing event was recorded in this batch.','','| Scene | Level | Arm | Hits | Median gap among missed runs |','|---|---|---|---:|---:|']
 for x in cells:
  for arm,v in x['arms'].items():
   if v['hits']<3:
    missed=[z['cost'] for z in groups[x['scene'],x['level'],arm] if z['status']=='ok' and not z['hit']]
    gap='unavailable' if not missed else f"{100*(statistics.median(missed)/x['target']-1):.6g}%"
    lines.append(f"| {x['scene']} | {x['level']} | {arm} | {v['hits']}/3 | {gap} |")
 lines+=['','## How stable is the signal?','','The following ratios include **only scenes where both arms hit all three times at the specified level**; censored scenes are excluded, so these cannot replace the reliability table. Each eligible scene has equal weight. A ratio greater than1 favors PRISM. The 95% bootstrap ranges resample scene-level log ratios10,000 times (fixed seed). They describe this selected sample; they are not population confidence guarantees because scenes are convenience-selected and related within families. N3 also leaves timing uncertainty.','','| Target | Eligible scenes /12 | Geometric mean Caspar/PRISM | Descriptive bootstrap range | Leave-one-family-out range |','|---|---:|---:|---:|---:|']
 for level,s in stability.items():
  lo,hi=s['bootstrap_scene_interval95'];v=list(s['leave_one_family_out'].values());lr=f'{min(v):.2f}–{max(v):.2f}' if v else '—'
  lines.append(f"| {level} | {s['eligible_scenes']}/12 | {s['geomean_caspar_over_prism']:.2f} | {lo:.2f}–{hi:.2f} | {lr} |")
 lines+=['','Family sensitivity excludes each eligible family in turn, not each repeat. If this changes the direction or ranges include1, the aggregate speed verdict remains fragile. Even consistent sample results do not establish performance on unrelated capture domains. A solver comparison also does not isolate the contribution of multi-shift from point repair, damping policy, and other configuration differences.','','## Costs, variability, and process wall','','Median endpoint costs and measured wall seconds include valid runs even when targets are missed. Crossing ranges include successful repeats only and must be read with the hit counts above.','','| Scene | Level | PRISM cost | Caspar cost | PRISM crossing range | Caspar crossing range | PRISM wall | Caspar wall |','|---|---|---:|---:|---:|---:|---:|---:|']
 fmt=lambda v:'—' if v is None else f'{v:.3f}'
 rngfmt=lambda v:'—' if v is None else f'{v[0]:.3f}–{v[1]:.3f}'
 for x in cells:
  p,c=x['arms'].values();lines.append(f"| {x['scene']} | {x['level']} | {fmt(p['cost'])} | {fmt(c['cost'])} | {rngfmt(p['crossing_range'])} | {rngfmt(c['crossing_range'])} | {fmt(p['wall'])} | {fmt(c['wall'])} |")
 lines+=['','Caspar graph setup is outside its native clock; PRISM includes solver-local setup. Process wall also has different diagnostic boundaries: Caspar includes in-driver CPU checks while PRISM independent CPU endpoint audits occur afterward. Native ratios are not fully normalized end-to-end pipeline speedups. All abandoned PRISM restart native work is charged. Native caps can overrun at in-flight solver boundaries; hits still require crossings within cap.','',f"PRISM measurement restarts: {summary['restarts']}/108. Valid measurement stages: {proof['measurement_stages']}; calibration stages: {proof['calibration_stages']}. Measurement native time: {summary['native_seconds']:.3f}s; calibration native time: {summary['calibration_native_seconds']:.3f}s; measurement process wall: {summary['process_wall']:.3f}s. These totals omit outer orchestration and independent audit overhead.",'','## Failures and verification','']
 failures=[x for x in cal+rows if x['status']!='ok']
 if failures:
  for x in failures:lines.append(f"- `{x['name']}`: {x['status']}; artifacts `{x.get('artifact_dir','see calibration')}`.")
 else:lines.append('All calibration and measurement pipelines returned valid, independently audited states.')
 lines +=['',f"Checked {manifests} binary/data manifests against frozen hashes, unchanged PRISM source snapshot, retained best-state hashes, cumulative stage time, and Caspar accepted-cost monotonicity. Maximum endpoint relative audit discrepancy {proof['max_endpoint_audit_error']:.3g}; maximum Caspar initial/reference discrepancy {proof['max_caspar_initial_gap']:.3g}; maximum Caspar native/CPU endpoint gap {proof['max_caspar_native_cpu_gap']:.3g}. All11 older jobs remain paused.",'','Before valid calibration, target0 was rejected by both drivers before optimization. Those invalid harness invocations are retained in `invalid-zero-target/`; the corrected effectively unreachable positive target1e-100 preserves the intended full-budget calibration. No valid solve outcome informed that correction.','','CPU preparation uses an optional content-addressed cache of the original observations and initial score. Creation checks bit-for-bit array equality; reloads check full input, array, and scorer-source hashes. Endpoint scoring is unchanged and cache work is outside both reported timing windows. The first six uncached measurements are retained; the archived original plan differs only by the added cache-location field. No targets or solver settings changed.','', 'Reproduce with `python3 bench/expanded_caspar_screen.py`, then `python3 bench/summarize_expanded_caspar.py /workspace/prism-caspar-expanded`. Existing records are retained on resume. Artifacts include `PROTOCOL.md`, `protocol.json`, `calibration.json`, `measurement-plan.json`, `results.json`, `summary.json`, `verification.json`, and all per-run traces/states/manifests.']
 pathlib.Path('/workspace/prism-ba/docs/expanded_caspar_results.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps(stability,indent=2))
if __name__=='__main__':main()
