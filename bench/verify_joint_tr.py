#!/usr/bin/env python3
import pathlib,json,re,csv
from profile_iterations import sha
from cached_benchmark_input import load_input
from audit_prism_state import audit
ROOT=pathlib.Path('/workspace/prism-joint-tr')
def main():
 cache={};rows=[];pred_errors=[];tr_checks=0
 for phase in ['joint','depth64','width_depth']:
  folder=ROOT/phase
  if not (folder/'results.json').exists():continue
  protocol=json.loads((folder/'protocol.json').read_text());assert sha(ROOT/'prism')==protocol['binary_sha256'];assert sha(ROOT/'source.cu')==protocol['source_sha256']
  for p,h in protocol['headers'].items():assert sha(p)==h
  rr=json.loads((folder/'results.json').read_text());assert len(rr)==(14 if phase=='joint' else 18)
  for r in rr:
   scene=r['scene'];stem=folder/(scene+'-mode'+str(r['mode'])+'-rep'+str(r['rep']) if phase=='joint' else scene+'-'+r['arm']+'-'+str(r['rep']))
   if scene not in cache:cache[scene]=load_input(pathlib.Path('/workspace/bal')/(scene+'.txt'),'/workspace/prism-caspar-expanded/cpu-cache')
   dh,(dims,obs),initial=cache[scene];assert dh==protocol['data_sha256'][scene]
   cost=audit(stem.with_suffix('.state'),dims,obs);assert abs(cost-r['cost'])<1e-10*max(1,cost)
   with stem.with_suffix('.csv').open() as f:trace=list(csv.DictReader(l for l in f if not l.startswith('#')))
   assert abs(float(trace[0]['cost'])-initial)<1e-7*initial
   assert abs(float(trace[-1]['cost'])-cost)<1e-7*cost
   assert all(float(b['cost'])<=float(a['cost'])*(1+1e-10) for a,b in zip(trace,trace[1:]))
   last={}
   for line in stem.with_suffix('.log').read_text().splitlines():
    if line.startswith(('CAMERA_TR o=','JOINT_ACCEPT','JOINT_TRIAL')):
     v={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)}
     if line.startswith('CAMERA_TR'):last=v
     else:
      if v['accept']:
       assert v['norm']<=v['radius']*(1+1e-8) and v['prediction']>0 and v['rho']>=.1;tr_checks+=1
       if line.startswith('JOINT_ACCEPT') and v['checked']:
        assert last['o']==v['o'];error=abs(last['prediction']-v['prediction'])/max(1,abs(v['prediction']));assert error<1e-7;pred_errors.append(error)
   rows.append(r)
 out=dict(endpoints=len(rows),native_seconds=sum(r['native'] for r in rows),process_seconds=sum(r['wall'] for r in rows),max_audit_error=max(r['audit_error'] for r in rows),joint_acceptance_checks=tr_checks,max_prediction_discrepancy=max(pred_errors))
 (ROOT/'verification.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
if __name__=='__main__':main()
