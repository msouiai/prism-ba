#!/usr/bin/env python3
"""External BA baselines: CPU-fp64 checked endpoints, native traces labeled."""
import argparse,json,pathlib,re,subprocess
from profile_iterations import sha,score_initial

def main():
 p=argparse.ArgumentParser();p.add_argument('--binary',type=pathlib.Path,required=True);p.add_argument('--kind',choices=['caspar32','ceres'],required=True);p.add_argument('--out',type=pathlib.Path,required=True);p.add_argument('--data',type=pathlib.Path,default=pathlib.Path('/workspace/bal'));p.add_argument('--scenes',nargs='+',required=True);p.add_argument('--reps',type=int,default=3);p.add_argument('--profiles',nargs='+');p.add_argument('--budgets',nargs='+',type=int);p.add_argument('--timeout',type=int,default=3600);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 profiles=a.profiles or (['default'] if a.kind=='caspar32' else ['lm-10000','lm-1','dogleg-10000','dogleg-1']);budgets=a.budgets or ([200,2000] if a.kind=='caspar32' else [600]);binary=str(a.binary.resolve())
 m=dict(kind=a.kind,binary=binary,binary_sha256=sha(binary),profiles=profiles,budgets=budgets,reps=a.reps,scenes=a.scenes,timeout=a.timeout,data_sha256={s:sha(a.data/(s+'.txt')) for s in a.scenes},ranking_cost='CPU fp64 against original double observations',trace_precision='native float diagnostics only' if a.kind=='caspar32' else 'fp64',timing='solve clock; setup excludes file parse; Caspar32 setup includes initial CPU audit',gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version','--format=csv,noheader'],text=True))
 mp=a.out/'preregistered.json'
 if mp.exists():assert json.loads(mp.read_text())==m,'Protocol changed'
 else:mp.write_text(json.dumps(m,indent=2)+'\n')
 for scene in a.scenes:
  initial=score_initial(a.data/(scene+'.txt'))
  for rep in range(1,a.reps+1):
   cells=[(pr,b) for pr in profiles for b in budgets];cells=cells if rep%2 else cells[::-1]
   for profile,budget in cells:
    arm=f'{a.kind}-{profile}-{budget}';stem=a.out/f'{scene}-{arm}-{rep}';lp=stem.with_suffix('.log');jp=stem.with_suffix('.json')
    if jp.exists():continue
    assert sha(binary)==m['binary_sha256'];print('RUN',scene,arm,rep,flush=True)
    if not lp.exists():
     command=['flock','/tmp/prism_gpu.lock','timeout',str(a.timeout),binary,str(a.data/(scene+'.txt'))]
     if a.kind=='caspar32':command += [str(budget),profile]
     else:
      method,radius=profile.split('-');command += [method,str(budget),radius,'8']
     with lp.open('w') as out,stem.with_suffix('.stderr').open('w') as err:r=subprocess.run(command,stdout=out,stderr=err)
     if r.returncode:
      jp.write_text(json.dumps(dict(scene=scene,arm=arm,rep=rep,status='failed',returncode=r.returncode),indent=2)+'\n');print('FAIL',scene,arm,rep,r.returncode,flush=True);continue
    log=lp.read_text();res=re.search(r'RESULT exit=(\d+) iters=(\d+) final_score=(\S+) runtime=(\S+)',log);ini=re.search(r'INITIAL score=(\S+) setup_seconds=(\S+)',log);check=re.search(r'CHECK final_score=(\S+)',log)
    if not (res and ini and check):raise RuntimeError(f'Incomplete log retained: {lp}')
    checked_initial=re.search(r'CHECK_INITIAL score=(\S+)',log)
    trace=[dict(iter=int(i),cost=float(c),wall_s=float(t)) for i,c,t in re.findall(r'TRACE iter=(\d+) cost=(\S+) seconds=(\S+)',log)]
    native=float(res[3]);cost=float(check[1]);row=dict(scene=scene,arm=arm,profile=profile,budget=budget,rep=rep,status='ok',iters=int(res[2]),exit_reason=int(res[1]),cost=cost,native_cost=native,native_cost_relerr=abs(native-cost)/max(1,abs(cost)),seconds=float(res[4]),setup_seconds=float(ini[2]),score_init=float(ini[1]),independent_score_init=initial,data_sha256=m['data_sha256'][scene],trace_native=trace)
    if checked_initial:row['checked_quantized_initial']=float(checked_initial[1]);row['initial_quantization_relerr']=abs(row['checked_quantized_initial']-initial)/max(1,abs(initial))
    if a.kind=='ceres':
     assert abs(float(ini[1])-initial)/max(1,abs(initial))<1e-6
     assert row['native_cost_relerr']<1e-6
     row['trace']=trace
    jp.write_text(json.dumps(row,indent=2)+'\n');print('DONE',scene,arm,rep,cost,row['seconds'],flush=True)
if __name__=='__main__':main()
