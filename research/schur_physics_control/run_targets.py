#!/usr/bin/env python3
"""Short nonlinear screen. Coarse arms remain opt-in and do not alter defaults."""
import pathlib,json,os,subprocess,fcntl,shutil,time
ROOT=pathlib.Path(__file__).resolve().parent
from paths import OUT as BASE_OUT, reference_eta2
OUT=BASE_OUT/'targets';OUT.mkdir(exist_ok=True,parents=True)
cfg=json.loads((ROOT.parent/'eta2_champion/champion.json').read_text())
env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))}|cfg['flags']
binary=ROOT/'build/prism-coarse'
protocol={'phase':'exploratory nonlinear follow-up after fixed-system loss','arms':[0,8,16],'repeats':3,'targets':{'muell-gba146':1946488.746262194,'final-1936':5125687.352261469},'native_cap':12,'outer_cap':600,'reason':'Cheap check whether history across the full nonlinear trajectory differs from the selected adjacent pair; no claim that the failed fixed gate predicts a win.'}
(OUT/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
shutil.copy2(ROOT/'build/solver-manifest.json',OUT/'solver-manifest.json')
def run(name,cmd,flags,timeout=150):
 print(name,flush=True);t=time.monotonic()
 with (OUT/(name+'.log')).open('w') as f:
  p=subprocess.run(cmd,env=flags,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
 (OUT/(name+'.json')).write_text(json.dumps({'command':cmd,'flags':{k:v for k,v in flags.items() if k.startswith('OCA_')},'returncode':p.returncode,'process_seconds':time.monotonic()-t},indent=2)+'\n')
 return p.returncode
with open('/tmp/prism_gpu.lock','w') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for name,binpath in [('parity-frozen',reference_eta2()),('parity-off',str(binary))]:
  cmd=[binpath,'--problem','/workspace/bal/ladybug-49.txt',*cfg['cli']];cmd[cmd.index('--max_iter')+1]='4'
  assert run(name,cmd,env)==0
 import re
 costs=[]
 for label in ['parity-frozen','parity-off']:
  text=(OUT/(label+'.log')).read_text();m=re.findall(r'RESULT .*?final_cost=([\deE.+-]+)',text)
  if not m:m=re.findall(r'Final cost\s*[:=]\s*([\deE.+-]+)',text)
  assert m, 'no final cost in parity log'
  costs.append(float(m[-1]))
 assert abs(costs[0]-costs[1])/costs[0]<1e-8, costs
 cmd=['compute-sanitizer','--tool','memcheck','--error-exitcode','9',str(binary),'--problem','/workspace/bal/muell-gba146.txt',*cfg['cli']]
 cmd[cmd.index('--max_iter')+1]='3'
 assert run('memcheck',cmd,env|{'OCA_COARSE_RANK':'16'},180)==0
 for scene,target in protocol['targets'].items():
  for rep in range(3):
   for rank in protocol['arms'][rep:]+protocol['arms'][:rep]:
    cmd=[str(binary),'--problem',f'/workspace/bal/{scene}.txt',*cfg['cli']]
    flags=env|{'OCA_COARSE_RANK':str(rank),'OCA_TARGET_COST':str(target),'OCA_MAX_SECONDS':'12'}
    # Preserve nonzero exits as failed arms; continue independent arms.
    run(f'{scene}-r{rank}-{rep}',cmd,flags)
print('DONE target screen',flush=True)
