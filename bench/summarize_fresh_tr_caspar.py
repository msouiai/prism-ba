#!/usr/bin/env python3
import pathlib,json,statistics
ROOT=pathlib.Path('/workspace/prism-fresh-tr-caspar')
def main():
 rows=json.loads((ROOT/'results.json').read_text());protocol=json.loads((ROOT/'protocol.json').read_text());scenes=list(dict.fromkeys(j['scene'] for j in protocol['jobs']));out={}
 for scene in scenes:
  cell={}
  for arm in ['tr','caspar64','caspar32']:
   rr=[r for r in rows if r['scene']==scene and r['arm']==arm]
   if not rr:continue
   hits=[r for r in rr if r.get('hit')];times=[r['crossing'] for r in hits];costs=[r['cost'] for r in rr if 'cost' in r]
   cell[arm]=dict(completed=len(rr),expected=3,hits=len(hits),median_crossing=statistics.median(times) if len(hits)==len(rr)==3 else None,successful_crossings=times,range=[min(times),max(times)] if times else None,median_endpoint=statistics.median(costs) if costs else None,median_over_target_fraction=statistics.median(r['endpoint_over_target_fraction'] for r in rr if 'endpoint_over_target_fraction' in r) if costs else None,uncertified_native_hits=sum(r.get('uncertified_native_hit',False) for r in rr),failures=sum(r['status']!='ok' for r in rr),max_native_cpu_gap=max((r.get('native_cpu_gap',0) for r in rr),default=0),max_initial_cpu_gap=max((r.get('initial_cpu_gap',0) for r in rr),default=0),median_native=statistics.median(r['seconds'] for r in rr if 'seconds' in r) if any('seconds' in r for r in rr) else None,median_process_wall=statistics.median(r['process_wall'] for r in rr))
  out[scene]=cell
 summary=dict(completed=len(rows),planned=len(protocol['jobs']),native_seconds=sum(r.get('seconds',0) for r in rows),process_seconds=sum(r['process_wall'] for r in rows),max_audit_error=max((r.get('audit_error',0) for r in rows),default=0),scenes=out)
 (ROOT/'summary.json').write_text(json.dumps(summary,indent=2));print('Completed',len(rows),'/',len(protocol['jobs']),'native',round(summary['native_seconds'],3))
 for scene,cell in out.items():
  print(scene)
  for arm,v in cell.items():print(' ',arm,f"{v['hits']}/{v['completed']}",'median',v['median_crossing'],'cost',v['median_endpoint'],'uncertified',v['uncertified_native_hits'],'fail',v['failures'])
if __name__=='__main__':main()
