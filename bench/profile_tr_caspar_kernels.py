#!/usr/bin/env python3
"""Separate CUDA tracing runs; never use their wall times as benchmark results."""
import pathlib,subprocess,os,json
ROOT=pathlib.Path('/workspace/prism-tr-mixed')
NSYS='/opt/nvidia/nsight-compute/2025.1.1/host/target-linux-x64/nsys'
def main():
 for scene,target,cap in [('final-1936',5074937.9725361075,12),('final-13682',27318392.631312046,20)]:
  stem=ROOT/(scene+'-caspar32-nsys')
  env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))}
  env.update(CASPAR_TARGET_COST=str(target*(1-1e-8)*.999),CASPAR_MAX_SECONDS=str(cap),CASPAR_STATE_OUT=str(stem)+'.state')
  cmd=['flock','/tmp/prism_gpu.lock','timeout','180',NSYS,'profile','--trace=cuda','--sample=none','--cpuctxsw=none','--output='+str(stem),'/workspace/prism-caspar-current/caspar32','/workspace/bal/'+scene+'.txt','100000','default']
  stem.with_suffix('.manifest.json').write_text(json.dumps(dict(command=cmd,flags={k:v for k,v in env.items() if k.startswith('CASPAR_')},note='Instrumented kernel attribution only; FP32 native stop margin .1%, original certification target unchanged'),indent=2))
  with stem.with_suffix('.log').open('x') as f,stem.with_suffix('.stderr').open('x') as e:r=subprocess.run(cmd,env=env,stdout=f,stderr=e)
  print(scene,'profile',r.returncode,flush=True)
  if r.returncode==0:
   with stem.with_suffix('.kernels.csv').open('x') as f:subprocess.run([NSYS,'stats','--report=cuda_gpu_kern_sum','--format=csv',str(stem)+'.nsys-rep'],stdout=f,check=True)
if __name__=='__main__':main()
