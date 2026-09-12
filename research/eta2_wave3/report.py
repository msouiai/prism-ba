"""Compact wave-3 tables, without pooling independent cohorts."""
from pathlib import Path
import csv,json,math,statistics
P=Path(__file__).resolve().parent
def median(x):return statistics.median(x)
def fmt(x):return '—' if x is None else f'{x:.4g}'
def load(stage):
 p=P/(stage+'-results.json');return json.loads(p.read_text()) if p.exists() else []
def comparisons(rows):
 out=[]
 for arm in sorted({r['arm'] for r in rows}-{'off'}):
  values=[]
  for cell in sorted({r['cell'] for r in rows}):
   a=[r for r in rows if r['arm']==arm and r['cell']==cell];b=[r for r in rows if r['arm']=='off' and r['cell']==cell]
   if len(a)!=3 or len(b)!=3 or not all(r['hit'] for r in a+b):continue
   av=[r['target_seconds'] for r in a];bv=[r['target_seconds'] for r in b]
   kind='faster' if max(av)<min(bv) else ('slower' if min(av)>max(bv) else 'overlap')
   values.append(dict(cell=cell,ratio=median(av)/median(bv),kind=kind,variant=av,control=bv))
  if len(values)==9:out.append(dict(arm=arm,ratio=math.exp(sum(math.log(x['ratio']) for x in values)/9),
    faster=sum(x['kind']=='faster' for x in values),slower=sum(x['kind']=='slower' for x in values),overlap=sum(x['kind']=='overlap' for x in values),cells=values))
 return out
def main():
 lines=['# Wave-3 numerical ledger','',
 'Frozen Eta2 is the control. Fresh cohorts remain separate; hit counts are observed samples. Native times include the intervention and trace overhead. N=3 disjoint ranges are descriptive, not confidence intervals.','']
 summary={};allrows=[]
 for stage in ['compatibility','locality','tails','opening','practical','opening-cap','opening-cap-practical','confirmation']:
  rows=load(stage)
  if not rows:continue
  allrows+=rows;lines += ['## '+stage,'','| Scene/cell | Arm | Hits | Median endpoint | Hit median s | Hit range s | Rejects | PCG/outer | Retry wall % |','|---|---|---:|---:|---:|---|---:|---:|---:|']
  groups=[]
  for cell,arm in sorted({(r.get('cell',r['scene']),r['arm']) for r in rows}):
   rr=[r for r in rows if r.get('cell',r['scene'])==cell and r['arm']==arm];times=[r['target_seconds'] for r in rr if r['hit']]
   q=dict(cell=cell,arm=arm,n=len(rr),hits=len(times),cost=median(r['cost'] for r in rr),time=median(times) if times else None,
          time_range=[min(times),max(times)] if times else None,rejects=median(r['rejects'] for r in rr),
          pcg=median(r.get('pcg_per_outer',r['mean_matvecs_per_outer']) for r in rr),retry=median(r.get('retry_fraction_native',0) for r in rr))
   groups.append(q);lines.append(f"| {cell} | {arm} | {len(times)}/{len(rr)} | {q['cost']:.8g} | {fmt(q['time'])} | {'—' if not times else fmt(min(times))+'–'+fmt(max(times))} | {q['rejects']:g} | {q['pcg']:.3g} | {100*q['retry']:.3g} |")
  cc=comparisons(rows) if 'practical' in stage else []
  if cc:
   lines+=['','| Arm | Geometric mean time/control | Faster / slower / overlap |','|---|---:|---|']
   for c in cc:lines.append(f"| {c['arm']} | {c['ratio']:.5f} | {c['faster']} / {c['slower']} / {c['overlap']} |")
  lines+=[''];summary[stage]=dict(rows=len(rows),groups=groups,comparisons=cc)
 (P/'NUMBERS.md').write_text('\n'.join(lines).rstrip()+'\n');(P/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 fields=['stage','scene','cell','arm','rep','hit','cost','target','target_seconds','native_seconds','score_init','outers','rejects','matvecs','pcg_per_outer','retry_fraction_native','max_touched_fraction','source']
 with (P/'metrics.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\n');w.writeheader();w.writerows(allrows)
 print('REPORTED',len(allrows),'native rows')
if __name__=='__main__':main()
