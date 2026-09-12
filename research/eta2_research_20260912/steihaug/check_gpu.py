#!/usr/bin/env python3
"""Authorized correctness checks only; acquire the shared lock for each run."""
import argparse
import csv
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import statistics
import subprocess
import sys
import time

P=Path(__file__).resolve().parent
F=P.parent.parent/'eta2_champion'
CHAMP=json.loads((F/'champion.json').read_text())
sys.path.insert(0,str(F/'bench'))
from audit_prism_state import audit,observations


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def write(path,obj):path.write_text(json.dumps(obj,indent=2)+'\n')


def run_locked(cmd,env,folder):
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        print('RUN',folder.name,flush=True)
        start=time.monotonic()
        with (folder/'stdout.log').open('w') as out,(folder/'stderr.log').open('w') as err:
            p=subprocess.run(cmd,env=env,stdout=out,stderr=err,timeout=600)
        elapsed=time.monotonic()-start
    return p.returncode,elapsed


def metric():
    folder=P/'results/metric';folder.mkdir(parents=True,exist_ok=True)
    binary=P/'build/test-metric'
    cmd=['/usr/local/cuda/bin/compute-sanitizer','--tool','memcheck','--error-exitcode','91',str(binary)]
    write(folder/'manifest.json',dict(command=cmd,binary_sha256=sha(binary),
      source_sha256=sha(P/'test_metric.cu'),metric_sha256=sha(P/'metric.cuh'),
      host=socket.gethostname(),scope='GPU metric correctness; no solver benchmark'))
    rc,seconds=run_locked(cmd,os.environ.copy(),folder)
    output=(folder/'stdout.log').read_text()+(folder/'stderr.log').read_text()
    result=dict(returncode=rc,process_seconds=seconds,
      passed=rc==0 and 'status=passed' in output and 'ERROR SUMMARY: 0 errors' in output)
    write(folder/'result.json',result);assert result['passed'],result
    print('METRIC',result,flush=True)


def solver(scene,arm,rep,sanitize=False):
    folder=P/'results'/f'{scene}-{arm}-{rep}';folder.mkdir(parents=True,exist_ok=True)
    bm=json.loads((P/'build_manifest.json').read_text())
    original=arm=='original'
    binary=Path('/tmp/prism-rl-actor/build/prism-tr') if original else P/'build/prism-stcg'
    expected=CHAMP['binary_sha256'] if original else bm['binary_sha256']
    assert sha(binary)==expected
    if not original:
        assert bm['local_headers']=={name:sha(P/name) for name in bm['local_headers']}
    if (folder/'result.json').exists():
        previous=json.loads((folder/'manifest.json').read_text())
        assert previous['binary_sha256']==expected,'Cached check belongs to another build'
        result=json.loads((folder/'result.json').read_text())
        assert result['passed'];return result
    problem=P.parent/'build/toy.txt' if scene=='toy' else Path('/workspace/bal')/(scene+'.txt')
    flags=dict(CHAMP['flags'],OCA_MAX_SECONDS='60')
    if not original:
        flags['OCA_STEIHAUG']='1' if arm=='stcg' else '0'
        flags['OCA_STCG_ATTEMPTS']=str(folder/'attempts.json')
    cli=CHAMP['cli'].copy()
    if scene=='toy':cli[cli.index('--max_iter')+1]='8'
    state=P/'build'/f'{scene}-{arm}-{rep}.state'
    cmd=[str(binary),'--problem',str(problem),*cli,'--csv',str(folder/'curve.csv'),'--state_out',str(state)]
    if sanitize:cmd=['/usr/local/cuda/bin/compute-sanitizer','--tool','memcheck','--error-exitcode','91']+cmd
    env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','CERES_','COLMAP_MFREE','MF_DEBUG'))}
    env.update(flags)
    write(folder/'manifest.json',dict(scene=scene,arm=arm,rep=rep,command=cmd,flags=flags,
      input_sha256=sha(problem),binary_sha256=expected,host=socket.gethostname(),
      build_manifest=None if original else bm,scope='Correctness/source-off compatibility only; no speed claim'))
    rc,seconds=run_locked(cmd,env,folder)
    output=(folder/'stdout.log').read_text();err=(folder/'stderr.log').read_text()
    m=re.search(r'RESULT .*?iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)',output)
    counts=re.search(r'MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)',output)
    assert rc==0 and m and counts,(rc,bool(m),bool(counts))
    dims,obs=observations(problem);cost=audit(state,dims,obs)
    rel=abs(cost-float(m[2]))/max(1,cost);assert rel<1e-8,rel
    initial=list(csv.DictReader(x for x in (folder/'curve.csv').read_text().splitlines() if not x.startswith('#')))[0]
    result=dict(scene=scene,arm=arm,rep=rep,returncode=rc,process_seconds=seconds,
      native_seconds=float(m[3]),outers=int(m[1]),cost=cost,score_init=float(initial['cost']),
      accepts=int(counts[1]),rejects=int(counts[2]),matvecs=int(counts[3]),cpu_cost_relative_error=rel,
      state_sha256=sha(state),passed=True,sanitizer=sanitize)
    if sanitize:
        assert 'ERROR SUMMARY: 0 errors' in output+err
    if not original:
        trace=json.loads((folder/'attempts.json').read_text())
        assert trace['totals']['accepted']==result['accepts']
        assert trace['totals']['matvecs']==result['matvecs']
        result['attempt_totals']=trace['totals']
    if arm=='stcg':
        rows=[]
        for line in output.splitlines():
            if line.startswith('STCG o='):
                d=dict(word.split('=',1) for word in line.split()[1:])
                if int(d['accept']):assert float(d['norm'])<=float(d['radius'])*(1+1e-8),d
                rows.append(d)
        assert rows;result['stcg_attempts']=len(rows)
        assert len(rows)==result['attempt_totals']['attempts']
    write(folder/'result.json',result)
    print('DONE',scene,arm,rep,'cost',cost,'outers',result['outers'],flush=True)
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['metric','toy','compatibility']);args=ap.parse_args()
    subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
    if args.stage=='metric':metric();return
    if args.stage=='toy':
        rows=[solver('toy',arm,0,True) for arm in ['off','stcg']]
        write(P/'results/toy-summary.json',rows);return
    rows=[]
    for rep in range(3):
        for arm in (['original','off'] if rep%2==0 else ['off','original']):
            rows.append(solver('dubrovnik-88',arm,rep))
    a=[x['cost'] for x in rows if x['arm']=='original'];b=[x['cost'] for x in rows if x['arm']=='off']
    delta=100*(statistics.median(b)/statistics.median(a)-1)
    result=dict(rows=rows,median_cost_delta_percent=delta,passed=abs(delta)<.15,
      scope='Source-off compatibility only, N=3. No timing or bit-identity claim.')
    write(P/'results/compatibility-summary.json',result);assert result['passed'],delta
    print('COMPATIBILITY delta_percent',delta,flush=True)


if __name__=='__main__':main()
