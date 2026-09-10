#!/usr/bin/env python3
"""Bounded, rotated A/B/S cache probe; records each run, never infers full-run wins."""
import argparse
import csv
import json
import os
from pathlib import Path
import re
import subprocess
from profile_iterations import sha, score_initial

COMMON = dict(OCA_FORCE_UNSHARED='1', OCA_RHO_LAMBDA='1', OCA_GRID_DOWN='2',
              OCA_RHO_SHIFT='1', OCA_ALPHA_RHO='1', OCA_MENU_GATE='1e-2',
              OCA_FTOL='1e-5', OCA_FTOL_K='8', OCA_NSHIFTS='5')
CONFIGS = {
    'A': dict(OCA_TAU_LAM='1', OCA_TAU_LAM_RATCHET='1'),
    'B': dict(OCA_TAU_LAM='1', OCA_TAU_LAM_RATCHET='1',
              OCA_TAU_LAM_COND='0.2', OCA_RETRY_SPAN='3'),
    'S': dict(OCA_RETRI='5', OCA_TAU_LAM='10',
              OCA_TAU_LAM_ANNEAL='0.8', OCA_RETRY_SPAN='3'),
}
ARMS = {'reference': {}, 'cache': {'OCA_RETRY_CACHE':'1'},
        'optimized': dict(OCA_RETRY_CACHE='1', OCA_MULTI_RHS='1', OCA_DIAG_NORM='1')}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--binary', type=Path, required=True)
    ap.add_argument('--data', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--configs', nargs='+', choices=CONFIGS, default=['A','B','S'])
    ap.add_argument('--arms', nargs='+', choices=ARMS, default=['cache'])
    ap.add_argument('--scenes', nargs='+', default=['ladybug-1197'])
    ap.add_argument('--reps', type=int, default=3)
    ap.add_argument('--max-iter', type=int, default=15)
    ap.add_argument('--timeout', type=float, default=900)
    ap.add_argument('--trace', action='store_true', help='host-only per-attempt damping/cache log')
    a = ap.parse_args()
    if min(a.reps, a.max_iter, a.timeout) <= 0: ap.error('budgets must be positive')
    a.binary = a.binary.resolve()
    a.out.mkdir(parents=True, exist_ok=False)  # never overwrite or silently reuse a run
    inputs = {s: {'sha256':sha(a.data/(s+'.txt')), 'initial_cost':score_initial(a.data/(s+'.txt'))}
              for s in a.scenes}
    flags = set(COMMON)
    for c in a.configs: flags.update(CONFIGS[c])
    for arm in a.arms: flags.update(ARMS[arm])
    if a.trace: flags.add('OCA_RETRY_CACHE_TRACE')
    binary = a.binary.read_bytes()
    missing = [k for k in flags if k.encode()+b'\0' not in binary]
    if missing: raise RuntimeError(f'Binary missing flags: {missing}')
    manifest = dict(binary=str(a.binary), binary_sha256=sha(a.binary), inputs=inputs,
                    common=COMMON, configs={c:CONFIGS[c] for c in a.configs},
                    arms={arm:ARMS[arm] for arm in a.arms}, reps=a.reps,
                    max_iter=a.max_iter, timeout=a.timeout, trace=a.trace,
                    gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version',
                                                 '--format=csv,noheader'],text=True).strip())
    (a.out/'preregistered.json').write_text(json.dumps(manifest,indent=2)+'\n')
    env0 = {k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))}
    cells = [(s,c,arm) for s in a.scenes for c in a.configs for arm in a.arms]
    rows = []
    for rep in range(a.reps):
        rotated = cells[rep%len(cells):]+cells[:rep%len(cells)]
        for scene, config, arm in rotated:
            if sha(a.binary)!=manifest['binary_sha256']: raise RuntimeError('Binary changed')
            stem = a.out/f'{scene}-{config}-{arm}-{rep+1}'
            env = dict(env0, **COMMON); env.update(CONFIGS[config]); env.update(ARMS[arm])
            if a.trace: env['OCA_RETRY_CACHE_TRACE']='1'
            command = ['flock','/tmp/prism_gpu.lock','timeout',str(a.timeout),str(a.binary),
                       '--problem',str((a.data/(scene+'.txt')).resolve()),'--algo','mfree_shifted_cg',
                       '--dof9','--zero_k2','--max_iter',str(a.max_iter),'--csv',str(stem.with_suffix('.csv'))]
            print('RUN',scene,config,arm,rep+1,flush=True)
            with stem.with_suffix('.log').open('w') as out, stem.with_suffix('.stderr').open('w') as err:
                rc = subprocess.run(command,env=env,stdout=out,stderr=err).returncode
            log = stem.with_suffix('.log').read_text()
            row = dict(scene=scene, config=config, arm=arm, rep=rep+1, returncode=rc, command=command)
            m = re.search(r'RESULT .*?iters=(\d+) final_cost=([\d.e+-]+) solve_seconds=([\d.e+-]+)',log)
            counts = re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+).*?cand_evals=(\d+)',log)
            cache = re.search(r'\[retry-cache\] ([^\n]+)',log)
            init = re.search(r'MFCG score_init=([\d.e+-]+)',log)
            if m and counts and init:
                row.update(outers=int(m[1]), final_cost=float(m[2]), native_seconds=float(m[3]),
                           accepts=int(counts[1]), rejects=int(counts[2]), matvecs=int(counts[3]),
                           menu_evals=int(counts[4]), initial_cost=float(init[1]), cap_hit=int(m[1])>=a.max_iter)
                row['initial_relative_error']=abs(float(init[1])-inputs[scene]['initial_cost'])/max(1,abs(inputs[scene]['initial_cost']))
                row['valid']=rc==0 and row['initial_relative_error']<=1e-6
            else: row['valid']=False
            if cache:
                row['cache']={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',cache[1])}
                row['hit_fraction']=row['cache']['reuses']/max(1,row['cache']['builds']+row['cache']['reuses'])
            row['timing_note']='Bounded solve time, not time to a pre-registered quality target.'
            stem.with_suffix('.json').write_text(json.dumps(row,indent=2)+'\n')
            rows.append(row)
            (a.out/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
            print('DONE',json.dumps(row),flush=True)
            if not row['valid']: raise RuntimeError(f'Invalid run retained: {stem}')

if __name__=='__main__': main()
