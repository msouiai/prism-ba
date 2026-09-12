#!/usr/bin/env python3
"""Short authorized correctness tests; every GPU run holds the shared lock."""
import argparse,csv,fcntl,hashlib,json,os,re,socket,statistics,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;C=P.parent;F=C.parent/'eta2_champion'
CHAMP=json.loads((F/'champion.json').read_text());sys.path.insert(0,str(F/'bench'))
from audit_prism_state import audit,observations

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(path,x):path.write_text(json.dumps(x,indent=2)+'\n')
def run(cmd,env,folder):
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);print('RUN',folder.name,flush=True);start=time.monotonic()
        with (folder/'stdout.log').open('w') as out,(folder/'stderr.log').open('w') as err:
            result=subprocess.run(cmd,env=env,stdout=out,stderr=err,timeout=180)
        seconds=time.monotonic()-start
    return result.returncode,seconds

def toy_math():
    folder=P/'results/kernel-toy';folder.mkdir(parents=True,exist_ok=True);binary=P/'build/frontload-toy'
    manifest=json.loads((P/'toy_build_manifest.json').read_text());assert sha(binary)==manifest['binary_sha256']
    cmd=['/usr/local/cuda/bin/compute-sanitizer','--tool','memcheck','--leak-check','full','--error-exitcode','91',str(binary)]
    write(folder/'manifest.json',dict(command=cmd,build_manifest=manifest,host=socket.gethostname()))
    rc,seconds=run(cmd,os.environ.copy(),folder);output=(folder/'stdout.log').read_text()+(folder/'stderr.log').read_text()
    ans=dict(returncode=rc,process_seconds=seconds,passed=rc==0 and 'FRONTLOAD_TOY pass=1' in output and 'ERROR SUMMARY: 0 errors' in output)
    write(folder/'result.json',ans);assert ans['passed'],output;print('KERNEL_TOY',ans,flush=True)

