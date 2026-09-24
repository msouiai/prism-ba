#!/usr/bin/env python3
"""One audited Muell development run of the existing on-the-fly-Jacobian path."""
import hashlib,json,math,os,pathlib,re,subprocess,sys,time
ROOT=pathlib.Path('/workspace/prism-fast-start/explore-jit');ROOT.mkdir(exist_ok=True)
BIN=pathlib.Path('/workspace/prism-fast-start/build/prism-tr');DATA=pathlib.Path('/workspace/bal/muell-gba146.txt');TARGET=1946488.746262194
sys.path.insert(0,'/workspace/prism-ba/bench');from cached_benchmark_input import load_input;from audit_prism_state import audit
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def put(p,x):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n');t.replace(p)
stem=ROOT/'muell-jit-1';rp=stem.with_suffix('.result.json')
if rp.exists():print(rp.read_text());raise SystemExit
dh,(dims,obs),initial=load_input(DATA,ROOT.parent/'cpu_cache');flags=json.load(open('/workspace/prism-model-followup/selected_candidate.json'))['flags']
env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE_','MF_DEBUG'))};env.update(flags,OCA_JIT_J='1',OCA_TARGET_COST=str(TARGET),OCA_MAX_SECONDS='90')
cmd=['flock','/tmp/prism_gpu.lock','timeout','180',str(BIN),'--problem',str(DATA),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--lam0','0.1','--max_iter','600','--csv',str(stem.with_suffix('.csv')),'--state_out',str(stem.with_suffix('.state')),'--mf-json',str(stem.with_suffix('.jsonl'))]
put(stem.with_suffix('.manifest.json'),dict(scope='One development diagnostic only. JIT recomputes per-observation Jacobians inside the Schur matvec; it keeps the original full cost acceptance and target.',command=cmd,flags={k:v for k,v in env.items() if k.startswith('OCA_')},target=TARGET,binary_sha256=sha(BIN),source_sha256=sha('/workspace/prism-fast-start/build/source.cu'),data_sha256=dh,initial_cpu_fp64_cost=initial))
t=time.monotonic()
with open(str(stem)+'.log','x') as out,open(str(stem)+'.stderr','x') as err:r=subprocess.run(cmd,env=env,stdout=out,stderr=err)
row=dict(returncode=r.returncode,wall_seconds=time.monotonic()-t,target=TARGET,binary_sha256=sha(BIN),data_sha256=dh)
if r.returncode==0:
 text=pathlib.Path(str(stem)+'.log').read_text();m=re.search(r'RESULT .*?iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)',text);q=re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+) negcurv=(\d+) cand_evals=(\d+)',text);x=re.search(r'TARGET reached outer=(\d+) seconds=(\S+)',text)
 assert m and q;cost=audit(stem.with_suffix('.state'),dims,obs);err_rel=abs(cost-float(m[2]))/max(1,cost);assert math.isfinite(cost) and err_rel<1e-7
 row.update(outers=int(m[1]),native_cost=float(m[2]),seconds=float(m[3]),audit_cpu_fp64_cost=cost,audit_error=err_rel,crossing_seconds=float(x[2]) if x else None,accepts=int(q[1]),rejects=int(q[2]),matvecs=int(q[3]),candidate_evals=int(q[5]),hit=bool(x and cost<=TARGET))
put(rp,row);print(json.dumps(row,indent=2,sort_keys=True))
