#!/usr/bin/env python3
"""Run the pre-registered, read-only terminal relaxation diagnostic."""
import pathlib,os,json,subprocess,fcntl,time,re,shutil,argparse
ROOT=pathlib.Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--extended',action='store_true');args=ap.parse_args()
suffix='-extended' if args.extended else ''
from paths import OUT as BASE_OUT, reference_eta2
OUT=BASE_OUT/('relaxation'+suffix);OUT.mkdir(exist_ok=True,parents=True)
base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))}
cfg=json.loads((ROOT.parent/'eta2_champion/champion.json').read_text())
v2flags={'OCA_RHO_LAMBDA':'1','OCA_GRID_DOWN':'2','OCA_RHO_SHIFT':'1','OCA_ALPHA_RHO':'1'}
v2cli=['--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter','60','--lam0','10.0','--tau_pt','3e-3','--func-tol','1e-6','--max-consec-fail','3']
champcli=cfg['cli'].copy();champcli[champcli.index('--max_iter')+1]='60'
arms={'v2':(v2cli,v2flags),'eta2':(champcli,cfg['flags'])}
shutil.copy2(ROOT/('EXTENDED_PROBE_PROTOCOL.md' if args.extended else 'RELAXATION_PROTOCOL.md'),OUT/'PROTOCOL.md')
for arm in arms:shutil.copy2(ROOT/f'build/probe-{arm}{suffix}/manifest.json',OUT/f'{arm}-manifest.json')
def run(stem,cmd,flags,timeout=30):
    print(stem,flush=True);t=time.monotonic();path=OUT/(stem+'.log')
    with path.open('w') as f:
        try:rc=subprocess.run(cmd,env=base|flags,stdout=f,stderr=subprocess.STDOUT,timeout=timeout).returncode
        except subprocess.TimeoutExpired:rc=124
    text=path.read_text();m=re.search(r'RESULT algo=\S+ iters=(\d+) final_cost=([\deE.+-]+) solve_seconds=([\deE.+-]+)',text)
    row={'name':stem,'command':cmd,'flags':flags,'returncode':rc,'process_seconds':time.monotonic()-t,'stop_messages':[l.strip() for l in text.splitlines() if 'converged (' in l or 'stop:' in l]}
    if m:row.update(outers=int(m[1]),cost=float(m[2]),seconds=float(m[3]))
    row['diagnostics']=[dict(kind=l.split()[0],**dict(x.split('=',1) for x in l.split()[1:])) for l in text.splitlines() if l.startswith(('RELAX_PROBE ','RELAX_TRIAL ','RELAX_CURVATURE ','GRAD_AUDIT phase=terminal'))]
    path.with_suffix('.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps(row.get('diagnostics',[])[-1:]),flush=True)
    return row
with open('/tmp/prism_gpu.lock','w') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    for arm,(cli,flags) in arms.items():
        short=cli.copy();short[short.index('--max_iter')+1]='4'
        new=str(ROOT/f'build/probe-{arm}{suffix}/probe')
        original='/workspace/multishift_repro/oca_cuda_v2' if arm=='v2' else reference_eta2()
        rows=[run(f'parity-{arm}-{label}',[binary,'--problem','/workspace/bal/ladybug-49.txt',*short],flags) for label,binary in [('original',original),('off',new)]]
        assert all(r['returncode']==0 for r in rows)
        assert abs(rows[0]['cost']-rows[1]['cost'])/rows[0]['cost']<1e-7
        row=run('memcheck-'+arm,['compute-sanitizer','--tool','memcheck','--error-exitcode','9',new,'--problem','/workspace/bal/ladybug-49.txt',*short],flags|{'OCA_GRAD_AUDIT':'1','OCA_RELAX_PROBE':'1'},120)
        assert row['returncode']==0 and row['diagnostics'][-1]['state_changed']=='0'
        assert float(row['diagnostics'][-1]['derivative_relative_error'])<1e-3
    for rep in range(3):
        for arm in (['v2','eta2'] if rep%2==0 else ['eta2','v2']):
            cli,flags=arms[arm]
            run(f'{arm}-{rep:02}',[str(ROOT/f'build/probe-{arm}{suffix}/probe'),'--problem','/workspace/bal/final-3068.txt',*cli],flags|{'OCA_GRAD_AUDIT':'1','OCA_RELAX_PROBE':'1'})
print('DONE terminal relaxation probe',flush=True)
