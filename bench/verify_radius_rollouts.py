#!/usr/bin/env python3
import pathlib,json,re,csv
from profile_iterations import sha
from cached_benchmark_input import load_input
from audit_prism_state import audit
ROOT=pathlib.Path('/workspace/prism-adaptive-radius')
def main():
 cache={};checked=[];residual=[];active_contracts=0
 for root,phases in [(ROOT,['adaptive','ray']),(pathlib.Path('/workspace/prism-early-radius'),['early']),(pathlib.Path('/workspace/prism-separate-tau'),['separate'])]:
  for phase in phases:
   path=root/phase
   if not (path/'results.json').exists():continue
   protocol=json.loads((path/'protocol.json').read_text());assert sha(root/'source.cu')==protocol['source_sha256'];assert sha(root/'prism')==protocol['binary_sha256']
   for p,h in protocol['headers'].items():assert sha(p)==h,p
   rows=json.loads((path/'results.json').read_text());assert len(rows)==14
   for r in rows:
    scene=r['scene'];stem=path/(scene+'-mode'+str(r['mode'])+'-rep'+str(r['rep']))
    if scene not in cache:cache[scene]=load_input(pathlib.Path('/workspace/bal')/(scene+'.txt'),'/workspace/prism-caspar-expanded/cpu-cache')
    dh,(dims,obs),initial=cache[scene];assert dh==protocol['data_sha256'][scene]
    cost=audit(stem.with_suffix('.state'),dims,obs);assert abs(cost-r['cost'])<=1e-10*max(1,cost)
    with stem.with_suffix('.csv').open() as f:trace=list(csv.DictReader(l for l in f if not l.startswith('#')))
    assert abs(float(trace[0]['cost'])-initial)<1e-7*initial
    assert abs(float(trace[-1]['cost'])-cost)<1e-7*cost
    assert all(float(b['cost'])<=float(a['cost'])*(1+1e-10) for a,b in zip(trace,trace[1:]))
    manifest=json.loads(stem.with_suffix('.manifest.json').read_text())
    if r['rep']>0:assert not any(k in manifest['flags'] for k in ['OCA_PROFILE','OCA_LEARN_LOG','OCA_RADIUS_TRACE'])
    prev=None
    for line in stem.with_suffix('.log').read_text().splitlines():
     if line.startswith('ADAPT_RADIUS'):
      v={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)};assert v['depth']<=128
      if not v['fallback']:assert v['residual']<=.1;residual.append(v['residual'])
     if line.startswith('RADIUS_TRIAL'):
      v={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)}
      if phase in ['early','separate']:assert v['o']==0
      if v['accept']:assert v['norm']<=v['radius']*(1+1e-8) and v['rho']>=.1
      if prev and prev['o']==v['o'] and not prev['accept'] and v['radius']<prev['radius']:
       if v['radius']<prev['norm']:active_contracts+=1
      prev=v
    checked.append(r)
 out=dict(audited_endpoints=len(checked),max_cost_relative_error=max(r['audit_error'] for r in checked),native_seconds=sum(r['native'] for r in checked),process_seconds=sum(r['wall'] for r in checked),verified_adaptive_current_solves=len(residual),max_verified_relative_residual=max(residual),logged_contractions_below_rejected_norm=active_contracts)
 (ROOT/'verification.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
if __name__=='__main__':main()
