#!/usr/bin/env python3
"""Check retained validation cells, audits, identities and frozen artifacts."""
import json,math,pathlib,sys
from profile_iterations import sha
from validation_study import read_rows,ARMS,SCENES
root=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else pathlib.Path('/workspace/prism-validation')
selection=json.loads((root/'selection.json').read_text());results=[]
for phase,expected in [('ablation',24),('budgets',72)]:
 rows=read_rows(root/phase);assert len(rows)==expected
 seen=set()
 for r in rows:
  key=(r['scene'],r['arm'],r['budget'],r['rep']);assert key not in seen;seen.add(key)
  assert r['status']=='ok' and math.isfinite(r['cost']) and r['cost']>=0
  label=r['arm']+(f"-{r['budget']}s" if r['budget'] else '')
  stem=root/phase/f"{r['scene']}-{label}-{r['rep']}"
  m=json.loads(stem.with_suffix('.manifest.json').read_text())
  assert sha(m['command'][4])==m['binary_sha256']
  data=pathlib.Path('/workspace/bal')/(r['scene']+'.txt')
  # Cache hashes, including shared inputs across all cells.
  if str(data) not in globals().setdefault('hashes',{}):hashes[str(data)]=sha(data)
  assert hashes[str(data)]==r['data_sha256']==m['data_sha256']
  if r['arm']!='caspar32':
   assert sha(stem.with_suffix('.state'))==r['state_sha256']
   assert r['audit_relerr']<1e-7 and r['initial_relerr']<1e-6
   costs=[float(t['cost']) for t in r['trace']]
   assert all(math.isfinite(c) for c in costs)
   assert all(y<=x+1e-9*max(1,x) for x,y in zip(costs,costs[1:]))
   if r['arm']=='selected':
    assert all(m['flags'].get(k)==v for k,v in selection['flags'].items())
    assert 'OCA_PROGRESSIVE_DEPTH' not in m['flags'] if selection['selected']=='rearm' else True
  results.append(r)
old=json.loads((root/'provenance.json').read_text())
for path,expected in old.items():
 actual=root/'caspar-driver-source.cc' if path.endswith('/bench/caspar/caspar_bal32_checked.cc') else pathlib.Path(path)
 assert sha(actual)==expected,(path,actual)
assert sha('/workspace/prism-ba/gpu/oca_cuda.cu')==sha(root/'prism-source.cu')
summary=dict(cells=len(results),failures=0,all_audits_pass=True,frozen_binary_and_input_hashes_match=True,prism_traces_finite_monotone=True,selected_policy_unchanged=True,max_prism_audit_relerr=max(r.get('audit_relerr',0) for r in results))
(root/'verification.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
