#!/usr/bin/env python3
"""Independent endpoint and numerical checks for bounded CG stopping research."""
import pathlib,json,re,csv,math,argparse
from cached_benchmark_input import load_input
from audit_prism_state import audit
from profile_iterations import sha
ROOT=pathlib.Path('/workspace/prism-tr-cg-stop')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--groups',nargs='+',required=True);a=ap.parse_args();cache={};records=[];failures=[];accepted=0;curvature=[];projected=[];stops=0;model_discards=0
 for group in a.groups:
  folder=ROOT/group;protocol=json.loads((folder/'protocol.json').read_text());rows=json.loads((folder/'results.json').read_text());assert len(rows)==len(protocol['jobs'])
  for r in rows:
   stem=folder/f'{r["scene"]}-{r["arm"]}-{r["rep"]}';m=json.loads(stem.with_suffix('.manifest.json').read_text());assert m['binary_sha256']==protocol['bins'][r['arm']]
   if r['returncode']:
    failures.append(dict(group=group,scene=r['scene'],arm=r['arm'],returncode=r['returncode'],process_wall=r['process_wall'],stderr=stem.with_suffix('.stderr').read_text()[-600:]));assert not r['hit'];continue
   scene=r['scene']
   if scene not in cache:cache[scene]=load_input(pathlib.Path('/workspace/bal')/(scene+'.txt'),'/workspace/prism-caspar-expanded/cpu-cache')
   dh,(dims,obs),initial=cache[scene];assert dh==m['input_sha256'];state=stem.with_suffix('.state');assert sha(state)==r['state_sha256'];cost=audit(state,dims,obs);assert math.isfinite(cost) and abs(cost-r['cost'])<=1e-12*max(1,cost)
   nominal=protocol['scenes'][scene]['nominal'];cap=protocol['scenes'][scene]['cap'];assert r['hit']==(r['crossing'] is not None and r['crossing']<=cap and cost<=nominal*(1-1e-8))
   log=stem.with_suffix('.log').read_text();reported=float(re.search(r'RESULT .*?final_cost=(\S+)',log)[1]);error=abs(cost-reported)/max(1,cost);assert error<1e-7
   with stem.with_suffix('.csv').open() as f:trace=list(csv.DictReader(l for l in f if not l.startswith('#')))
   assert abs(float(trace[0]['cost'])-initial)<=1e-7*initial;assert abs(float(trace[-1]['cost'])-cost)<=1e-7*max(1,cost)
   assert all(float(b['cost'])<=float(a['cost'])*(1+1e-12) for a,b in zip(trace,trace[1:]))
   for line in log.splitlines():
    if line.startswith('CAMERA_TR o='):
     v={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)}
     if v['accept']:
      assert v['rho']>=.1 and v['prediction']>0 and v['norm']<=v['radius']*(1+1e-8);accepted+=1;i=int(v['o']);actual=float(trace[i]['cost'])-float(trace[i+1]['cost']);expected=v['rho']*v['prediction'];csv_roundoff=1.1e-10+4*math.ulp(float(trace[i]['cost']))+4*math.ulp(float(trace[i+1]['cost']));assert abs(actual-expected)<=csv_roundoff+1e-7*abs(expected)
    if line.startswith('CG_PROJECTION '):
     v={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)};projected.append(v['model_error']);stops+=int(v['stop']);model_discards+=int(v['model_error']>1e-7)
     if v['stop']:assert v['model_error']<=1e-7 and v['norm']<=v['radius']*(1+1e-8)
   curvature.extend(float(x) for x in re.findall(r'^TR_RECURRENCE .*?error=(\S+)',log,re.M));assert all(x<=1e-7 for x in curvature)
   records.append(dict(group=group,name=stem.name,seconds=r['seconds'],cost=cost,audit_error=error,hit=r['hit'],state_sha256=sha(state)))
 # The four-arm largest-scene screen uses a separately frozen protocol.
 folder=ROOT/'large';protocol=json.loads((folder/'protocol.json').read_text());large=json.loads((folder/'results.json').read_text());assert len(large)==4
 for r in large:
  assert r['returncode']==0;scene=r['scene'];stem=folder/(scene+'-'+r['arm']);m=json.loads(stem.with_suffix('.manifest.json').read_text());assert m['binary_sha256']==protocol['bins'][r['arm']]
  if scene not in cache:cache[scene]=load_input(pathlib.Path('/workspace/bal')/(scene+'.txt'),'/workspace/prism-caspar-expanded/cpu-cache')
  dh,(dims,obs),initial=cache[scene];assert dh==m['input_sha256'];state=stem.with_suffix('.state');assert sha(state)==r['state_sha256'];cost=audit(state,dims,obs);assert abs(cost-r['cost'])<1e-12*max(1,cost)
  assert r['hit']==(r['crossing'] is not None and r['crossing']<=r['cap'] and cost<=r['target'])
  log=stem.with_suffix('.log').read_text()
  if r['arm']=='caspar32':
   import struct
   threshold=struct.unpack('f',struct.pack('f',r['target']*.999))[0];t=min(float(t) for c,t in re.findall(r'TRACE iter=\d+ cost=(\S+) seconds=(\S+)',log) if float(c)<=threshold);assert t==r['crossing']
  records.append(dict(group='large',name=stem.name,seconds=r['seconds'],cost=cost,audit_error=r['audit_error'],hit=r['hit'],state_sha256=sha(state)))
 scene='final-13682'
 if scene not in cache:cache[scene]=load_input(pathlib.Path('/workspace/bal')/(scene+'.txt'),'/workspace/prism-caspar-expanded/cpu-cache')
 _,(dims,obs),_=cache[scene];cost=audit(ROOT/'capture.state',dims,obs);native=float(re.search(r'RESULT .*?final_cost=(\S+)',(ROOT/'capture.log').read_text())[1]);assert abs(cost-native)/cost<1e-7
 # Instrumented repeat confirms projected-model accuracy at the expensive solve.
 large_audit_cost=audit(ROOT/'large-audit.state',dims,obs);audit_log=(ROOT/'large-audit.log').read_text();reported=float(re.search(r'RESULT .*?final_cost=(\S+)',audit_log)[1]);assert abs(large_audit_cost-reported)/large_audit_cost<1e-7
 large_stops=[]
 for line in audit_log.splitlines():
  if line.startswith('CG_PROJECTION '):
   v={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)};assert v['model_error']<1e-7;projected.append(v['model_error'])
   if v['stop']:assert v['ratio']<=.05 and v['norm']<=v['radius']*(1+1e-8);large_stops.append(dict(outer=int(v['o']),depth=int(v['depth']),ratio=v['ratio']))
 assert large_stops
 replay=[float(x) for x in re.findall(r'operator_error=(\S+)',(ROOT/'replay.log').read_text())];assert len(replay)==4 and max(replay)<1e-7
 paused=json.loads(pathlib.Path('/workspace/prism-block-error/paused-verified.json').read_text())
 for r in paused:
  f=pathlib.Path('/proc',str(r['pid']),'stat').read_text().split();assert f[2]=='T' and f[21]==r['start_ticks']
 result=dict(groups=a.groups,completed_endpoints=len(records),failed_runs=failures,accepted_checks=accepted,curvature_checks=len(curvature),max_curvature_error=max(curvature,default=0),projected_checks=len(projected),max_projected_error=max(projected,default=0),diagnostic_stops=stops,diagnostic_model_discards=model_discards,capture_cost=cost,large_audit_cost=large_audit_cost,large_audit_stops=large_stops,total_ba_endpoints=len(records)+2,replay_checks=len(replay),max_replay_error=max(replay),max_endpoint_error=max(r['audit_error'] for r in records),completed_native_seconds=sum(r['seconds'] for r in records),paused_jobs_verified=len(paused),records=records)
 (ROOT/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))
if __name__=='__main__':main()
