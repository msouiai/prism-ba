#!/usr/bin/env python3
"""Capture adjacent frozen states, then run serialized coarse-correction gates."""
import pathlib,os,json,subprocess,fcntl,hashlib,shutil,time
ROOT=pathlib.Path(__file__).resolve().parent
from paths import OUT;OUT.mkdir(exist_ok=True,parents=True)
cfg=json.loads((ROOT.parent/'eta2_champion/champion.json').read_text())
env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','MF_DEBUG','CASPAR_','COLMAP_MFREE'))}|cfg['flags']
shutil.copy2(ROOT/'PROTOCOL.md',OUT/'PROTOCOL.md')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
with open('/tmp/prism_gpu.lock','w') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for scene,outer in [('muell-gba146',11),('muell-gba146',12),('ladybug-598',7),('ladybug-598',8),('final-1936',0)]:
  dest=OUT/f'{scene}-o{outer}';dest.mkdir(exist_ok=True)
  if (dest/'capture_manifest.json').exists():continue
  cmd=[str(ROOT/'build/capture'),'--problem',f'/workspace/bal/{scene}.txt',*cfg['cli']]
  cmd[cmd.index('--max_iter')+1]=str(outer+1)
  flags=env|{'OCA_CG_CAPTURE':str(dest),'OCA_CG_CAPTURE_OUTER':str(outer),'OCA_MAX_SECONDS':'60'}
  print('CAPTURE',scene,outer,flush=True);start=time.monotonic()
  with (dest/'capture.log').open('w') as f:subprocess.run(cmd,env=flags,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=150)
  assert (dest/'bp').exists(), 'registered capture not reached'
  files={p.name:{'size':p.stat().st_size,'sha256':sha(p)} for p in dest.iterdir() if p.is_file()}
  (dest/'capture_manifest.json').write_text(json.dumps({'command':cmd,'flags':{k:v for k,v in flags.items() if k.startswith('OCA_')},'process_seconds':time.monotonic()-start,'binary_sha256':sha(ROOT/'build/capture'),'input_sha256':sha(pathlib.Path(f'/workspace/bal/{scene}.txt')),'files':files},indent=2)+'\n')
 # This exercises an active coarse correction if the predecessor is deep.
 cmd=['compute-sanitizer','--tool','memcheck','--error-exitcode','9',str(ROOT/'build/fixed'),str(OUT/'muell-gba146-o12'),str(OUT/'muell-gba146-o11')]
 print('MEMCHECK coarse',flush=True)
 with (OUT/'coarse-memcheck.log').open('w') as f:subprocess.run(cmd,env=env|{'PRISM_FIXED_REPS':'1'},stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
 for scene,outer,prior in [('muell-gba146',12,11),('ladybug-598',8,7),('final-1936',0,None)]:
  cmd=[str(ROOT/'build/fixed'),str(OUT/f'{scene}-o{outer}')]
  if prior is not None:cmd.append(str(OUT/f'{scene}-o{prior}'))
  print('FIXED',scene,flush=True)
  with (OUT/f'{scene}-fixed.log').open('w') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
print('DONE fixed gate',flush=True)