def solver(scene,arm,rep,sanitizer=False):
    folder=P/'results'/f'{scene}-{arm}-{rep}';folder.mkdir(parents=True,exist_ok=True)
    original=arm=='original';bm=json.loads((P/'build_manifest.json').read_text())
    binary=Path('/tmp/prism-rl-actor/build/prism-tr') if original else P/'build/prism-frontload'
    expected=CHAMP['binary_sha256'] if original else bm['binary_sha256'];assert sha(binary)==expected
    if not original:assert bm['local_headers']=={name:sha(P/name) for name in bm['local_headers']}
    problem=C/'build/toy.txt' if scene=='toy' else Path('/workspace/bal')/(scene+'.txt')
    flags=dict(CHAMP['flags'],OCA_MAX_SECONDS='60')
    if not original:flags.update(OCA_FRONTLOAD='1' if arm=='on' else '0',OCA_STCG_ATTEMPTS=str(folder/'attempts.json'))
    cli=CHAMP['cli'].copy()
    if scene=='toy':cli[cli.index('--max_iter')+1]='8'
    state=folder/'endpoint.state'
    cmd=[str(binary),'--problem',str(problem),*cli,'--csv',str(folder/'curve.csv'),'--state_out',str(state)]
    # Full leak audits are retained separately: the frozen CLI has 20 inherited
    # allocations. This stage checks native memory accesses with normal memcheck.
    if sanitizer:cmd=['/usr/local/cuda/bin/compute-sanitizer','--tool','memcheck','--error-exitcode','91']+cmd
    env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','CERES_','COLMAP_MFREE','MF_DEBUG'))};env.update(flags)
    write(folder/'manifest.json',dict(scene=scene,arm=arm,rep=rep,command=cmd,flags=flags,input_sha256=sha(problem),
          binary_sha256=expected,build_manifest=None if original else bm,host=socket.gethostname(),scope='Correctness only, no speed verdict'))
    rc,seconds=run(cmd,env,folder);output=(folder/'stdout.log').read_text();err=(folder/'stderr.log').read_text()
    match=re.search(r'RESULT .*?iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)',output)
    counts=re.search(r'MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)',output)
    if rc or not match or not counts:
        ans=dict(passed=False,returncode=rc,process_seconds=seconds,error='native process/result failed');write(folder/'result.json',ans);raise RuntimeError(output+err)
    dims,obs=observations(problem);cost=audit(state,dims,obs);rel=abs(cost-float(match[2]))/max(1,cost)
    initial=list(csv.DictReader(x for x in (folder/'curve.csv').read_text().splitlines() if not x.startswith('#')))[0]
    ans=dict(scene=scene,arm=arm,rep=rep,returncode=rc,process_seconds=seconds,native_seconds=float(match[3]),outers=int(match[1]),
             cost=cost,score_init=float(initial['cost']),accepts=int(counts[1]),rejects=int(counts[2]),matvecs=int(counts[3]),
             cpu_cost_relative_error=rel,state_sha256=sha(state),sanitizer=sanitizer,passed=rel<1e-8)
    if sanitizer:ans['sanitizer_zero_errors']='ERROR SUMMARY: 0 errors' in output+err;ans['passed'] &= ans['sanitizer_zero_errors']
    if not original:
        tr=json.loads((folder/'attempts.json').read_text());ans['attempt_totals']=tr['totals']
        ans['trace_counts_match']=tr['totals']['accepted']==ans['accepts'] and tr['totals']['matvecs']==ans['matvecs'];ans['passed'] &= ans['trace_counts_match']
    if arm=='on':
        linear=[];radius=[]
        for line in output.splitlines():
            if line.startswith('FRONTLOAD_LINEAR '):
                data=dict(x.split('=',1) for x in line.split()[1:]);linear.append(data)
                assert int(data['accepts_before'])<3 and float(data['eta'])==.05
                assert abs(float(data['recursive'])-float(data['fresh']))<1e-7
                assert int(data['depth'])<=int(data['cap'])
            if line.startswith('ATTR_RADIUS '):
                data=dict(x.split('=',1) for x in line.split()[1:]);radius.append(data)
                if int(data['accept']):assert float(data['norm'])<=float(data['radius'])*(1+1e-8)
        assert linear
        ans.update(opening_linear_rows=linear,coherent_attempts=len(linear),handoff_seen='FRONTLOAD_HANDOFF ' in output,
                   accepted_radius_checks=True,frontload_summary=next((line for line in output.splitlines() if line.startswith('FRONTLOAD_SUMMARY ')),None))
        if ans['accepts']>3:assert ans['handoff_seen']
    elif arm=='off':assert 'FRONTLOAD_LINEAR ' not in output and 'FRONTLOAD_CONFIG ' not in output
    write(folder/'result.json',ans);assert ans['passed'],ans
    print('DONE',scene,arm,rep,'cost',cost,'outers',ans['outers'],flush=True);return ans

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['kernel','toy','compatibility']);args=p.parse_args()
    subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
    if args.stage=='kernel':toy_math();return
    if args.stage=='toy':
        rows=[solver('toy',arm,1,True) for arm in ('off','on')];write(P/'results/toy-summary.json',rows);return
    rows=[]
    for rep in range(3):
        for arm in (('original','off') if rep%2==0 else ('off','original')):rows.append(solver('dubrovnik-88',arm,rep))
    a=[x['cost'] for x in rows if x['arm']=='original'];b=[x['cost'] for x in rows if x['arm']=='off'];delta=100*(statistics.median(b)/statistics.median(a)-1)
    report=dict(rows=rows,median_cost_delta_percent=delta,passed=abs(delta)<.15,scope='Source-off compatibility, N3; no timing or bit identity claim')
    write(P/'results/compatibility-summary.json',report);assert report['passed'];print('COMPATIBILITY',delta,flush=True)

if __name__=='__main__':main()
