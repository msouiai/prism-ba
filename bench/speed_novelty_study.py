#!/usr/bin/env python3
"""Frozen new-instance speed/Schur-recovery experiment; no policy tuning."""
import argparse
import datetime
import gzip
import hashlib
import json
import math
import os
import pathlib
import re
import shutil
import socket
import statistics
import subprocess
import time

from audit_prism_state import audit, observations

ROOT = pathlib.Path('/tmp/prism-speed-novelty')
REPO = pathlib.Path(__file__).resolve().parents[1]
BINS = {
    'champion': pathlib.Path('/tmp/prism-rl-actor/build/prism-tr'),
    'off': ROOT/'control-v2/prism-tr',
    'x4_floor': ROOT/'control-v2/prism-tr',
    'control_zero': ROOT/'control-v2/prism-tr',
    'legacy_off': pathlib.Path('/tmp/prism-rl-actor/build/prism-tr'),
    'legacy_control_off': ROOT/'control-v2/prism-tr',
    'caspar32': pathlib.Path('/workspace/prism-caspar-current/caspar32'),
    'caspar64': pathlib.Path('/workspace/prism-caspar-current/caspar64'),
    'ceres_lm': ROOT/'ceres/build/ceres_bal',
    'ceres_dogleg': ROOT/'ceres/build/ceres_bal',
}

def read(p):
    return json.loads(pathlib.Path(p).read_text())

def sha(p):
    with pathlib.Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def put(p, value):
    p = pathlib.Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    tmp.replace(p)

def register():
    p = ROOT/'protocol.json'
    if p.exists():
        proto = read(p)
        assert proto['runner_sha256'] == sha(__file__)
        assert all(sha(BINS[a]) == h for a, h in proto['binaries'].items())
        return proto
    champ = read(ROOT/'champion.json')
    assert sha(BINS['champion']) == champ['binary_sha256']
    proto = dict(selection=read(ROOT/'selection.json'),scenes=read(ROOT/'inputs.json'),
        champion=champ,runner_sha256=sha(__file__),host=socket.gethostname(),
        binaries={a:sha(b) for a,b in BINS.items()},registered=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version','--format=csv,noheader'],text=True).strip(),
        ceres_version='2.2.0',ceres_profiles={'ceres_lm':'ITERATIVE_SCHUR/SCHUR_JACOBI, radius10000, eight threads',
        'ceres_dogleg':'SPARSE_SCHUR/SuiteSparse, radius10000, eight threads'},
        cap_rule='A target qualifies only when reached inside native cap; Ceres may finish a current iteration beyond cap, which is retained and classified as late.',
        cap_limits='600 accepted iterations for Prism versus 600 attempted for external solvers; native cap primary.',
        precision_buffer='Caspar FP32 native stop is 0.999 times registered target, with original-observation FP64 endpoint audit. This is conservative and disclosed.',
        state_policy='Every endpoint independently audited; generated state compressed losslessly then raw export removed after decompressed SHA check.',
        comparison_rule='Median/min-max only for 3/3 hits; retain misses, endpoint gaps, cap hits and invalid audits. No aggregate over a changing subset.')
    put(p, proto)
    return proto

