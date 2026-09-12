#!/usr/bin/env python3
"""Fresh B0 phase profiles of the frozen Eta2 champion."""
from pathlib import Path
import csv, fcntl, hashlib, json, os, re, socket, statistics, subprocess, sys, tempfile, time

P=Path(__file__).resolve().parent
F=P.parent/'eta2_champion'
W3=P.parent/'eta2_wave3'
sys.path.insert(0,str(F/'bench'))
from audit_prism_state import observations,audit

CHAMP=json.loads((F/'champion.json').read_text())
BINARY=Path('/tmp/prism-rl-actor/build/prism-tr')


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def register():
    subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
    assert sha(BINARY)==CHAMP['binary_sha256']
    old=json.loads((W3/'registration.json').read_text())
    reg=dict(binary=str(BINARY),binary_sha256=sha(BINARY),champion_sha256=sha(F/'champion.json'),
        source_sha256=sha(F/'source/prism_eta2.cu'),protocol_sha256=sha(P/'B0_PROTOCOL.md'),
        flags=dict(CHAMP['flags'],OCA_PROFILE='1',OCA_PROF_SCORE='1'),
        practical=old['practical'],repetitions=3,host=socket.gethostname(),
        endpoint_policy='Independently audit temporary state, record hashes, then remove; diagnostic timing only')
    path=P/'b0-registration.json'
    if path.exists():assert json.loads(path.read_text())==reg
    else:write(path,reg)
    return reg


def parse(text):
    p=re.search(r'\[PROFILE\] assembly=(\S+)s pointfactor\+rhs=(\S+)s krylov=(\S+)s candidates=(\S+)s',text)
    assert p
    score=re.search(r'\[SCORE\] n=(\d+) pass1\+backsub=(\S+)ms copy\+neg=(\S+)ms retract=(\S+)ms cost=(\S+)ms',text)
    back=re.search(r'\[PROFILE\] backtrack=(\S+)s',text)
    alpha=re.search(r'\[PROFILE\] alpha=(\S+)s',text)
    result=dict(assembly=float(p[1]),pointfactor_rhs=float(p[2]),krylov=float(p[3]),
        candidates=float(p[4]),backtrack=float(back[1]) if back else 0.,
        alpha=float(alpha[1]) if alpha else 0.)
    if score:
        result['score_per_eval_ms']=dict(n=int(score[1]),pass1_backsub=float(score[2]),
            copy_neg=float(score[3]),retract=float(score[4]),cost=float(score[5]))
    return result


def run(reg,cell,rep):
    cid=cell['cell'];folder=P/'evidence'/'b0'/f'{cid}-{rep}'
    result_path=folder/'result.json'
    if result_path.exists():return json.loads(result_path.read_text())
    folder.mkdir(parents=True,exist_ok=True)
    assert sha(cell['path'])==cell['input_sha256']
    fd,name=tempfile.mkstemp(prefix='wave5-b0-',suffix='.state',dir='/dev/shm');os.close(fd)
    state=Path(name)
    env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','CERES_','COLMAP_MFREE','MF_DEBUG'))}
    flags=dict(reg['flags'],OCA_TARGET_COST=str(cell['target']),OCA_MAX_SECONDS=str(cell['cap']))
    env.update(flags)
    cmd=[str(BINARY),'--problem',cell['path'],*CHAMP['cli'],'--csv',str(folder/'curve.csv'),'--state_out',str(state)]
    manifest=dict(command=cmd,flags=flags,cell=cell,rep=rep,binary_sha256=sha(BINARY),
        protocol_sha256=reg['protocol_sha256'])
    write(folder/'manifest.json',manifest)
    start=time.monotonic()
    with open('/tmp/prism_gpu.lock','w') as lock,(folder/'stdout.log').open('w') as out,(folder/'stderr.log').open('w') as err:
        fcntl.flock(lock,fcntl.LOCK_EX)
        rc=subprocess.run(cmd,env=env,stdout=out,stderr=err,timeout=120).returncode
    process_seconds=time.monotonic()-start;text=(folder/'stdout.log').read_text()
    try:
        native=re.search(r'RESULT .*?iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)',text);assert rc==0 and native
        count=re.search(r'MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+) negcurv=(\d+)',text);assert count
        obs=observations(cell['path']);score=float(audit(state,*obs));native_cost=float(native[2])
        assert abs(score-native_cost)/max(1,score)<1e-6
        state_sha=sha(state);profile=parse(text);phase_sum=sum(profile[k] for k in
            ['assembly','pointfactor_rhs','krylov','candidates','backtrack','alpha'])
        curves=list(csv.DictReader(x for x in (folder/'curve.csv').read_text().splitlines() if not x.startswith('#')))
        crossings=[float(x['wall_s']) for x in curves if float(x['cost'])<=cell['target']]
        row=dict(valid=True,cell=cid,scene=cell['scene'],rep=rep,cost=score,native_cost=native_cost,
            native_seconds=float(native[3]),process_seconds=process_seconds,outers=int(native[1]),
            accepts=int(count[1]),rejects=int(count[2]),matvecs=int(count[3]),negcurv=int(count[4]),
            hit=bool(crossings and score<=cell['target']),target_seconds=crossings[0] if crossings else None,
            profile=profile,phase_sum_seconds=phase_sum,
            unaccounted_seconds=float(native[3])-phase_sum,
            state_sha256=state_sha,state_bytes=state.stat().st_size,
            endpoint_retained=False,source=str(folder.relative_to(P)))
    finally:
        state.unlink(missing_ok=True)
    write(result_path,row);print('B0',cid,rep,row['native_seconds'],profile,flush=True)
    return row


def summarize(rows):
    phases=['assembly','pointfactor_rhs','krylov','candidates','backtrack','alpha']
    total={key:sum(r['profile'][key] for r in rows) for key in phases}
    phase_sum=sum(total.values());native=sum(r['native_seconds'] for r in rows)
    cells=[]
    for cid in sorted({r['cell'] for r in rows}):
        group=[r for r in rows if r['cell']==cid]
        med={key:statistics.median(r['profile'][key] for r in group) for key in phases}
        cells.append(dict(cell=cid,runs=len(group),hits=sum(r['hit'] for r in group),
            median_native_seconds=statistics.median(r['native_seconds'] for r in group),
            median_phase_seconds=med,median_matvecs=statistics.median(r['matvecs'] for r in group),
            median_outers=statistics.median(r['outers'] for r in group),
            median_rejects=statistics.median(r['rejects'] for r in group)))
    result=dict(runs=len(rows),all_hits=all(r['hit'] for r in rows),aggregate_seconds=total,
        aggregate_profile_sum=phase_sum,aggregate_native_seconds=native,
        fraction_of_profile_sum={k:v/phase_sum for k,v in total.items()},
        fraction_of_native_seconds={k:v/native for k,v in total.items()},
        aggregate_unaccounted_fraction=(native-phase_sum)/native,cells=cells,
        interpretation='Instrumented diagnostic; explicit synchronizations perturb wall time')
    write(P/'b0-summary.json',result);return result


def main():
    reg=register();rows=[]
    for rep in range(3):
        cells=reg['practical'] if rep%2==0 else list(reversed(reg['practical']))
        for cell in cells:
            rows.append(run(reg,cell,rep));write(P/'b0-results.json',rows)
    print(json.dumps(summarize(rows),indent=2))


if __name__=='__main__':main()
