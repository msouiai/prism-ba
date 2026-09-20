#!/usr/bin/env python3
"""Verify and summarize reference-ranking and fixed Schur experiments."""
import pathlib,json,re,statistics,math
from build_tr_candidate import sha
ROOT=pathlib.Path('/workspace/prism-tr-reference')
def main():
 m=json.loads((ROOT/'rank/stop-manifest.json').read_text());assert sha(ROOT/'rank/source.cu')==m['source_sha256'];assert sha(ROOT/'rank/prism-tr')==m['binary_sha256'];assert all(sha(ROOT/'rank/headers'/k)==v for k,v in m['headers_sha256'].items())
 report=dict(build=m,phases={},fixed={},counters={'status':'blocked','reason':'ERR_NVGPUCTRPERM','log':str(ROOT/'fixed/counters-measured.log')})
 for phase in ['rank-audit','rank-timing','large']:
  rows=json.loads((ROOT/phase/'results.json').read_text())
  for r in rows:
   assert r['returncode']==0 and math.isfinite(r['cost']) and r['audit_error']<1e-7
   stem=r['scene']+'-'+r['arm']+('-'+str(r['rep']) if 'rep' in r else '');log=(ROOT/phase/(stem+'.log')).read_text()
   r['accepted_checks']=0
   for line in log.splitlines():
    if line.startswith('CAMERA_TR o='):
     v={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)}
     if v['accept']:
      assert all(math.isfinite(v[k]) for k in ['rho','prediction','norm','radius']) and v['rho']>=.1 and v['prediction']>0 and v['norm']<=v['radius']*(1+1e-8)
      r['accepted_checks']+=1
   r['fallbacks']=len(re.findall(r'^FP32_FALLBACK ',log,re.M));counts=re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)',log)
   if counts:r.update(accepts=int(counts[1]),rejects=int(counts[2]),matvecs=int(counts[3]))
   projections=[dict((k,float(v)) for k,v in re.findall(r'(\w+)=([^ ]+)',line)) for line in log.splitlines() if line.startswith('CG_PROJECTION ')]
   r['projected_proposals_logged']=len(projections);r['reduced_model_mismatches_logged']=sum(v['model_error']>1e-7 for v in projections)
   for v in projections:assert math.isfinite(v['prediction']) and v['norm']<=v['radius']*(1+1e-8)
  report['phases'][phase]=rows
 summaries=[]
 for phase in ['rank-timing']:
  rows=report['phases'][phase]
  for scene in sorted(set(r['scene'] for r in rows)):
   arms={a:sorted((r for r in rows if r['arm']==a and r['scene']==scene),key=lambda r:r['rep']) for a in ['double','storage']};assert all(r['hit'] for rr in arms.values() for r in rr)
   times={a:statistics.median(r['crossing'] for r in rr) for a,rr in arms.items()}
   summaries.append(dict(scene=scene,control=times['double'],candidate=times['storage'],change_percent=100*(times['storage']/times['double']-1),paired_wins=sum(c['crossing']<b['crossing'] for b,c in zip(arms['double'],arms['storage'])),runs=len(arms['double'])))
 report['timing_summary']=summaries
 for phase in ['fixed','fixed-staged','fixed-tuned']:
  m=json.loads((ROOT/phase/'manifest.json').read_text());assert all(sha(ROOT/phase/k)==v for k,v in m['files'].items())
  lines=(ROOT/phase/'results.log').read_text().splitlines();rows=[]
  for line in lines:
   if line.startswith('FIXED '):
    v={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)};assert v['error_over_b']<1e-7;rows.append(v)
  modes=[]
  for mode in sorted(set(r['mode'] for r in rows)):
   rr=[r for r in rows if r['mode']==mode];ratios=[r['pass1_ms']/next(b['pass1_ms'] for b in rows if b['depth']==r['depth'] and b['mode']==0) for r in rr]
   modes.append(dict(mode=int(mode),median_ms=statistics.median(r['pass1_ms'] for r in rr),median_ratio=statistics.median(ratios),max_operator_error=max(r['error_over_b'] for r in rr)))
  report['fixed'][phase]={'rows':rows,'summary':modes}
 report['completed_endpoints']=sum(len(rows) for rows in report['phases'].values());report['completed_native_seconds']=sum(r['seconds'] for rows in report['phases'].values() for r in rows)
 (ROOT/'verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(summaries,indent=2));print('endpoints',report['completed_endpoints'],'native seconds',report['completed_native_seconds']);print(json.dumps({k:v['summary'] for k,v in report['fixed'].items()},indent=2))
if __name__=='__main__':main()