def run_one(proto, phase, scene, arm, rep, target, cap, dims, obs, iterations=600):
    folder = ROOT/phase
    folder.mkdir(exist_ok=True)
    stem = folder/f'{scene}-{arm}-{rep}'
    rp = stem.with_suffix('.result.json')
    if rp.exists():
        row = read(rp)
        assert row['target'] == target and row['cap'] == cap
        assert read(stem.with_suffix('.manifest.json'))['binary_sha256'] == proto['binaries'][arm]
        return row
    assert sha(BINS[arm]) == proto['binaries'][arm]
    env = {k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','CERES_','COLMAP_MFREE','MF_DEBUG'))}
    state = stem.with_suffix('.state')
    path = proto['scenes'][scene]['path']
    if arm.startswith('caspar'):
        env.update(CASPAR_TARGET_COST=str(target*(.999 if arm=='caspar32' else 1)),
            CASPAR_MAX_SECONDS=str(cap),CASPAR_STATE_OUT=str(state))
        cmd = [str(BINS[arm]),path,str(iterations),'default']
    elif arm.startswith('ceres'):
        env.update(CERES_TARGET_COST=str(target),CERES_MAX_SECONDS=str(cap),CERES_STATE_OUT=str(state))
        cmd = [str(BINS[arm]),path,'lm' if arm=='ceres_lm' else 'dogleg',str(iterations),'10000','8']
    else:
        env.update(proto['champion']['flags'],OCA_TARGET_COST=str(target),OCA_MAX_SECONDS=str(cap))
        if arm in ('off','legacy_off','legacy_control_off'):
            env['OCA_SCHUR_NUMERIC_GUARD'] = '0'
        if arm == 'off':
            env['OCA_SCHUR_ABLATION'] = '1'
        if arm in ('legacy_off','legacy_control_off'):
            env.pop('OCA_RLA_FIXED_ETA')
        if arm == 'x4_floor':
            env['OCA_SCHUR_RECOVERY_MODE'] = '2'
        cmd = [str(BINS[arm]),'--problem',path,'--algo','mfree_shifted_cg','--dof9','--zero_k2',
            '--lam0','0.1','--max_iter',str(iterations),'--state_out',str(state)]
    cmd = ['flock','/tmp/prism_gpu.lock','timeout','120']+cmd
    put(stem.with_suffix('.manifest.json'),dict(command=cmd,binary_sha256=proto['binaries'][arm],
        input_sha256=proto['scenes'][scene]['input_sha256'],protocol_sha256=sha(ROOT/'protocol.json'),
        flags={k:v for k,v in env.items() if k.startswith(('OCA_','CASPAR_','CERES_'))}))
    print('RUN',phase,scene,arm,rep,flush=True)
    start = time.monotonic()
    with stem.with_suffix('.log').open('w') as out, stem.with_suffix('.stderr').open('w') as err:
        proc = subprocess.run(cmd,env=env,stdout=out,stderr=err)
    row = dict(phase=phase,scene=scene,arm=arm,rep=rep,target=target,cap=cap,
        process_wall=time.monotonic()-start,returncode=proc.returncode,hit=False,valid=False,artifact=str(stem))
    try:
        assert proc.returncode == 0, ('returncode',proc.returncode)
        log = stem.with_suffix('.log').read_text()
        cost = audit(state,dims,obs)
        if arm.startswith(('caspar','ceres')):
            reported = float(re.search(r'CHECK final_score=(\S+)',log)[1])
            seconds = float(re.search(r'RESULT .*?runtime=(\S+)',log)[1])
            trace = [(int(i),float(c),float(t),int(a)) for i,c,t,a in
                re.findall(r'TRACE iter=(\d+) cost=(\S+) seconds=(\S+) accepted=(\d+)',log)]
            # Ceres iteration zero is initial evaluation, not an attempted step.
            attempted = [x for x in trace if not arm.startswith('ceres') or x[0]>0]
            accepts = sum(x[3] for x in attempted)
            row.update(accepts=accepts,rejects=len(attempted)-accepts,outers=len(attempted),
                setup_seconds=float(re.search(r'setup_seconds=(\S+)',log)[1]),
                numeric_rebuilds=0,negcurv=0,trace=[dict(iter=i,cost=c,seconds=t,accepted=a) for i,c,t,a in trace])
            # Endpoint audit certifies the final target-crossing state, not all intermediate traces.
            crossing = seconds if cost<=target else None
            row['cap_hit'] = seconds>=cap or len(attempted)>=iterations
        else:
            m = re.search(r'RESULT .*?final_cost=(\S+) solve_seconds=(\S+)',log)
            reported,seconds = map(float,m.groups())
            reached = re.search(r'TARGET reached outer=(\d+) seconds=(\S+)',log)
            crossing = float(reached[2]) if reached else None
            counts = re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+) negcurv=(\d+)',log)
            repair = re.search(r'NUMERIC_REPAIR summary rebuilds=(\d+) floor=(\S+)',log)
            events = [{k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)} for line in log.splitlines() if line.startswith('NUMERIC_REPAIR o=')]
            row.update(accepts=int(counts[1]),rejects=int(counts[2]),matvecs=int(counts[3]),negcurv=int(counts[4]),
                outers=int(counts[1])+int(counts[2]),numeric_rebuilds=int(repair[1]) if repair else 0,
                numeric_floor=float(repair[2]) if repair else None,repair_events=events,setup_seconds=0)
            row['cap_hit'] = seconds>=cap or row['accepts']>=iterations
            for line in log.splitlines():
                if line.startswith('CLASSICAL_LM o='):
                    v = {k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)}
                    assert abs(v['lambda']-v['tau']) <= 1e-10*max(1e-16,v['lambda'])
                    if v['accept']:
                        assert v['rho']>.1 and v['prediction']>0
                if line.startswith('ATTR_RADIUS o='):
                    v = {k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)}
                    if v['accept']:
                        assert v['rho']>.1 and v['norm']<=v['radius']*(1+1e-8)
        error = abs(cost-reported)/max(1,abs(cost))
        row.update(cost=cost,reported=reported,seconds=seconds,crossing=crossing,audit_error=error,
            state_sha256=sha(state),target_gap_fraction=cost/target-1 if target>1e-50 else None)
        assert math.isfinite(cost) and error<proto['selection']['audit_relative_tolerance'],('audit',error)
        row.update(valid=True,hit=crossing is not None and crossing<=cap and cost<=target)
    except Exception as e:
        row['error'] = str(e)
    if state.exists():
        gz = pathlib.Path(str(state)+'.gz')
        with state.open('rb') as f, gzip.open(gz,'wb',compresslevel=1) as out:
            shutil.copyfileobj(f,out)
        with gzip.open(gz,'rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest() == sha(state)
        row['compressed_state_sha256'] = sha(gz)
        state.unlink()
    put(rp,row)
    print('DONE',phase,scene,arm,rep,'valid',row['valid'],'hit',row['hit'],'s',row.get('crossing'),
        'cost',row.get('cost'),'repairs',row.get('numeric_rebuilds'),'error',row.get('error'),flush=True)
    return row

def summary(rows):
    out = []
    for phase,scene,arm in dict.fromkeys((r['phase'],r['scene'],r['arm']) for r in rows):
        rr = [r for r in rows if (r['phase'],r['scene'],r['arm'])==(phase,scene,arm)]
        hits = [r['crossing'] for r in rr if r['hit']]
        out.append(dict(phase=phase,scene=scene,arm=arm,runs=len(rr),hits=len(hits),valid=sum(r['valid'] for r in rr),
            median=statistics.median(hits) if len(hits)==len(rr) else None,range=[min(hits),max(hits)] if hits else None,
            costs=[r.get('cost') for r in rr],seconds=[r.get('seconds') for r in rr],
            rejects=[r.get('rejects') for r in rr],rebuilds=[r.get('numeric_rebuilds') for r in rr],
            cap_hits=sum(r.get('cap_hit',False) for r in rr)))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('phase',choices=['register','compatibility','calibrate','measure'])
    a = ap.parse_args()
    proto = register()
    if a.phase == 'register':
        return
    rows = []
    if a.phase == 'compatibility':
        scene = 'compat-ladybug49'
        path = pathlib.Path('/workspace/bal/ladybug-49.txt')
        proto['scenes'][scene] = dict(path=str(path),input_sha256=sha(path))
        dims,obs = observations(path)
        for rep in range(1,4):
            for arm in ['champion','control_zero','legacy_off','legacy_control_off']:
                rows.append(run_one(proto,'compatibility',scene,arm,rep,1e-100,5,dims,obs,8))
        assert all(r['valid'] for r in rows)
        for pair in [('champion','control_zero'),('legacy_off','legacy_control_off')]:
            rr = [r for r in rows if r['arm'] in pair]
            assert (max(r['cost'] for r in rr)-min(r['cost'] for r in rr))/max(r['cost'] for r in rr)<1e-7
            assert len({(r['accepts'],r['rejects'],r['matvecs']) for r in rr})==1
        put(ROOT/'compatibility.json',dict(passed=True,rows=rows))
        return
    assert read(ROOT/'compatibility.json')['passed']
    if a.phase == 'measure':
        anchors = read(ROOT/'anchors.json')
        assert anchors['protocol_sha256']==sha(ROOT/'protocol.json')
    for si,(scene,spec) in enumerate(proto['scenes'].items()):
        assert sha(spec['path']) == spec['input_sha256']
        dims,obs = observations(spec['path'])
        tasks = [('calibration',1e-100,15,['off','caspar64'])] if a.phase=='calibrate' else [
            ('q'+str(mult),anchors['anchors'][scene]*mult,proto['selection']['native_caps'][scene],
             proto['selection']['timing_arms']+(['off','x4_floor'] if mult==1.01 else []))
            for mult in proto['selection']['quality_multipliers']]
        for phase,target,cap,arms in tasks:
            for rep in range(1,4):
                offset=(si+rep-1)%len(arms)
                for arm in arms[offset:]+arms[:offset]:
                    rows.append(run_one(proto,phase,scene,arm,rep,target,cap,dims,obs))
                    put(ROOT/(a.phase+'-rows.json'),rows)
                    put(ROOT/(a.phase+'-summary.json'),summary(rows))
        del obs
    if a.phase == 'calibrate':
        assert all(sum(r['valid'] for r in rows if r['scene']==s and r['arm']==arm)>=1
            for s in proto['scenes'] for arm in ['off','caspar64'])
        anchors = {s:min(r['cost'] for r in rows if r['scene']==s and r['valid']) for s in proto['scenes']}
        record = dict(anchors=anchors,protocol_sha256=sha(ROOT/'protocol.json'),
            calibration_sha256=sha(ROOT/'calibrate-rows.json'),frozen=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            interpretation='Best endpoint under bounded reference calibration, not a certified optimum; all targets fixed before measured runs.')
        p = ROOT/'anchors.json'
        if p.exists():
            assert read(p)['anchors']==anchors
        else:
            put(p,record)
    else:
        assert len(rows)==153
        put(ROOT/'COMPLETE.json',dict(runs=len(rows),valid=sum(r['valid'] for r in rows),
            seconds=sum(r.get('seconds',0) for r in rows),completed=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    print('COMPLETE',a.phase,len(rows),flush=True)

if __name__=='__main__':
    main()
