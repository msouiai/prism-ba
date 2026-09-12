"""O1 native memory/endpoint and frozen-off compatibility gates (not timings)."""
from pathlib import Path
import fcntl,hashlib,json,os,re,statistics,subprocess,sys
P=Path(__file__).resolve().parent;sys.path.insert(0,str(P/'o2'))
from validate import audit_state
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 cfg=json.loads((P.parent/'eta2_champion/champion.json').read_text());bm=json.loads((P/'o1_build_manifest.json').read_text());binary=P/'build/prism-o1'
 assert sha(binary)==bm['binary_sha256']
 kernels=json.loads((P/'o1-kernel-validation.json').read_text());assert kernels['passed'] and kernels['header_sha256']==sha(P/'o1.cuh')
 out=P/'o1-validation';out.mkdir(exist_ok=True)
 env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','CERES_'))};env.update(cfg['flags']);env.update(OCA_O1_SWEEPS='3',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
 bal=P/'o2/build/toy.txt';state=out/'tiny.state';log=out/'tiny.log';assert not log.exists()
 cmd=['compute-sanitizer','--tool','memcheck','--error-exitcode','97',str(binary),'--problem',str(bal),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--lam0','.1','--max_iter','40','--state_out',str(state)]
 with open('/tmp/prism_gpu.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  with log.open('w') as f:r=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180)
 text=log.read_text();assert r.returncode==0 and 'ERROR SUMMARY: 0 errors' in text,text[-2000:]
 assert 'O1_FINAL ' in text
 cost=audit_state(state,bal);native=float(re.search(r'RESULT.*final_cost=(\S+)',text)[1]);assert abs(cost-native)<1e-6*max(1,cost)
 comp=json.loads((P/'o1-compatibility-results.json').read_text());med={a:statistics.median(x['cost'] for x in comp if x['arm']==a) for a in ['off','original']};delta=med['off']/med['original']-1;assert abs(delta)<.0015
 smoke=json.loads((P/'o1-smoke-results.json').read_text())[0];assert smoke['valid']
 result=dict(passed=True,binary_sha256=sha(binary),compatibility_relative_median=delta,command=cmd,input_sha256=sha(bal),log_sha256=sha(log),state_sha256=sha(state),cost=cost,native_cost=native,kernel_validation_sha256=sha(P/'o1-kernel-validation.json'),scope='correctness only; no performance inference from compatibility/smoke; engineering guard failures remain labeled')
 (P/'o1-native-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':main()
