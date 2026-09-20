#!/usr/bin/env python3
"""Independent rerun of endpoint certificates and paired-study integrity checks."""
import pathlib,json,re,csv,math
from profile_iterations import sha
from cached_benchmark_input import load_input
from audit_prism_state import audit
ROOT=pathlib.Path('/workspace/prism-fresh-tr-caspar')
def main():
 protocol=json.loads((ROOT/'protocol.json').read_text());rows=json.loads((ROOT/'results.json').read_text());assert len(rows)==45
 bins={'tr':pathlib.Path('/workspace/prism-tr-candidate/prism-tr'),'caspar64':pathlib.Path('/workspace/prism-caspar-current/caspar64'),'caspar32':pathlib.Path('/workspace/prism-caspar-current/caspar32')}
 for a,h in protocol['binary_sha256'].items():assert sha(bins[a])==h
 for p,h in protocol['tooling_sha256'].items():assert sha(p)==h,p
 proof=json.loads(pathlib.Path('/workspace/prism-caspar-current/precision-proof.json').read_text());assert proof['f32_binary_sha256']==protocol['binary_sha256']['caspar32'];assert proof['f32_driver_sha256']==sha('/workspace/prism-caspar-current/driver32.cc')
 expected={j['name']:j for j in protocol['jobs']};assert len(expected)==45 and {r['name'] for r in rows}==set(expected)
 cache={};errors=[];state_hashes={};failures=[];hits={a:0 for a in bins};false_hits={a:0 for a in bins};accepted_checks=0
 for row in rows:
  j=expected[row['name']];assert all(row[k]==v for k,v in j.items());stem=ROOT/j['name'];manifest=json.loads(stem.with_suffix('.manifest.json').read_text());assert manifest['job']==j
  assert manifest['binary_sha256']==protocol['binary_sha256'][j['arm']]
  assert not any(k in manifest['flags'] for k in ['OCA_PROFILE','OCA_LEARN_LOG','OCA_TR_RECURRENCE_AUDIT','OCA_JOINT_TR','OCA_RADIUS_TRACE'])
  if row['status']!='ok':failures.append(dict(name=row['name'],status=row['status']));assert not row['hit'];continue
  scene=j['scene']
  if scene not in cache:cache[scene]=load_input(pathlib.Path('/workspace/bal')/(scene+'.txt'),'/workspace/prism-caspar-expanded/cpu-cache')
  dh,(dims,obs),initial=cache[scene];assert dh==protocol['data_sha256'][scene]==manifest['data_sha256']
  cost=audit(stem.with_suffix('.state'),dims,obs);assert math.isfinite(cost)
  error=abs(cost-row['cost'])/max(1,cost);assert error<1e-12;errors.append(row['audit_error']);assert row['audit_error']<1e-7
  state_hashes[row['name']]=sha(stem.with_suffix('.state'))
  log=stem.with_suffix('.log').read_text()
  if j['arm']=='tr':
   assert manifest['flags']['OCA_NSHIFTS']=='1' and manifest['flags']['OCA_TR_RECURRENCE']=='1'
   assert float(manifest['flags']['OCA_TARGET_COST'])==j['nominal']
   for line in log.splitlines():
    if line.startswith('CAMERA_TR o='):
     v={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)}
     if v['accept']:assert v['rho']>=.1 and v['prediction']>0 and v['norm']<=v['radius']*(1+1e-8);accepted_checks+=1
   with stem.with_suffix('.csv').open() as f:trace=list(csv.DictReader(l for l in f if not l.startswith('#')))
   assert abs(float(trace[-1]['cost'])-cost)<1e-7*max(1,cost)
  else:
   assert float(manifest['flags']['CASPAR_TARGET_COST'])==j['target']
   assert row['precision']==('f32' if j['arm']=='caspar32' else 'f64')
   ci=re.search(r'CHECK_INITIAL score=(\S+) precision=(\S+)',log);assert ci and ci[2]==row['precision']
   if j['arm']=='caspar64':assert row['initial_cpu_gap']<1e-6
  native_hit=row['crossing'] is not None and row['crossing']<=j['cap'];certified=native_hit and cost<=j['target']
  assert row['hit']==certified and row['uncertified_native_hit']==(native_hit and not certified)
  hits[j['arm']]+=int(certified);false_hits[j['arm']]+=int(native_hit and not certified)
 for scene in {j['scene'] for j in protocol['jobs']}:
  for arm in bins:
   positions=[]
   for rep in [1,2,3]:
    order=[j['arm'] for j in protocol['jobs'] if j['scene']==scene and j['rep']==rep];assert len(order)==3;positions.append(order.index(arm))
   assert sorted(positions)==[0,1,2]
 out=dict(runs=len(rows),audited_endpoints=len(errors),max_reported_cpu_audit_error=max(errors),precision_proof=proof['colmap_commit'],hits=hits,uncertified_native_hits=false_hits,failures=failures,accepted_tr_feasibility_checks=accepted_checks,state_sha256=state_hashes)
 (ROOT/'verification.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='state_sha256'},indent=2))
if __name__=='__main__':main()
