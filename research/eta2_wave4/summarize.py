"""Rebuild descriptive tables from all registered rows, without pooling cohorts."""
from pathlib import Path
import collections,json,math,statistics
P=Path(__file__).resolve().parent
def median(xs):return statistics.median(xs) if xs else None
def extent(xs):return [min(xs),max(xs)] if xs else None
def summary(rows):
 out=[]
 for scene,arm in sorted({(r['scene'],r['arm']) for r in rows}):
  rr=[r for r in rows if r['scene']==scene and r['arm']==arm];hits=[r for r in rr if r['hit']]
  row=dict(scene=scene,arm=arm,n=len(rr),valid=sum(r['valid'] for r in rr),hits=len(hits),cost_median=median([r['cost'] for r in rr]),cost_range=extent([r['cost'] for r in rr]),native_seconds_median=median([r['native_seconds'] for r in rr]),native_seconds_range=extent([r['native_seconds'] for r in rr]),conditional_native_seconds_median=median([r['native_seconds'] for r in hits]),conditional_native_seconds_range=extent([r['native_seconds'] for r in hits]),outers_median=median([r['outers'] for r in rr]),rejects_median=median([r['rejects'] for r in rr]),retry_fraction_median=median([r.get('retry_fraction_native',0) for r in rr]),pcg_per_outer_median=median([r.get('pcg_per_outer',0) for r in rr]),score_init_range=extent([r['score_init'] for r in rr]))
  if any('opening_completed' in r for r in rr):row.update(openings_completed=sum(r.get('opening_completed',False) for r in rr),accepted_sweep_counts=[r.get('opening_accepted_sweeps') for r in rr],opening_stop_counts=dict(collections.Counter(r.get('opening_stop','not_recorded') for r in rr)))
  out.append(row)
 return out
def main():
 result={};count=0
 for family in ['aside','o5','o2','o1']:
  rows=json.loads((P/f'{family}-tails-results.json').read_text());count+=len(rows);result[family]=summary(rows)
  for suffix in ['practical-results']:
   file=P/f'{family}-{suffix}.json'
   if file.exists():count+=len(json.loads(file.read_text()))
 result['scored_native_runs']=count
 (P/'RESULTS.json').write_text(json.dumps(result,indent=2)+'\n')
 lines=['# Wave 4 registered tail tables','','Each row has its own fresh control cohort. Conditional time includes all native','setup, opening and cleanup. A dash means no observed target success. N=5 is','screening; do not pool rows or interpret a difference of one hit as established','reliability. The original observations and full-L2 targets are unchanged.','']
 for family in ['aside','o5','o2','o1']:
  lines+=['## '+family,'','| Scene | Arm | Hits | Median final L2 | Conditional native seconds [range] | Median rejects |','|---|---|---:|---:|---:|---:|']
  for r in result[family]:
   tm=r['conditional_native_seconds_median'];span=r['conditional_native_seconds_range'];ts='—' if tm is None else f'{tm:.3f} [{span[0]:.3f}, {span[1]:.3f}]'
   lines.append(f"| {r['scene']} | {r['arm']} | {r['hits']}/{r['n']} | {r['cost_median']:,.2f} | {ts} | {r['rejects_median']:g} |")
  lines+=['']
 lines+=['O1 Final3068 rows with zero accepted opening sweeps are Eta2 fallback outcomes','after an incomplete numerical attempt; they are **not evidence for an O1 basin','effect**. See the report and per-sweep logs for the valid/incomplete distinction.','',f'Total scored native rows in these cohorts and gated panels: **{count}**.','Compatibility, memory checks, kernel tests and witness replays are separate.','']
 (P/'TABLES.md').write_text('\n'.join(lines));print('Scored native rows',count)
if __name__=='__main__':main()
