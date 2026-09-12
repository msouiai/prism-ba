#!/usr/bin/env python3
"""Authorized small native correctness and source-off compatibility checks."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
from build import P,CAMPAIGN,sha
from parse_trace import analyze
sys.path.insert(0,str(CAMPAIGN));import grid_common as common
OUT=P/'evidence/correctness';SAN='/usr/local/cuda/bin/compute-sanitizer'

def logged(name,cmd,env=None):
 folder=OUT/name;folder.mkdir(parents=True,exist_ok=True)
 if (folder/'result.json').exists():
  old=json.loads((folder/'result.json').read_text());assert old['passed'];return old
 with open('/tmp/prism_gpu.lock','w') as lock,(folder/'stdout.log').open('w') as out:
  fcntl.flock(lock,fcntl.LOCK_EX);rc=subprocess.run(cmd,env=env,stdout=out,stderr=subprocess.STDOUT,timeout=180).returncode
 text=(folder/'stdout.log').read_text();r=dict(command=cmd,returncode=rc,passed=rc==0 and 'ERROR SUMMARY: 0 errors' in text)
 (folder/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(name,r['passed'],flush=True)
 if not r['passed']:raise RuntimeError(text[-6000:])
 return r

def main():
 manifest=json.loads((P/'build_manifest.json').read_text());assert manifest['binary_sha256']==sha(P/'build/prism-soft-kick')
 for f,h in manifest['local_headers'].items():assert sha(P/f)==h
 for f,h in manifest['reused_headers'].items():assert sha(CAMPAIGN/f)==h
 assert json.loads((P/'math_verification.json').read_text())['passed'];OUT.mkdir(parents=True,exist_ok=True)
 tests=dict(native_build_manifest_sha256=sha(P/'build_manifest.json'),math_sha256=sha(P/'math_verification.json'),
  source_sha256={x:sha(P/x) for x in ('test_state.cu','test_math.cc','parse_trace.py','run_correctness.py')},
  test_binary_sha256={x:sha(P/'build'/x) for x in ('soft-state-test','soft-math-test')})
 (P/'tests_manifest.json').write_text(json.dumps(tests,indent=2)+'\n')
 logged('state-restoration-memcheck-v3',[SAN,'--tool','memcheck','--error-exitcode','91',str(P/'build/soft-state-test')])
 assert 'SOFT_STATE_MEMORY warm_free_before=' in (OUT/'state-restoration-memcheck-v3/stdout.log').read_text()
 assert 'new_resident_bytes=0' in (OUT/'state-restoration-memcheck-v3/stdout.log').read_text()
 assert 'SOFT_STATE_TEST pass=1 restored=1 kept=1' in (OUT/'state-restoration-memcheck-v3/stdout.log').read_text()
 for on in (0,1):
  folder=OUT/f'tiny-memcheck-{on}';folder.mkdir(parents=True,exist_ok=True)
  env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','CERES_','COLMAP_MFREE','MF_DEBUG'))}
  flags=dict(common.CHAMP['flags'],OCA_SOFT_KICK=str(on),OCA_SOFT_KICK_ORACLE='1',OCA_FTOL='1',OCA_FTOL_K='1',OCA_MAX_SECONDS='60',OCA_STCG_ATTEMPTS=str(folder/'attempts.json'))
  env.update(flags);cli=list(common.CHAMP['cli']);cli[cli.index('--max_iter')+1]='5'
  cmd=[SAN,'--tool','memcheck','--error-exitcode','91',str(P/'build/prism-soft-kick'),'--problem',str(CAMPAIGN/'build/toy.txt'),*cli,'--csv',str(folder/'curve.csv')]
  (folder/'manifest.json').write_text(json.dumps(dict(command=cmd,flags=flags,build_manifest=manifest,input_sha256=sha(CAMPAIGN/'build/toy.txt'),scope='Artificial FTOL=1,K=1 forces the mechanism only for correctness, never an efficacy arm'),indent=2)+'\n')
  logged(f'tiny-memcheck-{on}',cmd,env)
  audit=analyze(folder/'attempts.json',folder/'stdout.log');(folder/'trace_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
  if on:
   text=(folder/'stdout.log').read_text();assert 'SOFT_KICK_EVENT' in text and 'history_preserved=1' in text
   assert audit['corrected']['intervention_attempts']==1
   assert all(x=='1' for x in re.findall(r'COARSE_ORACLE .*?pass=(\d+)',text))
 rows=[]
 for rep in range(3):
  for arm in (['original','off'] if rep%2==0 else ['off','original']):
   folder=OUT/f'dubrovnik-88-{arm}-{rep}';flags=dict(OCA_SOFT_KICK='0')
   if arm=='off':flags['OCA_STCG_ATTEMPTS']=str(folder/'attempts.json')
   row=common.run(folder,'dubrovnik-88',arm,rep,common.ORIGINAL if arm=='original' else P/'build/prism-soft-kick',flags,CAMPAIGN/'PROTOCOL_11.md',target=0,cap=5,build_manifest=manifest if arm=='off' else None)
   rows.append(row)
   if arm=='off':
    audit=analyze(folder/'attempts.json',folder/'stdout.log');(folder/'trace_audit.json').write_text(json.dumps(audit,indent=2)+'\n');assert audit['corrected']['intervention_attempts']==0
 (OUT/'compatibility_rows.json').write_text(json.dumps(rows,indent=2)+'\n')
 med={a:statistics.median(r['cost'] for r in rows if r['arm']==a) for a in ('original','off')}
 initial=[r['score_init'] for r in rows];spread=(max(initial)-min(initial))/max(1,abs(max(initial)))
 report=dict(median_cost=med,relative_cost_delta=med['off']/med['original']-1,initial_score_relative_spread=spread,
  initial_score_roundoff_pass=spread<=1e-10,endpoint_screen_pass=abs(med['off']/med['original']-1)<=.0015,
  no_efficacy_claim=True,scope='N3 original/source-off compatibility plus small mechanism/memory tests only')
 (OUT/'compatibility_summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
 assert report['initial_score_roundoff_pass'] and report['endpoint_screen_pass']

if __name__=='__main__':main()
