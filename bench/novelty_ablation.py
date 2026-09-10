#!/usr/bin/env python3
"""Fresh four-way frozen Prism ablation; retains complete and failed runs."""
import argparse,csv,json,os,pathlib,re,subprocess,time
from profile_iterations import COMMON,sha,score_initial
ARMS={'A-single':{'OCA_NSHIFTS':'1'},'B-single-guarded':{'OCA_NSHIFTS':'1','OCA_MENU_BACKTRACK':'8'},'C-multi':{'OCA_NSHIFTS':'5'},'D-multi-guarded':{'OCA_NSHIFTS':'5','OCA_MENU_BACKTRACK':'8'}}
EXEC={'OCA_RETRY_CACHE':'1','OCA_MULTI_RHS':'1','OCA_DIAG_NORM':'1'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--binary',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);p.add_argument('--data',type=pathlib.Path,default=pathlib.Path('/workspace/bal'));p.add_argument('--scenes',nargs='+',required=True);p.add_argument('--reps',type=int,default=3);p.add_argument('--max-iter',type=int,default=600);p.add_argument('--timeout',type=int,default=3600);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 binary=str(a.binary.resolve());bb=a.binary.read_bytes()
 for flag in set(COMMON)|set(EXEC)|{'OCA_NSHIFTS','OCA_MENU_BACKTRACK'}:assert flag.encode()+b'\0' in bb,flag
 m=dict(binary=binary,binary_sha256=sha(binary),common=COMMON,execution=EXEC,arms=ARMS,scenes=a.scenes,reps=a.reps,max_iter=a.max_iter,timeout=a.timeout,data_sha256={s:sha(a.data/(s+'.txt')) for s in a.scenes},gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version','--format=csv,noheader'],text=True))
 mp=a.out/'preregistered.json'
 if mp.exists():assert json.loads(mp.read_text())==m,'Protocol changed'
 else:mp.write_text(json.dumps(m,indent=2)+'\n')
 for scene in a.scenes:
  initial=score_initial(a.data/(scene+'.txt'))
  for rep in range(1,a.reps+1):
   order=list(ARMS);j=(rep-1)%4;order=order[j:]+order[:j]
   for arm in order:
    stem=a.out/f'{scene}-{arm}-{rep}';jp=stem.with_suffix('.json');lp=stem.with_suffix('.log')
    if jp.exists():continue
    assert sha(binary)==m['binary_sha256']
    print('RUN',scene,arm,rep,flush=True)
    if not lp.exists():
     env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','COLMAP_MFREE','MF_DEBUG'))};env.update(COMMON);env.update(EXEC);env.update(ARMS[arm])
     command=['flock','/tmp/prism_gpu.lock','timeout',str(a.timeout),binary,'--problem',str(a.data/(scene+'.txt')),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter',str(a.max_iter),'--csv',str(stem.with_suffix('.csv'))]
     with lp.open('w') as out,stem.with_suffix('.stderr').open('w') as err:r=subprocess.run(command,env=env,stdout=out,stderr=err)
     if r.returncode:
      jp.write_text(json.dumps(dict(scene=scene,arm=arm,rep=rep,status='failed',returncode=r.returncode),indent=2)+'\n');print('FAIL',scene,arm,rep,r.returncode,flush=True);continue
    log=lp.read_text();match=re.search(r'RESULT .*?iters=(\d+) final_cost=([\d.e+-]+) solve_seconds=([\d.e+-]+)',log)
    if not match:raise RuntimeError(f'Incomplete log retained: {lp}')
    with stem.with_suffix('.csv').open() as f:trace=list(csv.DictReader(line for line in f if not line.startswith('#')))
    actual=float(trace[0]['cost']);rel=abs(actual-initial)/max(1,abs(initial));assert rel<1e-6,(scene,rel)
    counts=re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+).*?cand_evals=(\d+)',log);assert counts
    row=dict(scene=scene,arm=arm,rep=rep,status='ok',iters=int(match[1]),cost=float(match[2]),seconds=float(match[3]),score_init=actual,independent_score_init=initial,score_init_relerr=rel,accepts=int(counts[1]),rejects=int(counts[2]),matvecs=int(counts[3]),menu_evals=int(counts[4]),trace=trace,data_sha256=m['data_sha256'][scene])
    extra=re.search(r'\[menu-backtrack\] trials=(\d+) rescues=(\d+) evals=(\d+).*?total_scored=(\d+)',log)
    if extra:row.update(backtrack_trials=int(extra[1]),backtrack_rescues=int(extra[2]),backtrack_evals=int(extra[3]))
    alpha=re.search(r'alpha_evals=(\d+)',log);row['alpha_evals']=int(alpha[1]) if alpha else 0;row['total_scored']=row['menu_evals']+row['alpha_evals']+row.get('backtrack_evals',0)
    jp.write_text(json.dumps(row,indent=2)+'\n');print('DONE',scene,arm,rep,row['cost'],row['seconds'],flush=True)
if __name__=='__main__':main()
