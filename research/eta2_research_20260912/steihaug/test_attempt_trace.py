#!/usr/bin/env python3
"""Prove the common attempt timer retains continue/break paths without CUDA."""
import json
from pathlib import Path
import subprocess

P=Path(__file__).resolve().parent;B=P/'build';B.mkdir(exist_ok=True)
source=B/'attempt_scope_test.cc'
source.write_text('''#include "attempt_trace.h"
int main(int argc,char** argv){
 StcgAttemptTrace trace(argv[1]);long matvecs=0;
 for(int k=0;k<4;++k){
  StcgAttemptClock clock(&trace,0,k,k>0,&matvecs);
  matvecs+=k+1;clock.row.pcg_iterations=k+1;
  if(k==0){clock.row.cutoff=true;clock.row.numeric_repair=true;continue;}
  if(k==1)continue;
  clock.row.accepted=true;break;
 }
}
''')
subprocess.run(['g++','-std=c++17','-O2','-I'+str(P),str(source),'-o',str(B/'attempt-scope-test')],check=True)
subprocess.run([str(B/'attempt-scope-test'),str(B/'attempt-scope-test.json')],check=True)
r=json.loads((B/'attempt-scope-test.json').read_text());t=r['totals']
assert len(r['rows'])==3 and t['attempts']==3 and t['accepted']==1 and t['not_accepted']==2
assert t['numeric_repairs']==1 and t['curvature_cutoffs']==1 and t['cutoff_accepts']==0
assert t['matvecs']==6 and t['pcg_iterations']==6
assert all(x['seconds']>=0 for x in r['rows'])
assert [x['retry_entry'] for x in r['rows']]==[False,True,True]
result=dict(status='passed',numeric_continue_recorded=True,rejected_continue_recorded=True,
            accepted_break_recorded=True,added_cuda_calls=0,rows=r['rows'])
(P/'attempt_trace_verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
