#!/usr/bin/env python3
"""Bounded, independently audited Ceres setup sensitivity check."""
import datetime
import fcntl
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import time

P = Path(__file__).resolve().parent
sys.path.insert(0, str(P.parent))
import run_eta2 as common

TARGET = 1744796.9841897595
PROBLEM = Path('/workspace/bal/final-3068.txt')
BINARY = P / 'build/ceres_setup'
ARMS = {
    'control': {'CERES_NORMALIZE':'0','CERES_STRICT_STOP':'0'},
    'normalize': {'CERES_NORMALIZE':'1','CERES_STRICT_STOP':'0'},
    'strict_stop': {'CERES_NORMALIZE':'0','CERES_STRICT_STOP':'1'},
    'normalize_strict': {'CERES_NORMALIZE':'1','CERES_STRICT_STOP':'1'},
    'normalize_strict_eta01': {'CERES_NORMALIZE':'1','CERES_STRICT_STOP':'1','CERES_INNER_ETA':'0.01'},
}

def record(path, data):
    common.write(path, data)


def run(arm, rep, dims, obs, input_sha, reference):
    folder = P / 'evidence' / f'{arm}-{rep}'
    folder.mkdir(parents=True, exist_ok=True)
    if (folder/'result.json').exists():
        return json.loads((folder/'result.json').read_text())
    state = folder/'endpoint.state'
    flags = dict(ARMS[arm], CERES_TARGET_COST=str(TARGET), CERES_MAX_SECONDS='60',
                 CERES_STATE_OUT=str(state))
    env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CERES_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))}
    env.update(flags)
    command=[str(BINARY),str(PROBLEM),'lm','600','10000','8']
    manifest=dict(command=command,flags=flags,target=TARGET,native_cap=60,process_cap=180,
                  input_sha256=input_sha,binary_sha256=common.sha(BINARY),
                  source_sha256=common.sha(P/'ceres_bal.cc'),protocol_sha256=common.sha(P/'PROTOCOL.md'))
    record(folder/'manifest.json',manifest)
    print('RUN',arm,rep,flush=True)
    start=time.monotonic()
    with (folder/'stdout.log').open('w') as out,(folder/'stderr.log').open('w') as err:
        try:
            proc=subprocess.run(command,env=env,stdout=out,stderr=err,timeout=180)
            rc=proc.returncode
        except subprocess.TimeoutExpired:
            rc=124
    row=dict(arm=arm,rep=rep,scene='final-3068',target=TARGET,valid=False,hit=False,
             returncode=rc,process_seconds=time.monotonic()-start,source=str(folder.relative_to(P)))
    try:
        assert rc==0,rc
        log=(folder/'stdout.log').read_text()
        result=re.search(r'RESULT exit=(\d+) iters=(\d+) final_score=(\S+) runtime=(\S+)',log)
        initial=re.search(r'INITIAL score=(\S+) setup_seconds=(\S+)',log)
        checked=re.search(r'CHECK final_score=(\S+)',log)
        normalization=re.search(r'NORMALIZE enabled=(\d+) center=(\S+) scale=(\S+) initial=(\S+) transformed_initial=(\S+) relerr=(\S+)',log)
        options=re.search(r'SETUP_OPTIONS normalize=(\d+) strict=(\d+) eta=(\S+) gradient_tolerance=(\S+) function_tolerance=(\S+) parameter_tolerance=(\S+)',log)
        assert result and initial and checked and normalization and options
        assert abs(float(initial[1])-reference['independent_score_init'])/reference['independent_score_init']<1e-6
        assert float(normalization[6])<1e-8
        trace=[dict(outer=int(i),cost=float(c),seconds=float(t),accepted=bool(int(a)))
               for i,c,t,a in re.findall(r'TRACE iter=(\d+) cost=(\S+) seconds=(\S+) accepted=(\d+)',log)]
        accepted=[t for t in trace if t['accepted']]
        assert accepted and all(math.isfinite(t['cost']) for t in accepted)
        assert all(b['cost']<=a['cost']+1e-8*max(1,a['cost']) for a,b in zip(accepted,accepted[1:]))
        cost=common.audit(state,dims,obs)
        errors=[abs(cost-float(v))/max(1,abs(cost)) for v in [result[3],checked[1]]]
        assert math.isfinite(cost) and max(errors)<1e-6,errors
        assert abs(accepted[-1]['cost']-cost)/max(1,abs(cost))<1e-6
        crossing=next((t['seconds'] for t in accepted if t['cost']<=TARGET),None)
        termination=re.search(r'Termination:\s*(.+)',log)
        row.update(valid=True,cost=cost,native_cost=float(result[3]),audit_relative_error=max(errors),
                   native_seconds=float(result[4]),setup_seconds=float(initial[2]),
                   hit=crossing is not None and crossing<=60 and cost<=TARGET,
                   target_seconds=crossing,outers=sum(t['outer']>0 for t in trace),
                   accepts=sum(t['outer']>0 and t['accepted'] for t in trace),
                   rejects=sum(t['outer']>0 and not t['accepted'] for t in trace),
                   exit_reason=int(result[1]),stop_reason=termination[1] if termination else 'unparsed',
                   trace=trace,normalization_relative_error=float(normalization[6]),
                   world_center=[float(v) for v in normalization[2].split(',')],world_scale=float(normalization[3]),
                   actual_options=dict(normalize=int(options[1]),strict=int(options[2]),eta=float(options[3]),
                     gradient_tolerance=float(options[4]),function_tolerance=float(options[5]),parameter_tolerance=float(options[6])),
                   state_sha256=common.sha(state))
    except Exception as exc:
        row['error']=str(exc)
    if state.exists():
        gz=Path(str(state)+'.gz')
        with state.open('rb') as f,gzip.open(gz,'wb',compresslevel=1) as out:
            shutil.copyfileobj(f,out)
        with gzip.open(gz,'rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest()==common.sha(state)
        row['compressed_state_sha256']=common.sha(gz)
        state.unlink()  # Only this run's state, after verified lossless preservation.
    record(folder/'result.json',row)
    print('DONE',arm,rep,'valid',row['valid'],'hit',row['hit'],'cost',row.get('cost'),
          'target_seconds',row.get('target_seconds'),'error',row.get('error'),flush=True)
    return row


def main():
    registration=dict(recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        protocol_sha256=common.sha(P/'PROTOCOL.md'),source_sha256=common.sha(P/'ceres_bal.cc'),
        driver_sha256=common.sha(P/'run.py'),target=TARGET,arms=ARMS,reps=3,
        note='New instrumented driver; primary frozen Ceres and Eta2 records remain unchanged.')
    if (P/'registration.json').exists():
        old=json.loads((P/'registration.json').read_text())
        for key in ['protocol_sha256','source_sha256','driver_sha256','target','arms','reps']:
            assert old[key]==registration[key],key
    else:
        record(P/'registration.json',registration)
    print('Registered setup sensitivity check; waiting for the current measurement.',flush=True)
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        with (P/'build.log').open('w') as out:
            subprocess.run(['cmake','-S',str(P),'-B',str(P/'build'),'-DCMAKE_BUILD_TYPE=Release'],stdout=out,stderr=subprocess.STDOUT,check=True)
            subprocess.run(['cmake','--build',str(P/'build'),'-j','2'],stdout=out,stderr=subprocess.STDOUT,check=True)
        record(P/'build-manifest.json',dict(binary_sha256=common.sha(BINARY),
               source_sha256=common.sha(P/'ceres_bal.cc'),cmake_sha256=common.sha(P/'CMakeLists.txt')))
        baseline=json.loads((P.parent/'evidence/ceres-storm/final-3068-ceres-lm-10000-600-1.json').read_text())
        input_sha=common.sha(PROBLEM)
        assert input_sha==baseline['data_sha256']
        dims,obs=common.observations(PROBLEM)
        rows=[run('control',rep,dims,obs,input_sha,baseline) for rep in range(3)]
        assert all(r['valid'] for r in rows), 'Adapter control invalid; no attribution allowed.'
        gaps=[abs(r['cost']/baseline['cost']-1) for r in rows]
        record(P/'control-validation.json',dict(relative_endpoint_gaps=gaps,threshold=.001,
               passed=max(gaps)<.001,old_frozen_lm_cost=baseline['cost']))
        assert max(gaps)<.001, 'New control leaves the frozen endpoint regime; investigate before proceeding.'
        arms=list(ARMS)[1:]
        for rep in range(3):
            for arm in arms if rep%2==0 else arms[::-1]:
                rows.append(run(arm,rep,dims,obs,input_sha,baseline))
        record(P/'results.json',rows)
        summary=[]
        for arm in ARMS:
            rr=[r for r in rows if r['arm']==arm]
            valid=[r for r in rr if r['valid']]
            hits=[r['target_seconds'] for r in valid if r['hit']]
            summary.append(dict(arm=arm,n=len(rr),valid=len(valid),hits=len(hits),
              median_cost=statistics.median(r['cost'] for r in valid) if valid else None,
              median_target_seconds=statistics.median(hits) if hits else None,
              median_native_seconds=statistics.median(r['native_seconds'] for r in valid) if valid else None))
        record(P/'summary.json',summary)
        print('SETUP STUDY COMPLETE',json.dumps(summary),flush=True)


if __name__=='__main__':
    main()
