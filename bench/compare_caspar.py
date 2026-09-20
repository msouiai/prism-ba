#!/usr/bin/env python3
"""Run fixed COLMAP Caspar fp64 budgets against retained Prism controls."""
import argparse, json, pathlib, re, subprocess, time
from profile_iterations import sha, score_initial

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--binary',type=pathlib.Path,required=True)
    ap.add_argument('--out',type=pathlib.Path,required=True)
    ap.add_argument('--data',type=pathlib.Path,default=pathlib.Path('/workspace/bal'))
    ap.add_argument('--scenes',nargs='+',default=['venice-52','ladybug-1197','final-3068','final-4585'])
    ap.add_argument('--reps',type=int,default=3)
    ap.add_argument('--prism-full',type=pathlib.Path,default=pathlib.Path('/workspace/prism-retries/v4-quality-A'))
    ap.add_argument('--prism-largest',type=pathlib.Path,default=pathlib.Path('/workspace/prism-retries/v4-A60'))
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    manifest=dict(binary=str(args.binary.resolve()),binary_sha256=sha(args.binary),
        colmap_commit='ed8080bcf42ef0e42d3f5d0cd21eeff0698dfde8',precision='f64',
        budgets=[200,2000],reps=args.reps,scenes=args.scenes,
        data_sha256={s:sha(args.data/(s+'.txt')) for s in args.scenes},
        settings='COLMAP defaults, fixed principal point, k2=0, all BAL observations, no robust loss',
        prism_controls={'full600':str(args.prism_full.resolve()),'largest60':str(args.prism_largest.resolve())},
        control_reuse='All completed N=3 Prism controls retained. Caspar collected subsequently, not interleaved with Prism.',
        gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version','--format=csv,noheader'],text=True))
    mp=args.out/'preregistered.json'
    if mp.exists():assert json.loads(mp.read_text())==manifest,'Experiment changed'
    else:mp.write_text(json.dumps(manifest,indent=2)+'\n')
    for scene in args.scenes:
        initial=score_initial(args.data/(scene+'.txt'))
        for rep in range(1,args.reps+1):
            for budget in ([200,2000] if rep%2 else [2000,200]):
                stem=args.out/f'{scene}-caspar{budget}-{rep}'
                jp=stem.with_suffix('.json')
                if jp.exists():continue
                assert sha(args.binary)==manifest['binary_sha256']
                lp=stem.with_suffix('.log')
                # Never silently discard a completed repeat on parser/restart errors.
                if lp.exists():
                    log=lp.read_text()
                    if 'RESULT ' not in log:raise RuntimeError(f'Incomplete log retained: {lp}; review before resuming')
                else:
                    print(f'RUN {scene} budget={budget} rep={rep}',flush=True)
                    with lp.open('w') as f,stem.with_suffix('.stderr').open('w') as err:
                        subprocess.run(['flock','/tmp/prism_gpu.lock',str(args.binary.resolve()),str(args.data/(scene+'.txt')),str(budget)],stdout=f,stderr=err,check=True)
                    log=lp.read_text()
                m=re.search(r'RESULT exit=(\d+) iters=(\d+) final_score=(\S+) runtime=(\S+)',log)
                init=re.search(r'INITIAL score=(\S+) setup_seconds=(\S+)',log)
                checked=re.search(r'CHECK final_score=(\S+)',log)
                assert m and init and checked,lp
                final_err=abs(float(checked[1])-float(m[3]))/max(abs(float(m[3])),1)
                assert final_err<1e-6,(scene,final_err)
                err=abs(float(init[1])-initial)/max(abs(initial),1)
                assert err<1e-6,(scene,err,float(init[1]),initial)
                trace=[dict(iter=int(it),cost=float(c),wall_s=float(t),accepted=bool(int(ac)),pcg=int(pc))
                    for it,c,t,ac,pc in re.findall(r'TRACE iter=(\d+) cost=(\S+) seconds=(\S+) accepted=(\d+) pcg=(\d+)',log)]
                assert trace and all(t['cost']>0 for t in trace)
                r=dict(scene=scene,arm=f'caspar{budget}',rep=rep,budget=budget,exit_reason=int(m[1]),iters=int(m[2]),
                    cost=float(m[3]),seconds=float(m[4]),setup_seconds=float(init[2]),
                    independent_score_final=float(checked[1]),score_final_relerr=final_err,
                    score_init=float(init[1]),independent_score_init=initial,score_init_relerr=err,trace=trace,
                    data_sha256=manifest['data_sha256'][scene])
                jp.write_text(json.dumps(r,indent=2)+'\n')
                print(f"DONE {scene} {budget} rep={rep}: cost={r['cost']:.9g} seconds={r['seconds']:.3f} exit={r['exit_reason']}",flush=True)
if __name__=='__main__':main()
