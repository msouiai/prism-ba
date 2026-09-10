#!/usr/bin/env python3
"""Seven-outer attribution run, never a benchmark timing."""
import json,pathlib,os,subprocess
root=pathlib.Path('/workspace/prism-tr-fp32-products/profile');root.mkdir();stem=root/'final-13682';m=json.load(open('/workspace/prism-tr-fp32-products/large/final-13682-tr.manifest.json'))
env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};env.update(m['flags'],OCA_PROFILE='1',OCA_CG_STOP_TRACE='1',OCA_FP32_RESIDUAL_AUDIT='1')
nsys='/opt/nvidia/nsight-compute/2025.1.1/host/target-linux-x64/nsys';args=m['command'][4:];args[args.index('--max_iter')+1]='7';args[-1]=str(stem)+'.state'
cmd=['flock','/tmp/prism_gpu.lock','timeout','180',nsys,'profile','--trace=cuda','--sample=none','--cpuctxsw=none','--output='+str(stem)]+args
(root/'manifest.json').write_text(json.dumps(dict(command=cmd,flags={k:v for k,v in env.items() if k.startswith('OCA_')},binary_sha256=m['binary_sha256'],input_sha256=m['input_sha256'],scope='Instrumented seven outer iterations; kernel and model attribution only, not equal-quality comparison.'),indent=2))
with open(str(stem)+'.log','x') as f,open(str(stem)+'.stderr','x') as e:r=subprocess.run(cmd,env=env,stdout=f,stderr=e)
print('profile return',r.returncode,flush=True)
if r.returncode==0:
 with open(str(stem)+'.kernels.csv','x') as f:subprocess.run([nsys,'stats','--force-export=true','--report=cuda_gpu_kern_sum','--format=csv',str(stem)+'.nsys-rep'],stdout=f,check=True)
print('done',flush=True)
