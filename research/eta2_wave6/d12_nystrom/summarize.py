#!/usr/bin/env python3
"""Parse D12 fixed logs and freeze the attribution decision."""
from __future__ import annotations
import hashlib,json,pathlib,re,statistics

HERE=pathlib.Path(__file__).resolve().parent
EV=HERE/'evidence'

def tokens(line):
    out={}
    for key,value in re.findall(r'(\w+)=([^ ]+)',line):
        try:out[key]=float(value) if any(c in value for c in '.eE') else int(value)
        except ValueError:out[key]=value
    return out

def parse(scene):
    path=EV/f'{scene}.log'
    rows=[tokens(x) for x in path.read_text().splitlines() if x.startswith('NYSTROM ')]
    groups={}
    for row in rows:groups.setdefault((row['mode'],row['requested_rank']),[]).append(row)
    summary={}
    for (mode,rank),group in groups.items():
        key=f'{mode}-r{rank}'
        summary[key]={k:statistics.median(r[k] for r in group) for k in
          ('iterations','solve_products','sketch_products','total_products','restarts','true_relative','total_ms','sketch_ms','preconditioner_ms','effective_rank','theta_min','theta_max','factor_residual')}
        summary[key].update(n=len(group),hits=sum(r['hit'] for r in group),triggered=sum(r['triggered'] for r in group),
                            time_range=[min(r['total_ms'] for r in group),max(r['total_ms'] for r in group)],
                            residual_range=[min(r['true_relative'] for r in group),max(r['true_relative'] for r in group)])
    return {'rows':rows,'summary':summary,'log_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

result={s:parse(s) for s in ('muell-gba146','ladybug-598','final-1936')}
mu=result['muell-gba146']['summary'];base=mu['oracle-r0'];restart=mu['dispatch8-r0']
rank_gates={}
for rank in (4,8,16):
    arm=mu[f'dispatch8-r{rank}']
    rank_gates[str(rank)]={
      'all_hit':arm['hits']==3,
      'time_vs_uninterrupted':arm['total_ms']/base['total_ms'],
      'median_products':arm['total_products'],
      'time_vs_restart_only':arm['total_ms']/restart['total_ms'],
      'same_solve_products_as_restart':arm['solve_products']==restart['solve_products'],
      'nystrom_attribution_pass':arm['total_ms']<.9*restart['total_ms'] or arm['solve_products']<restart['solve_products']}
result['gates']={
 'baseline_iterations_match':base['iterations']==41,
 'baseline_residual_abs_delta':abs(base['true_relative']-0.49729670082734323),
 'restart_signal_time_ratio':restart['total_ms']/base['total_ms'],
 'restart_signal_product_reduction':1-restart['total_products']/base['total_products'],
 'shallow_dispatches_inactive':all(result[s]['summary'][f'dispatch8-r{r}']['triggered']==0 for s in ('ladybug-598','final-1936') for r in (0,4,8,16)),
 'rank_gates':rank_gates,
 'nystrom_promoted':False,
 'restart_followup_earned':restart['total_ms']<.9*base['total_ms'] and restart['total_products']<.7*base['total_products']}
result['provenance']={
 'build_manifest':json.loads((EV/'build_manifest.json').read_text()),
 'run_manifest':json.loads((EV/'run_manifest.json').read_text()),
 'sources':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
   [HERE/'nystrom_fixed.cu',HERE/'build.py',HERE/'run.py',pathlib.Path(__file__),HERE.parent/'D12_NYSTROM_PROTOCOL.md']}}
(HERE.parent/'d12-nystrom-results.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps(result['gates'],indent=2))
