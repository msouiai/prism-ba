#!/usr/bin/env python3
import argparse,collections,json,pathlib,statistics
p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,default=pathlib.Path('/workspace/prism-fixed-reuse'));a=p.parse_args();root=a.root
rows=json.loads((root/'results.json').read_text());cases=collections.defaultdict(list)
for r in rows:cases[r['scene'],int(r['snapshot'])].append(r)
assert 6<=len(cases)<=10 and len(rows)==9*len(cases)
result=[]
for (scene,snapshot),rs in cases.items():
 assert len(rs)==9
 case=dict(scene=scene,snapshot=snapshot,outer=rs[0]['outer'],source_depth=rs[0]['source_depth'],bucket=rs[0]['bucket'],tolerance=rs[0]['tolerance'],methods={})
 for method,name in [(0,'ordinary'),(1,'always'),(2,'selective')]:
  ms=[r for r in rs if r['method']==method];assert len(ms)==3
  item=dict(valid=sum(int(r['valid']) for r in ms),fallbacks=sum(int(r['fallback']) for r in ms))
  for key in ['charged','seconds','diagnostic_verify','capture','calls','narrow','projection','wide']:item[key]=statistics.median(r[key] for r in ms)
  item['charged_range']=[min(r['charged'] for r in ms),max(r['charged'] for r in ms)]
  item['max_residual']=max(r['residual'] for r in ms);item['decisions']=[r['decision'] for r in ms]
  assert all(r['valid']==0 or r['residual']<=r['tolerance']*(1+1e-8) for r in ms)
  case['methods'][name]=item
 for name in ['always','selective']:
  case['methods'][name]['ordinary_over_method']=case['methods']['ordinary']['charged']/case['methods'][name]['charged'] if case['methods']['ordinary']['valid']==case['methods'][name]['valid']==3 else None
 result.append(case)
eligible=[r for r in result if r['bucket']==1]
confirmation=len(eligible)>=3 and all(r['methods']['selective']['ordinary_over_method'] is not None and r['methods']['selective']['ordinary_over_method']>=1.05 for r in eligible)
summary=dict(cases=len(result),trials=len(rows),certified=sum(int(r['valid']) for r in rows),reported_trial_seconds=sum(r['seconds'] for r in rows),eligible_cases=len(eligible),eligible_wins=sum(r['methods']['selective']['ordinary_over_method'] is not None and r['methods']['selective']['ordinary_over_method']>=1.05 for r in eligible),confirmation_gate=confirmation,results=result)
(root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
