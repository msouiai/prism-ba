#!/usr/bin/env python3
"""Re-audit all mixed-storage research endpoints, hashes, TR acceptance and drift."""
import pathlib,json,re,csv,math
from profile_iterations import sha
from cached_benchmark_input import load_input
from audit_prism_state import audit
ROOT=pathlib.Path('/workspace/prism-tr-mixed')
def main():
 cache={};records=[];accepted=0;drifts=[];rho_errors=[]
 expected={'audit':6,'timing':24,'point-double-timing':18,'full-audit':4,'extra-scenes':6}
 for directory,n in expected.items():
  folder=ROOT/directory;rows=json.loads((folder/'results.json').read_text());assert len(rows)==n
  protocol=json.loads((folder/'protocol.json').read_text())
  for r in rows:
   assert r['returncode']==0,r
   name=f'{r["scene"]}-{r["arm"]}'+(f'-{r["rep"]}' if 'rep' in r else '');stem=folder/name
   m=json.loads(stem.with_suffix('.manifest.json').read_text());assert m['binary_sha256']==protocol['bins'][r['arm']]
   state=stem.with_suffix('.state');assert sha(state)==r['state_sha256']
   if r['scene'] not in cache:cache[r['scene']]=load_input(pathlib.Path('/workspace/bal')/(r['scene']+'.txt'),'/workspace/prism-caspar-expanded/cpu-cache')
   dh,(dims,obs),initial=cache[r['scene']];assert dh==m['input_sha256']
   cost=audit(state,dims,obs);assert abs(cost-r['cost'])<1e-12*max(1,cost);assert r['audit_error']<1e-7
   if directory=='extra-scenes':target=r['target'];cap=r['cap']
   else:target=protocol['scenes'][r['scene']]['nominal']*(1-1e-8);cap=protocol['scenes'][r['scene']]['cap']
   assert r['hit']==(r['crossing'] is not None and r['crossing']<=cap and cost<=target)
   log=stem.with_suffix('.log').read_text();trace=None
   if stem.with_suffix('.csv').exists():
    with stem.with_suffix('.csv').open() as f:trace=list(csv.DictReader(l for l in f if not l.startswith('#')))
    assert abs(float(trace[0]['cost'])-initial)<1e-7*initial
    assert abs(float(trace[-1]['cost'])-cost)<1e-7*max(1,cost)
    assert all(float(b['cost'])<=float(a['cost'])*(1+1e-12) for a,b in zip(trace,trace[1:]))
   for line in log.splitlines():
    if line.startswith('CAMERA_TR o='):
     v={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)}
     if v['accept']:
      assert v['rho']>=.1 and v['prediction']>0 and v['norm']<=v['radius']*(1+1e-8);accepted+=1
      if trace:
       i=int(v['o']);actual=float(trace[i]['cost'])-float(trace[i+1]['cost']);e=abs(actual/v['prediction']-v['rho'])/max(1,abs(v['rho']));assert e<1e-7;rho_errors.append(e)
   drift=[float(v) for v in re.findall(r'^TR_RECURRENCE .*?error=(\S+)',log,re.M)];assert all(v<=1e-7 for v in drift);drifts+=drift
   records.append(dict(name=directory+'/'+name,cost=cost,audit_error=r['audit_error'],seconds=r['seconds'],hit=r['hit'],state_sha256=sha(state)))
 # Profiling endpoints are correctness checks, never benchmark samples.
 profile=[]
 for state in sorted(ROOT.glob('*.state')):
  scene='final-13682' if state.name.startswith('final-13682-') else 'final-1936'
  if scene not in cache:cache[scene]=load_input(pathlib.Path('/workspace/bal')/(scene+'.txt'),'/workspace/prism-caspar-expanded/cpu-cache')
  dh,(dims,obs),initial=cache[scene];cost=audit(state,dims,obs);log=state.with_suffix('.log').read_text()
  m=re.search(r'CHECK final_score=(\S+)',log) or re.search(r'RESULT .*?final_cost=(\S+)',log);assert m
  e=abs(cost-float(m[1]))/max(1,cost);assert math.isfinite(cost) and e<1e-7;profile.append(dict(name=state.stem,cost=cost,audit_error=e,state_sha256=sha(state)))
 assert len(profile)==5
 for variant in ['storage','point-double']:
  manifest=json.loads((ROOT/variant/'mixed-manifest.json').read_text());assert sha(ROOT/variant/'prism-tr')==manifest['binary_sha256'];assert sha(ROOT/variant/'source.cu')==manifest['source_sha256'];assert (ROOT/variant/'source.cu').read_bytes()==(ROOT/('reproduce-'+variant)/'source.cu').read_bytes()
 paused=json.loads(pathlib.Path('/workspace/prism-block-error/paused-verified.json').read_text())
 for p in paused:
  fields=pathlib.Path('/proc',str(p['pid']),'stat').read_text().split();assert fields[2]=='T' and fields[21]==p['start_ticks']
 result=dict(endpoints=len(records)+len(profile),experiment_endpoints=len(records),profile_endpoints=len(profile),max_audit_error=max(r['audit_error'] for r in records+profile),accepted_tr_checks=accepted,rho_identity_checks=len(rho_errors),max_rho_identity_error=max(rho_errors),curvature_checks=len(drifts),max_curvature_error=max(drifts),native_experiment_seconds=sum(r['seconds'] for r in records),paused_jobs_verified=len(paused),records=records,profiles=profile)
 (ROOT/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ['records','profiles']},indent=2))
if __name__=='__main__':main()
