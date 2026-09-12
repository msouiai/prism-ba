#!/usr/bin/env python3
"""Authorized correctness/compatibility runs only; serialized with other agents."""
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from build import P,CAMPAIGN,sha

sys.path.insert(0,str(CAMPAIGN))
import grid_common as common

OUT=P/'evidence/correctness'
SAN=Path('/usr/local/cuda/bin/compute-sanitizer')

def logged(name,command,env=None):
    folder=OUT/name;folder.mkdir(parents=True,exist_ok=True)
    if (folder/'result.json').exists():
        previous=json.loads((folder/'result.json').read_text());assert previous['passed'];return previous
    report=dict(command=[str(x) for x in command],binary_sha256=sha(command[-1]) if name=='kernel-memcheck' else None)
    with open('/tmp/prism_gpu.lock','w') as lock,(folder/'stdout.log').open('w') as out:
        fcntl.flock(lock,fcntl.LOCK_EX)
        result=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT,env=env,timeout=180)
    text=(folder/'stdout.log').read_text();report.update(returncode=result.returncode,passed=result.returncode==0 and 'ERROR SUMMARY: 0 errors' in text)
    (folder/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(name,report['passed'],flush=True)
    if not report['passed']:raise RuntimeError(text[-5000:])
    return report

def main():
    manifest=json.loads((P/'build_manifest.json').read_text());toy_manifest=json.loads((P/'toy_build_manifest.json').read_text())
    for h,s in manifest['local_headers'].items():assert sha(P/h)==s
    for h,s in toy_manifest['local_headers'].items():assert sha(P/h)==s
    binary=P/'build/prism-coarse';toy=P/'build/coarse-toy'
    assert sha(binary)==manifest['binary_sha256'];assert sha(toy)==toy_manifest['binary_sha256']
    OUT.mkdir(parents=True,exist_ok=True)
    logged('kernel-memcheck',[str(SAN),'--tool','memcheck','--leak-check','full','--error-exitcode','91',str(toy)])
    kernel=(OUT/'kernel-memcheck/stdout.log').read_text()
    assert 'COARSE_TOY pass=1' in kernel and all(x=='1' for x in re.findall(r'COARSE_ORACLE .*?pass=(\d+)',kernel))
    # Native BAL smoke: keep the registered late activation rule, even if inert.
    for on in (0,1):
        folder=OUT/f'tiny-memcheck-{on}';folder.mkdir(parents=True,exist_ok=True)
        env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','CERES_','COLMAP_MFREE','MF_DEBUG'))}
        flags=dict(common.CHAMP['flags'],OCA_COARSE=str(on),OCA_COARSE_ORACLE='1',OCA_ATTEMPT_TRACE='1',OCA_MAX_SECONDS='60')
        env.update(flags)
        command=[str(SAN),'--tool','memcheck','--error-exitcode','91',str(binary),'--problem',str(CAMPAIGN/'build/toy.txt'),*common.CHAMP['cli'],'--csv',str(folder/'curve.csv')]
        (folder/'manifest.json').write_text(json.dumps(dict(command=command,flags=flags,binary_sha256=sha(binary),input_sha256=sha(CAMPAIGN/'build/toy.txt'),protocol_sha256=sha(CAMPAIGN/'PROTOCOL_01_NATIVE.md')),indent=2)+'\n')
        logged(f'tiny-memcheck-{on}',command,env)
    rows=[]
    for rep in range(3):
        order=['original','coarse-off'] if rep%2==0 else ['coarse-off','original']
        for arm in order:
            rows.append(common.run(OUT/f'dubrovnik-88-{arm}-{rep}','dubrovnik-88',arm,rep,
                common.ORIGINAL if arm=='original' else binary,dict(OCA_COARSE='0',OCA_ATTEMPT_TRACE='1'),
                CAMPAIGN/'PROTOCOL_01_NATIVE.md',target=0,cap=5,build_manifest=manifest if arm!='original' else None))
    (OUT/'compatibility_rows.json').write_text(json.dumps(rows,indent=2)+'\n')
    import statistics
    med={a:statistics.median(r['cost'] for r in rows if r['arm']==a) for a in ('original','coarse-off')}
    scores=[r['score_init'] for r in rows]
    initial_relative_spread=(max(scores)-min(scores))/max(1,abs(max(scores)))
    report=dict(median_cost=med,relative_cost_delta=med['coarse-off']/med['original']-1,
                same_score_init_bitwise=len(set(scores))==1,
                initial_score_relative_spread=initial_relative_spread,
                initial_score_roundoff_budget=1e-10,
                initial_score_roundoff_pass=initial_relative_spread<=1e-10,
                endpoint_screen_pass=abs(med['coarse-off']/med['original']-1)<=.0015,
                retained_initial_assertion='compatibility_summary.json preserves the failed bitwise initial-score test',
                scope='N=3 compatibility only; no active-coarse efficacy or speed claim')
    (OUT/'compatibility_summary_scaled.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    assert report['endpoint_screen_pass'] and report['initial_score_roundoff_pass']

if __name__=='__main__':main()
