from pathlib import Path
import csv,json,math,hashlib,statistics
root=Path('/workspace/multishift_repro');out=root/'codex_evidence'
manifest=json.loads((out/'manifest.json').read_text());rows=list(csv.DictReader((root/'repro_codex.csv').open()))
assert len(rows)==60, f'Expected60 rows, got{len(rows)}'
assert list(rows[0])==['dataset','rep','final_cost','solve_seconds']
expected={(scene,str(rep)) for scene in manifest['datasets'] for rep in [1,2,3]}
assert {(r['dataset'],r['rep']) for r in rows}==expected
for r in rows:
 for key in ['final_cost','solve_seconds']:
  x=float(r[key]);assert math.isfinite(x) and x>0,(r,key)
assert hashlib.sha256((root/'oca_cuda').read_bytes()).hexdigest()==manifest['binary_sha256']
assert hashlib.sha256((root/'run_repro.sh').read_bytes()).hexdigest()==manifest['runner_sha256']
summary={}
for scene in manifest['datasets']:
 rr=[r for r in rows if r['dataset']==scene];costs=[float(r['final_cost']) for r in rr];secs=[float(r['solve_seconds']) for r in rr]
 summary[scene]={'n':len(rr),'final_cost_median':statistics.median(costs),'final_cost_min':min(costs),'final_cost_max':max(costs),'range_pct_of_median':100*(max(costs)-min(costs))/statistics.median(costs),'native_seconds_median':statistics.median(secs),'native_seconds_min':min(secs),'native_seconds_max':max(secs)}
result={'csv_sha256':hashlib.sha256((root/'repro_codex.csv').read_bytes()).hexdigest(),'rows':len(rows),'datasets':len(summary),'missing_or_nonfinite':0,'native_seconds_total':sum(float(r['solve_seconds']) for r in rows),'median_scene_cost_range_pct':statistics.median(s['range_pct_of_median'] for s in summary.values()),'scope':'same binary CLI configuration; not the published library path or a cross-host speed claim','summary':summary}
(out/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='summary'},indent=2))
for name in ['ladybug-49','dubrovnik-88','venice-52','final-4585']:print(name,json.dumps(summary[name]))
