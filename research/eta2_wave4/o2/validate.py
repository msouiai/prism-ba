#!/usr/bin/env python3
"""Serialized tiny correctness and frozen/off compatibility; no O2 scored grid."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import numpy as np
from reference import projection

P=Path(__file__).resolve().parent
F=P.parent.parent/'eta2_champion'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def toy():
    rng=np.random.default_rng(20260912);nc,npnt=4,24
    centers=np.c_[np.linspace(-.8,.8,nc),np.zeros(nc),np.zeros(nc)]
    truth=np.c_[rng.uniform(-1,1,npnt),rng.uniform(-.6,.6,npnt),rng.uniform(-5,-3,npnt)]
    obs=[]
    for c in range(nc):
        for p in range(npnt):
            y=truth[p]-centers[c];q=projection(y,np.array([800.,-.03,0.]),y[2],1.)[0]+rng.normal(size=2)*.15
            obs.append((c,p,*q))
    initial_x=truth+rng.normal(size=truth.shape)*.07
    initial_t=-centers+rng.normal(size=centers.shape)*.02
    initial_c=np.c_[np.zeros((nc,3)),initial_t,np.full(nc,800.),np.full(nc,-.03),np.zeros(nc)]
    path=P/'build/toy.txt'
    with path.open('w') as out:
        out.write(f'{nc} {npnt} {len(obs)}\n')
        for c,p,u,v in obs:out.write(f'{c} {p} {u:.17g} {v:.17g}\n')
        for x in np.r_[initial_c.ravel(),initial_x.ravel()]:out.write(f'{x:.17g}\n')
    return path


def audit_state(state_path,bal):
    with state_path.open('rb') as f:
        assert f.read(8)==b'PRISMS01'
        nc,npnt,no=np.fromfile(f,dtype='<u8',count=3).astype(int)
        r=np.fromfile(f,dtype='<f8',count=9*nc).reshape(nc,3,3)
        t=np.fromfile(f,dtype='<f8',count=3*nc).reshape(nc,3)
        x=np.fromfile(f,dtype='<f8',count=3*npnt).reshape(npnt,3)
        intr=np.fromfile(f,dtype='<f8',count=3*nc).reshape(3,nc).T
    with bal.open() as f:
        f.readline();obs=np.array([[float(v) for v in f.readline().split()] for _ in range(no)])
    ci,pi=obs[:,0].astype(int),obs[:,1].astype(int)
    y=np.einsum('nij,nj->ni',r[ci],x[pi])+t[ci]
    residual=projection(y,intr[ci],y[:,2],1.)[0]-obs[:,2:]
    return float(.5*np.sum(residual*residual))


def main():
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--compat-only',action='store_true');ap.add_argument('--edge-only',action='store_true');args=ap.parse_args()
    cfg=json.loads((F/'champion.json').read_text());baseline=Path('/tmp/prism-rl-actor/build/prism-tr')
    assert sha(baseline)==cfg['binary_sha256']
    build=json.loads((P/'build_manifest.json').read_text());binary=P/'build/prism-o2'
    assert sha(binary)==build['binary_sha256']
    subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
    out=P/'validation';out.mkdir(exist_ok=True)
    if not args.edge_only and (P/'validation_manifest.json').exists():
        i=0
        while (out/f'prior-manifest-{i}.json').exists():i+=1
        (out/f'prior-manifest-{i}.json').write_bytes((P/'validation_manifest.json').read_bytes())
    clean={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))}
    clean.update(cfg['flags']);clean.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    rows=json.loads((out/'runs.json').read_text()) if args.edge_only and (out/'runs.json').exists() else []
    def run(label,exe,bal,max_iter,flags=None,sanitizer=False,export=False):
        env=clean.copy();env.update(flags or {})
        if exe==binary:
            for suffix in ('wave.json','attempts.json'):
                path=out/(label+'.'+suffix)
                if path.exists():
                    i=0
                    while (out/(label+f'.prior-{i}.'+suffix)).exists():i+=1
                    path.rename(out/(label+f'.prior-{i}.'+suffix))
            env.update(OCA_WAVE_TRACE=str(out/(label+'.wave.json')),
                       OCA_STCG_ATTEMPTS=str(out/(label+'.attempts.json')))
        cmd=[str(exe),'--problem',str(bal),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--lam0','.1','--max_iter',str(max_iter)]
        state=out/(label+'.state')
        if export and state.exists():
            i=0
            while (out/(label+f'.prior-{i}.state')).exists():i+=1
            state.rename(out/(label+f'.prior-{i}.state'))
        if export:cmd+=['--state_out',str(state)]
        if sanitizer:cmd=[shutil.which('compute-sanitizer'),'--tool','memcheck','--error-exitcode','97']+cmd
        logpath=out/(label+'.log')
        if logpath.exists():
            i=0
            while (out/(label+f'.prior-{i}.log')).exists():i+=1
            logpath.rename(out/(label+f'.prior-{i}.log'))
        with logpath.open('w') as log:
            result=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=120)
        text=(out/(label+'.log')).read_text()
        if result.returncode:raise RuntimeError(f'{label} exit={result.returncode}: '+text[-2500:])
        match=re.search(r'RESULT.*?cost=(\S+).*?seconds=(\S+)',text)
        if not match:
            match=re.search(r'RESULT.*?final_cost=(\S+).*?time=(\S+)',text)
        # Preserve raw output even if a reporting format changes.
        values=re.findall(r'RESULT[^\n]+',text)
        row={'label':label,'binary_sha256':sha(exe),'input_sha256':sha(bal),'command':cmd,
             'returncode':result.returncode,'result':values[-1] if values else None,
             'flags':flags or {},'log_sha256':sha(out/(label+'.log'))}
        if exe==binary:
            wave=json.loads((out/(label+'.wave.json')).read_text())
            attempt=json.loads((out/(label+'.attempts.json')).read_text())
            assert len(wave)==len(attempt['rows'])
            for w,a in zip(wave,attempt['rows']):
                assert w['outer']==a['outer'] and w['retry']==a['retry_index']
                assert w['pcg_iterations']==a['pcg_iterations'] and w['accepted']==a['accepted']
                assert w['numeric_repair']==a['numeric_repair'] and w['curvature_cutoff']==a['curvature_cutoff']
                assert w['lambda']>0 and w['tau']>0 and 0<w['eta']<=.5
                assert w['gauge_fraction'] is None and w['top5_fraction'] is None and not w['gauge_measured']
                if w['numeric_repair']:
                    assert w['rho'] is None and w['raw_norm'] is None and not w['observed']
                    assert w['lambda_after']>w['lambda'] and w['cost_stage_before']==w['cost_stage_after']
                    assert w['cost_original_before']==w['cost_original_after']
            row['wave_attempt_parity']=True
            row['trace_rows']=len(wave)
            row['trace_numeric_repairs']=sum(w['numeric_repair'] for w in wave)
            row['wave_sha256']=sha(out/(label+'.wave.json'))
            row['attempts_sha256']=sha(out/(label+'.attempts.json'))
        if sanitizer:
            assert 'ERROR SUMMARY: 0 errors' in text
            row['memcheck_errors']=0
        if export:row['independent_original_cost']=audit_state(state,bal)
        if 'OCA_O2_AUDIT' in (flags or {}):
            row['audit_lines']=re.findall(r'O2_AUDIT[^\n]+',text)
            row['stages_checked']=[float(re.search(r'stage=(\S+)',s).group(1)) for s in row['audit_lines']]
            assert row['stages_checked']==[0,.25,.5,.75,.9,1],row
        rows.append(row);(out/'runs.json').write_text(json.dumps(rows,indent=2)+'\n')
        print(json.dumps(row),flush=True)
    with open('/tmp/prism_gpu.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if args.edge_only:
            tiny=toy();lines=tiny.read_text().splitlines();nc,npnt,no=map(int,lines[0].split())
            for o in range(no):
                c,p=lines[1+o].split()[:2];lines[1+o]=f'{c} {p} 0 0'
            for c in range(nc):lines[1+no+9*c+6]='0'
            zero=P/'build/zero-residual.txt';zero.write_text('\n'.join(lines)+'\n')
            run('target-cap-edge',binary,zero,6,{'OCA_O2':'1','OCA_TARGET_COST':'1'},export=True)
            text=(out/'target-cap-edge.log').read_text()
            assert 'reason=attempt_cap attempts=18 accepts=0' in text
            trace=text.splitlines();hit=next(i for i,x in enumerate(trace) if x.startswith('TARGET reached'))
            assert any('O2_TRANSITION' in x and 'to=1 ' in x for x in trace[:hit])
            assert 'full_objective_entered=1 opening_complete=0 schedule_complete=0' in text
            run('partial-stage-target-edge',binary,zero,1,{'OCA_O2':'1','OCA_TARGET_COST':'1'},export=True)
            text=(out/'partial-stage-target-edge.log').read_text()
            assert 'TARGET reached' not in text and 'full_objective_entered=0' in text
        elif not args.compat_only:
            tiny=toy()
            run('tiny-on-audit',binary,tiny,40,{'OCA_O2':'1','OCA_O2_AUDIT':'1'},True,True)
            run('tiny-off-memcheck',binary,tiny,12,{},True)
        if not args.edge_only:
            bal=Path('/workspace/bal/dubrovnik-88.txt')
            for rep in range(3):
                for arm in (['original','off'] if rep%2==0 else ['off','original']):
                    run(f'compat-{arm}-{rep}',baseline if arm=='original' else binary,bal,600)
    summary={'baseline_sha256':sha(baseline),'candidate_sha256':sha(binary),'rows':rows,
             'source_and_header_identity':True,'gpu_lock':'/tmp/prism_gpu.lock','kind':'correctness_not_performance',
             'edge_checks_passed':args.edge_only or any(r['label']=='partial-stage-target-edge' for r in rows),
             'numeric_continue_trace_checked':any(r.get('wave_attempt_parity') and r.get('trace_numeric_repairs',0)>0 for r in rows),
             'wave_trace_schema':'JSON array; see HANDOFF.md',
             'wave_gauge_measured':False}
    (P/'validation_manifest.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':main()
