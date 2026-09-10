#!/usr/bin/env python3
import pathlib,json,os,subprocess,fcntl,hashlib,time,sys,argparse

ROOT=pathlib.Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--upgrade',action='store_true');ap.add_argument('--output',type=pathlib.Path,default=pathlib.Path('/workspace/prism-schur-eta2'));ap.add_argument('--data-root',type=pathlib.Path,default=pathlib.Path('/workspace/bal'));ap.add_argument('--baseline',type=pathlib.Path,default=ROOT.parent/'eta2_champion/build/prism-eta2');args=ap.parse_args();upgrade=args.upgrade
OUT=args.output/('targets-upgrade' if upgrade else 'targets');OUT.mkdir(exist_ok=True,parents=True)
cfg=json.loads((ROOT.parent/'eta2_champion/champion.json').read_text())
env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};env.update(cfg['flags'])
protocol={'arms':['hcc','upgrade' if upgrade else 'gram'],'repeats':3,'max_outer':600,'native_seconds':12,'targets':{'muell-gba146':1946488.746262194,'final-1936':5125687.352261469},'selection':'Muell fixed-system native-eta winner; Final1936 registered cheap-solve control. Targets copied unchanged from sustained eta2 protocol. No target tuning.','criterion':'Every hit; >=1.10x Muell median, no >5% slowdown on control for global promotion. Scene-specific wins labeled limited.'}
protocol['upgrade']=dict(enabled=upgrade,after_iterations=8,method='Preserve x; recompute true residual; restart with Schur Gram, same operator, forcing tolerance and total128 CG cap. Extra matvec charged. Follow-up chosen after always-on failure, not an independent holdout.')
(OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
(OUT/'solver_manifest.json').write_text((ROOT/'build/solver_manifest.json').read_text())
with open('/tmp/prism_gpu.lock','w') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 # Baseline compatibility when off; objective parity is checked in summarize.py.
 for label,binary in [('frozen',str(args.baseline)),('off',str(ROOT/'build/prism-gram'))]:
  cmd=[binary,'--problem',str(args.data_root/'ladybug-49.txt'),*cfg['cli']];cmd[cmd.index('--max_iter')+1]='4'
  with (OUT/f'parity-{label}.log').open('w') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=60)
 # Check the new kernel in the integrated solver before timing.
 cmd=['compute-sanitizer','--tool','memcheck','--error-exitcode','9',str(ROOT/'build/prism-gram'),'--problem',str(args.data_root/'ladybug-49.txt'),*cfg['cli']];cmd[cmd.index('--max_iter')+1]='4'
 if upgrade:
  cmd[cmd.index('--problem')+1]=str(args.data_root/'ladybug-598.txt');cmd[cmd.index('--max_iter')+1]='8'
 with (OUT/'memcheck.log').open('w') as f:subprocess.run(cmd,env=env|{'OCA_PCG_GRAM':'2' if upgrade else '1'},stdout=f,stderr=subprocess.STDOUT,check=True,timeout=120)
 for scene,target in protocol['targets'].items():
  for rep in range(3):
   for arm in (protocol['arms'] if rep%2==0 else list(reversed(protocol['arms']))):
    flags=env|{'OCA_TARGET_COST':str(target),'OCA_MAX_SECONDS':'12','OCA_PCG_GRAM':str(2 if arm=='upgrade' else int(arm=='gram'))}
    stem=f'{scene}-{arm}-{rep}';cmd=[str(ROOT/'build/prism-gram'),'--problem',str(args.data_root/f'{scene}.txt'),*cfg['cli']]
    print(stem,flush=True);start=time.monotonic()
    with (OUT/f'{stem}.log').open('w') as f:p=subprocess.run(cmd,env=flags,stdout=f,stderr=subprocess.STDOUT,timeout=120)
    (OUT/f'{stem}.json').write_text(json.dumps({'command':cmd,'flags':{k:v for k,v in flags.items() if k.startswith('OCA_')},'returncode':p.returncode,'process_wall_seconds':time.monotonic()-start,'target':target},indent=2))
    assert p.returncode==0
print('DONE',flush=True)
