#!/usr/bin/env python3
import pathlib,re,json,statistics,math,sys
ROOT=pathlib.Path('/workspace/prism-schur-eta2')
def spread(values):
 return dict(median=statistics.median(values),minimum=min(values),maximum=max(values))
fixed=[]
for d in sorted(ROOT.iterdir()):
 if not d.is_dir() or not (d/'fixed.log').exists():continue
 rows=[]
 for line in (d/'fixed.log').read_text().splitlines():
  if line.startswith('FIXED '):rows.append({k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)})
 assert len(rows)==18
 for tol in sorted({r['tolerance'] for r in rows}):
  for mode in [1,2,3]:
   group=[r for r in rows if r['tolerance']==tol and r['mode']==mode];assert len(group)==3
   fixed.append(dict(scene=d.name,tolerance=tol,mode={1:'Hcc',2:'Schur legacy',3:'Schur Gram'}[mode],n=3,metrics={k:spread([r[k] for r in group]) for k in group[0] if k not in ['rep','mode','tolerance']}))
(ROOT/'fixed-summary.json').write_text(json.dumps(fixed,indent=2))
print('FIXED N3 native-eta totals(ms), including setup:')
for row in fixed:
 if row['tolerance']==.5:print(row['scene'],row['mode'],row['metrics']['total_ms'], 'iters',row['metrics']['iterations']['median'])
p=ROOT/('targets-upgrade' if '--upgrade' in sys.argv else 'targets')
if not (p/('final-1936-upgrade-2.log' if '--upgrade' in sys.argv else 'final-1936-gram-2.log')).exists():exit()
protocol=json.loads((p/'protocol.json').read_text());records=[]
for scene,target in protocol['targets'].items():
 for arm in protocol['arms']:
  for rep in range(3):
   path=p/f'{scene}-{arm}-{rep}.log';s=path.read_text()
   hit=re.search(r'TARGET reached outer=(\d+) seconds=([\d.e+-]+) cost=([\d.e+-]+)',s)
   result=re.search(r'RESULT algo=\S+ iters=(\d+) final_cost=([\d.e+-]+) solve_seconds=([\d.e+-]+)',s)
   counts=re.search(r'MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)',s)
   assert result and counts
   if hit:assert float(hit[3])<=target and float(result[2])<=target
   records.append(dict(scene=scene,arm=arm,rep=rep,hit=bool(hit),target_seconds=float(hit[2]) if hit else None,final_cost=float(result[2]),native_seconds=float(result[3]),outers=int(result[1]),accepts=int(counts[1]),rejects=int(counts[2]),matvecs=int(counts[3])))
parity=[]
for label in ['frozen','off']:
 s=(p/f'parity-{label}.log').read_text();m=re.search(r'RESULT algo=\S+ iters=(\d+) final_cost=([\d.e+-]+)',s);assert m;parity.append(float(m[2]))
assert abs(parity[0]-parity[1])<=1e-8*max(parity)
assert 'ERROR SUMMARY: 0 errors' in (p/'memcheck.log').read_text()
summaries=[]
for scene in protocol['targets']:
 for arm in protocol['arms']:
  rows=[r for r in records if r['scene']==scene and r['arm']==arm]
  v={k:spread([r[k] for r in rows]) for k in ['final_cost','outers','rejects','matvecs','native_seconds']}
  hits=[r['target_seconds'] for r in rows if r['hit']]
  if hits:v['target_seconds']=spread(hits)
  summaries.append(dict(scene=scene,arm=arm,hits=len(hits),metrics=v))
  print('TARGET',scene,arm,len(hits),v)
(p/'summary.json').write_text(json.dumps(dict(records=records,summaries=summaries,off_parity_costs=parity,memcheck_errors=0),indent=2))
