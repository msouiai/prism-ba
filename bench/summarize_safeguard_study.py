#!/usr/bin/env python3
import pathlib,json,re,math,statistics,csv,io
from build_tr_candidate import sha
ROOT=pathlib.Path('/workspace/prism-tr-safeguard')
def fields(line):return {k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)}
def main():
 report={'builds':{},'phases':{},'summaries':{},'block_checks':[],'pair_checks':[]}
 for variant in ['pair','factored']:
  d=ROOT/variant;m=json.loads((d/'stop-manifest.json').read_text());assert sha(d/'source.cu')==m['source_sha256'] and sha(d/'prism-tr')==m['binary_sha256'];assert all(sha(d/'headers'/k)==v for k,v in m['headers_sha256'].items());report['builds'][variant]=m
 for phase in ['small-audit','pair-timing','factored-audit','factored-timing','large']:
  rows=json.loads((ROOT/phase/'results.json').read_text())
  for r in rows:
   assert r['returncode']==0 and math.isfinite(r['cost']) and r['audit_error']<1e-7
   stem=r['scene']+'-'+r['arm']+('-'+str(r['rep']) if 'rep' in r else '');s=(ROOT/phase/(stem+'.log')).read_text();counts=re.search('accepts=(\\d+) rejects=(\\d+) total_matvecs=(\\d+)',s)
   if counts:r.update(accepts=int(counts[1]),rejects=int(counts[2]),matvecs=int(counts[3]))
   r['accepted_checks']=0
   for line in s.splitlines():
    if line.startswith('CAMERA_TR o='):
     v=fields(line)
     if v['accept']:assert v['rho']>=.1 and v['prediction']>0 and math.isfinite(v['prediction']) and v['norm']<=v['radius']*(1+1e-8);r['accepted_checks']+=1
    if line.startswith('BLOCK_MODEL '):report['block_checks'].append(dict(phase=phase,scene=r['scene'],**fields(line)))
    if line.startswith('PAIR_SAFE '):
     v=fields(line)
     if v['use']:assert v['eligible'] and v['safe']<v['raw'] and v['prediction']>0 and v['slope']<0 and v['norm']<=v['radius']*(1+1e-8)
     report['pair_checks'].append(dict(phase=phase,scene=r['scene'],**v))
  report['phases'][phase]=rows
  if phase.endswith('timing'):
   summary=[]
   for scene in sorted(set(r['scene'] for r in rows)):
    arms={a:sorted((r for r in rows if r['scene']==scene and r['arm']==a),key=lambda r:r['rep']) for a in ['double','storage']};assert all(r['hit'] for rr in arms.values() for r in rr)
    a,b=[statistics.median(r['crossing'] for r in arms[k]) for k in ['double','storage']];summary.append(dict(scene=scene,control=a,candidate=b,change_percent=100*(b/a-1),paired_wins=sum(b['crossing']<a['crossing'] for a,b in zip(arms['double'],arms['storage'])),runs=3))
   report['summaries'][phase]=summary
 for line in (ROOT/'diagnostic/run.log').read_text().splitlines():
  if line.startswith('BLOCK_MODEL '):report['block_checks'].append(dict(phase='diagnostic',scene='final-13682',**fields(line)))
  if line.startswith('PAIR_SAFE '):report['pair_checks'].append(dict(phase='diagnostic',scene='final-13682',**fields(line)))
 report['diagnostic']=json.loads((ROOT/'diagnostic/result.json').read_text());report['pair_cpu_audits']=json.loads((ROOT/'diagnostic/cpu-pair/results.json').read_text());assert all(r['relative_error']<1e-7 for r in report['pair_cpu_audits']);report['derivative_test']=json.loads((ROOT/'derivative-test.json').read_text());report['derivative_test_mixed']=json.loads((ROOT/'derivative-test-mixed.json').read_text())
 if (ROOT/'factored-profile/result.json').exists():
  report['profile']=json.loads((ROOT/'factored-profile/result.json').read_text());s=(ROOT/'factored-profile/final-13682.kernels.csv').read_text();rows=list(csv.DictReader(io.StringIO(s[s.index('Time (%)'):])));report['profile_kernels']=[dict(name=r['Name'],seconds=int(r['Total Time (ns)'])/1e9,calls=int(r['Instances']),avg_ms=float(r['Avg (ns)'])/1e6) for r in rows if any(x in r['Name'] for x in ['MFAssemble','MFDirectFullModel','MFPointFactorObs','MFDiagK','MFRhsPrime'])]
 report['completed_ba_endpoints']=sum(len(rows) for rows in report['phases'].values())+1+('profile' in report)
 report['native_seconds']=sum(r['seconds'] for rows in report['phases'].values() for r in rows)+float(re.search('solve_seconds=(\\S+)',(ROOT/'diagnostic/run.log').read_text())[1])+report.get('profile',{}).get('seconds',0)
 (ROOT/'verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report['summaries'],indent=2));print('BA endpoints',report['completed_ba_endpoints'],'plus captured proposals',len(report['pair_cpu_audits']));print('native seconds',report['native_seconds'])
if __name__=='__main__':main()
