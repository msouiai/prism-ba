#!/usr/bin/env python3
"""Run pre-registered eta2 captures and fixed-system PCG tests under a GPU lock."""
import pathlib,subprocess,json,os,fcntl,hashlib,time,argparse
ROOT=pathlib.Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--output',type=pathlib.Path,default=pathlib.Path('/workspace/prism-schur-eta2'));ap.add_argument('--data-root',type=pathlib.Path,default=pathlib.Path('/workspace/bal'));ap.add_argument('--baseline',type=pathlib.Path,default=ROOT.parent/'eta2_champion/build/prism-eta2');args=ap.parse_args()
OUT=args.output;OUT.mkdir(exist_ok=True)
pkg=ROOT.parent/'eta2_champion';cfg=json.loads((pkg/'champion.json').read_text())
env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};env.update(cfg['flags'])
with open('/tmp/prism_gpu.lock','w') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 # An invalid menu width must reject, never silently benchmark a different arm.
 command=[str(args.baseline),'--problem',str(args.data_root/'ladybug-49.txt'),*cfg['cli']]
 bad=env|{'OCA_NSHIFTS':'5'}
 p=subprocess.run(command,env=bad,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=120)
 (OUT/'nshifts5-rejection.log').write_text(p.stdout)
 assert p.returncode!=0 and 'classical LM requires' in p.stdout
 for scene,outer in [('muell-gba146',12),('ladybug-598',8),('final-1936',0)]:
  dest=OUT/scene;dest.mkdir(exist_ok=True)
  command=[str(ROOT/'build/capture'),'--problem',str(args.data_root/f'{scene}.txt'),*cfg['cli']]
  command[command.index('--max_iter')+1]=str(outer+1)
  capture_env=env|{'OCA_CG_CAPTURE':str(dest),'OCA_CG_CAPTURE_OUTER':str(outer),'OCA_MAX_SECONDS':'60'}
  print('capture',scene,outer,flush=True)
  with (dest/'capture.log').open('w') as f:subprocess.run(command,env=capture_env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=150)
  assert (dest/'dimensions.txt').exists(), 'registered state not reached; do not substitute silently'
  files={}
  for path in dest.iterdir():
   if path.is_file():
    with path.open('rb') as f:files[path.name]={'size':path.stat().st_size,'sha256':hashlib.file_digest(f,'sha256').hexdigest()}
  with open(str(args.data_root/f'{scene}.txt'),'rb') as f:inputsha=hashlib.file_digest(f,'sha256').hexdigest()
  (dest/'capture_manifest.json').write_text(json.dumps({'command':command,'flags':{k:v for k,v in capture_env.items() if k.startswith('OCA_')},'input_sha256':inputsha,'files':files},indent=2))
  print('fixed benchmark',scene,flush=True)
  with (dest/'fixed.log').open('w') as f:subprocess.run([str(ROOT/'build/fixed'),str(dest)],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
print('DONE',flush=True)
