#!/usr/bin/env python3
"""Registered serial pair/precision experiment with independent endpoint scoring."""
import argparse, csv, fcntl, functools, gzip, hashlib, json, math, os, re, shutil
import socket, statistics, subprocess, sys, time
from pathlib import Path
P=Path(__file__).resolve().parent
F=P.parent/'eta2_champion'
sys.path.insert(0,str(F/'bench'))
from audit_prism_state import observations,audit
observations=functools.lru_cache(maxsize=2)(observations)
CHAMP=json.loads((F/'champion.json').read_text())
ORIGINAL=Path('/tmp/prism-rl-actor/build/prism-tr')
TARGETS={'final-3068':1744796.9841897595,'venice-52':243740.27}
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,obj):
    p.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
def records(text,prefix):
    out=[]
    for line in text.splitlines():
        if line.startswith(prefix+' '):
            row={}
            for k,v in re.findall(r'(\w+)=(\S+)',line):
                try:row[k]=float(v)
                except ValueError:row[k]=v
            # Keep non-finite diagnostics visible but JSON-safe.
            out.append({k:(v if not isinstance(v,float) or math.isfinite(v) else str(v)) for k,v in row.items()})
    return out
def run(scene,arm,rep,stage,target,input_sha):
    folder=P/'evidence'/stage/f'{scene}-{arm}-{rep}';folder.mkdir(parents=True,exist_ok=True)
    path=folder/'result.json'
    if path.exists():return json.loads(path.read_text())
    binary=ORIGINAL if arm=='original' else P/'build/prism-pair'
    bm=json.loads((P/'build/manifest.json').read_text())
    expected=CHAMP['binary_sha256'] if arm=='original' else bm['binary_sha256']
    assert sha(binary)==expected
    flags=dict(CHAMP['flags'],OCA_MAX_SECONDS='60')
    if target is not None:flags['OCA_TARGET_COST']=str(target)
    if arm in ['pair','pair64','both64']:flags.update(OCA_DEPTH_STOP='1',OCA_DEPTH_PAIR='1')
    if arm in ['declip','declip64','both64']:flags['OCA_DEPTH_DECLIP']='1'
    if arm in ['pair64','declip64','both64']:flags['OCA_DEPTH_FP64']='1'
    env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','CERES_','COLMAP_MFREE','MF_DEBUG'))}
    env.update(flags)
    problem=Path('/workspace/bal')/(scene+'.txt');assert sha(problem)==input_sha
    state=folder/'endpoint.state'
    cmd=[str(binary),'--problem',str(problem),'--algo','mfree_shifted_cg','--dof9','--zero_k2',
         '--lam0','0.1','--max_iter','600','--csv',str(folder/'curve.csv'),'--state_out',str(state)]
    write(folder/'manifest.json',dict(command=cmd,flags=flags,binary_sha256=expected,
          source_sha256=bm['frozen_source_sha256'] if arm=='original' else bm['source_sha256'],
          input_sha256=input_sha,protocol_sha256=sha(P/'PROTOCOL.md'),host=socket.gethostname(),
          cap_seconds=60,cap_outers=600,target=target))
    print('RUN',stage,scene,arm,rep,flush=True)
    dims,obs=observations(problem)
    with (folder/'stdout.log').open('w') as out,(folder/'stderr.log').open('w') as err:
        begin=time.monotonic()
        try:rc=subprocess.run(cmd,env=env,stdout=out,stderr=err,timeout=180).returncode
        except subprocess.TimeoutExpired:rc=124
        process=time.monotonic()-begin
    row=dict(scene=scene,arm=arm,rep=rep,stage=stage,target=target,valid=False,hit=False,
             returncode=rc,process_seconds=process,source=str(folder.relative_to(P)))
    try:
        assert rc==0,rc
        text=(folder/'stdout.log').read_text()
        m=re.search(r'RESULT .*?iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)',text);assert m
        count=re.search(r'MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)',text);assert count
        reached=re.search(r'TARGET reached outer=(\d+) seconds=(\S+) cost=(\S+)',text)
        with (folder/'curve.csv').open() as f:
            curve=list(csv.DictReader(l for l in f if not l.startswith('#')))
        costs=[float(v['cost']) for v in curve]
        assert all(math.isfinite(v) for v in costs)
        assert all(b<=a+1e-8*max(1,abs(a)) for a,b in zip(costs,costs[1:]))
        endpoint=audit(state,dims,obs);error=abs(endpoint-float(m[2]))/max(1,endpoint)
        assert error<1e-6,error
        triggers=records(text,'DEPTH_TRIGGER');probes=records(text,'DEPTH_RESULT')
        assert sum(r['kind']==1 for r in probes)<=1 and sum(r['kind']==2 for r in probes)<=1
        if arm in ['original','off']:assert not triggers and not probes
        for p in probes:
            if p['accept']:assert p['candidate']<p['cost'] and p['rho']>.1 and not p['trunc']
            assert p['cg']<=512
        crossing=float(reached[2]) if reached else None
        reason='target' if reached else 'budget' if 'BUDGET stop=' in text else 'depth_confirmed' if 'DEPTH_STOP confirmed' in text else 'ftol' if 'converged (OCA_FTOL' in text else 'outer_cap' if int(m[1])>=600 else 'other'
        row.update(valid=True,cost=endpoint,native_cost=float(m[2]),native_seconds=float(m[3]),
            audit_relative_error=error,initial_cost=costs[0],target_seconds=crossing,
            hit=target is not None and crossing is not None and crossing<=60 and endpoint<=target,
            outers=int(m[1]),accepts=int(count[1]),rejects=int(count[2]),matvecs=int(count[3]),
            stop_reason=reason,cap_hit=reason in ['budget','outer_cap'],
            triggers=triggers,probes=probes,restores=records(text,'DEPTH_RESTORE'),
            probe_summary=records(text,'DEPTH_SUMMARY'),state_sha256=sha(state),
            pair_witnesses=records(text,'PAIR_WITNESS'),pair_restores=records(text,'PAIR_RESTORE'),
            precision=records(text,'DEPTH_PRECISION'),linear=records(text,'DEPTH_LINEAR'))
        assert len(row['precision'])==sum(len(probes)>0 and arm in ['pair64','declip64','both64'] for _ in probes)
        if arm in ['original','off']:assert not row['precision'] and not row['pair_witnesses']
        for v in row['pair_restores']:
            assert abs(v['lambda']*v['radius']**2/(v['saved_lambda']*v['saved_radius']**2)-1)<1e-12
    except Exception as exc:row['error']=str(exc)
    if state.exists():
        gz=Path(str(state)+'.gz')
        with state.open('rb') as f,gzip.open(gz,'wb',compresslevel=1) as out:shutil.copyfileobj(f,out)
        with gzip.open(gz,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==sha(state)
        row['compressed_state_sha256']=sha(gz)
        state.unlink()  # This run's raw state only; lossless compressed copy verified above.
    write(path,row)
    print('DONE',scene,arm,rep,'valid',row['valid'],'hit',row['hit'],'cost',row.get('cost'),
          'seconds',row.get('target_seconds') or row.get('native_seconds'),'probes',len(row.get('probes',[])),
          'stop',row.get('stop_reason'),'error',row.get('error'),flush=True)
    assert row['valid'],row
    return row
def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['compatibility','final','venice','screen','combo'])
    a=ap.parse_args()
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        manifest=P/'inputs.json'
        if not manifest.exists():
            write(manifest,{s:sha(Path('/workspace/bal')/(s+'.txt')) for s in
                           ['final-3068','venice-52','dubrovnik-88','ladybug-1197']})
        inputs=json.loads(manifest.read_text())
        if a.stage=='compatibility':scenes=['dubrovnik-88'];arms=['original','off'];n=3
        elif a.stage=='final':scenes=['final-3068'];arms=['original','pair','pair64'];n=10
        elif a.stage=='venice':scenes=['venice-52'];arms=['original','pair','pair64','declip','declip64'];n=10
        elif a.stage=='screen':scenes=['dubrovnik-88','ladybug-1197'];arms=['original','off','pair','pair64','declip64','both64'];n=3
        else:
            gate=json.loads((P/'gates.json').read_text())
            assert gate['pair64_final_pass'] and gate['declip64_venice_hits']>0
            scenes=['final-3068','venice-52'];arms=['both64'];n=10
        rows=[]
        for s in scenes:
            for rep in range(n):
                j=rep%len(arms)
                for arm in arms[j:]+arms[:j]:
                    rows.append(run(s,arm,rep,a.stage,TARGETS.get(s),inputs[s]))
                    write(P/(a.stage+'-results.json'),rows)
        for s in scenes:
            for arm in arms:
                rr=[r for r in rows if r['scene']==s and r['arm']==arm]
                hits=[r['target_seconds'] for r in rr if r['hit']]
                print('SUMMARY',s,arm,'hits',len(hits),'/',len(rr),
                      'cost',statistics.median(r['cost'] for r in rr),
                      'conditional_seconds',statistics.median(hits) if hits else None,
                      'native_seconds',statistics.median(r['native_seconds'] for r in rr),flush=True)
if __name__=='__main__':main()
