#!/usr/bin/env python3
"""Summarize audited experiment records, including failed and regressing arms."""
import pathlib,json,re,statistics
from build_tr_candidate import sha
ROOT=pathlib.Path('/workspace/prism-tr-fp32-products')
def main():
 report={'phases':{},'builds':{}}
 for variant in ['build','reliable','compensated']:
  p=ROOT/variant;m=json.loads((p/'stop-manifest.json').read_text());assert sha(p/'source.cu')==m['source_sha256'];assert sha(p/'prism-tr')==m['binary_sha256'];assert all(sha(p/'headers'/k)==v for k,v in m['headers_sha256'].items());report['builds'][variant]=m['binary_sha256']
 for phase in ['audit','reliable-audit','timing','large','compensated-audit']:
  rows=json.loads((ROOT/phase/'results.json').read_text());completed=[r for r in rows if r['returncode']==0];assert all(r['audit_error']<1e-7 for r in completed)
  for r in rows:
   stem=(r['scene']+'-'+r['arm']+(('-'+str(r['rep'])) if 'rep' in r else ''));log=(ROOT/phase/(stem+'.log')).read_text()
   r['fallbacks']=len(re.findall(r'^FP32_FALLBACK ',log,re.M))
   gaps=[float(v) for v in re.findall(r'^FP32_RESIDUAL .*?gap_relative=(\S+)',log,re.M)];r['residual_checks_logged']=len(gaps);r['max_residual_gap_logged']=max(gaps,default=None)
   projections=[dict((k,float(v)) for k,v in re.findall(r'(\w+)=([^ ]+)',line)) for line in log.splitlines() if line.startswith('CG_PROJECTION ')]
   r['projections_logged']=len(projections);r['projections_verified_logged']=sum(v['model_error']<=1e-7 for v in projections)
  report['phases'][phase]={'completed':len(completed),'failed':len(rows)-len(completed),'hits':sum(r['hit'] for r in rows),'native_seconds_completed':sum(r['seconds'] for r in completed),'rows':rows}
 summary=[];rows=report['phases']['timing']['rows']
 for scene in sorted(set(r['scene'] for r in rows)):
  arms={a:[r for r in rows if r['scene']==scene and r['arm']==a] for a in ['double','storage']}
  assert all(r['hit'] for rr in arms.values() for r in rr)
  times={a:statistics.median(r['crossing'] for r in rr) for a,rr in arms.items()}
  summary.append(dict(scene=scene,control=times['double'],candidate=times['storage'],change_percent=100*(times['storage']/times['double']-1),paired_wins=sum(c['crossing']<b['crossing'] for b,c in zip(arms['double'],arms['storage'])),runs=len(arms['double'])))
 report['timing_summary']=summary
 if (ROOT/'profile/verification.json').exists():report['profile']=json.loads((ROOT/'profile/verification.json').read_text())
 report['product_test']=json.loads((ROOT/'compensated/product-test.json').read_text())
 (ROOT/'verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(summary,indent=2));print('Completed',sum(p['completed'] for p in report['phases'].values()),'failed',sum(p['failed'] for p in report['phases'].values()))
if __name__=='__main__':main()
