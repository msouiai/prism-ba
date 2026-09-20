#!/usr/bin/env python3
"""One eight-outer kernel-level diagnostic profile; never a timing benchmark."""
import hashlib,json,os,pathlib,re,subprocess,sys,time
ROOT=pathlib.Path('/workspace/prism-fast-start/nsys');ROOT.mkdir(exist_ok=True)
BIN=pathlib.Path('/workspace/prism-fast-start/build/prism-tr');DATA=pathlib.Path('/workspace/bal/muell-gba146.txt')
NSYS=pathlib.Path('/opt/nvidia/nsight-compute/2025.1.1/host/target-linux-x64/nsys');stem=ROOT/'muell-first8'
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def put(p,x):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n');t.replace(p)
if (stem.with_suffix('.result.json')).exists():print((stem.with_suffix('.result.json')).read_text());raise SystemExit
flags=json.load(open('/workspace/prism-model-followup/selected_candidate.json'))['flags']
env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE_','MF_DEBUG'))};env.update(flags,OCA_MAX_SECONDS='60',OCA_PROFILE='1')
binary_cmd=[str(BIN),'--problem',str(DATA),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--lam0','0.1','--max_iter','8','--csv',str(stem.with_suffix('.csv')),'--state_out',str(stem.with_suffix('.state')),'--mf-json',str(stem.with_suffix('.jsonl'))]
cmd=['flock','/tmp/prism_gpu.lock','timeout','180',str(NSYS),'profile','--force-overwrite=true','--trace=cuda','--sample=none','--cpuctxsw=none','--cuda-memory-usage=false','--output='+str(stem),*binary_cmd]
put(stem.with_suffix('.manifest.json'),dict(scope='Kernel-level diagnostic only: current guarded binary, exactly eight outer iterations, Nsys instrumentation. No timing claim.',command=cmd,flags={k:v for k,v in env.items() if k.startswith('OCA_')},binary_sha256=sha(BIN),source_sha256=sha('/workspace/prism-fast-start/build/source.cu'),data_sha256=sha(DATA)))
t=time.monotonic()
with open(str(stem)+'.log','x') as out,open(str(stem)+'.stderr','x') as err:r=subprocess.run(cmd,env=env,stdout=out,stderr=err)
row=dict(returncode=r.returncode,wall_seconds=time.monotonic()-t)
if r.returncode==0:
 text=pathlib.Path(str(stem)+'.log').read_text();m=re.search(r'RESULT .*?iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)',text);q=re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+).*?cand_evals=(\d+)',text)
 assert m and q;row.update(outers=int(m[1]),native_cost=float(m[2]),solve_seconds=float(m[3]),accepts=int(q[1]),rejects=int(q[2]),matvecs=int(q[3]),candidate_evals=int(q[4]),report=str(stem)+'.nsys-rep')
put(stem.with_suffix('.result.json'),row);print(json.dumps(row,indent=2,sort_keys=True))
