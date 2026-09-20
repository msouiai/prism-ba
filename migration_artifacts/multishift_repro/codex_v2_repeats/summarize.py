from pathlib import Path
import json,csv,statistics,math,hashlib
root=Path('/workspace/multishift_repro/codex_v2_repeats')
rows=list(csv.DictReader((root/'repro_codex_v2_n10.csv').open()))
assert len(rows)==30
assert {(r['dataset'],int(r['rep'])) for r in rows}=={(s,i) for s in ['dubrovnik-88','venice-52','final-3068'] for i in range(1,11)}
valid=[r for r in rows if r['returncode']=='0' and r['final_cost']!='NA' and math.isfinite(float(r['final_cost']))]
summary={}
for scene in ['dubrovnik-88','venice-52','final-3068']:
 rr=[r for r in valid if r['dataset']==scene];costs=[float(r['final_cost']) for r in rr];times=[float(r['solve_seconds']) for r in rr]
 median=statistics.median(costs)
 summary[scene]={'requested':10,'valid':len(rr),'cost_median':median,'cost_min':min(costs),'cost_max':max(costs),'range_pct_of_median':100*(max(costs)-min(costs))/median,'costs_sorted':sorted(costs),'sample_stdev':statistics.stdev(costs),'native_seconds_median':statistics.median(times),'native_seconds_min':min(times),'native_seconds_max':max(times),'outers_min':min(int(r['iters']) for r in rr),'outers_max':max(int(r['iters']) for r in rr),'rejects_min':min(int(r['rejects']) for r in rr),'rejects_max':max(int(r['rejects']) for r in rr)}
result={'records':len(rows),'valid':len(valid),'csv_sha256':hashlib.sha256((root/'repro_codex_v2_n10.csv').read_bytes()).hexdigest(),'native_seconds_total':sum(float(r['solve_seconds']) for r in valid),'scope':'Observed N10 distribution for V2 library-settings configuration; no universal noise floor or champion significance inferred','summary':summary}
(root/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
