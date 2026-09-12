"""Unscored initial-state check of the O1 numerical follow-up."""
from pathlib import Path
import fcntl,gzip,hashlib,json,os,re,subprocess,sys,tempfile
P=Path(__file__).resolve().parent;sys.path.insert(0,str(P/'o2'))
from validate import audit_state
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 subprocess.run(['python3',str(P.parent/'eta2_champion/build.py'),'--check-only'],check=True)
 bm=json.loads((P/'o1-schur-build-manifest.json').read_text());b=P/'build/prism-o1-schur';assert sha(b)==bm['binary_sha256']
 assert all(sha(p)==h for p,h in bm['sources'].items());kv=json.loads((P/'o1-schur-kernel-validation.json').read_text());assert kv['passed'] and kv['header_sha256']==sha(P/'o1_schur.cuh')
 cfg=json.loads((P.parent/'eta2_champion/champion.json').read_text());env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','CERES_'))};env.update(cfg['flags']);env.update(OCA_O1_SWEEPS='3',OCA_MAX_SECONDS='60',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
 out=P/'o1-schur-diagnostic';out.mkdir(exist_ok=True);rows=[]
 with open('/tmp/prism_gpu.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  for scene in ['final-3068','venice-52']:
   bal=Path('/workspace/bal')/(scene+'.txt');log=out/(scene+'.log');assert not log.exists()
   fd,state=tempfile.mkstemp(prefix='o1-schur-',suffix='.state',dir='/dev/shm');os.close(fd);state=Path(state)
   cmd=[str(b),'--problem',str(bal),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--lam0','.1','--max_iter','1','--state_out',str(state)]
   manifest=dict(command=cmd,flags=cfg['flags']|{'OCA_O1_SWEEPS':'3','OCA_MAX_SECONDS':'60'},binary_sha256=sha(b),input_sha256=sha(bal),protocol_sha256=sha(P/'O1_SCHUR_DIAGNOSTIC.md'),scope='one-outer numerical diagnostic; no target/hit-rate/performance claim')
   (out/(scene+'-manifest.json')).write_text(json.dumps(manifest,indent=2)+'\n')
   with log.open('w') as f:r=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180)
   text=log.read_text();assert r.returncode==0,text[-2000:];cost=audit_state(state,bal);native=float(re.search(r'RESULT.*final_cost=(\S+)',text)[1]);assert abs(cost-native)<1e-6*max(1,cost)
   data=state.read_bytes();compressed=out/(scene+'.state.gz');compressed.write_bytes(gzip.compress(data,compresslevel=9));assert gzip.decompress(compressed.read_bytes())==data;state.unlink()
   events=[dict(kind=l.split()[0],**dict(re.findall(r'(\w+)=(\S+)',l))) for l in text.splitlines() if l.startswith(('O1_SWEEP ','O1_QP ','O1_FINAL '))]
   row=dict(scene=scene,valid=True,cost=cost,native_cost=native,events=events,state_sha256=hashlib.sha256(data).hexdigest(),compressed_sha256=sha(compressed),log_sha256=sha(log));rows.append(row);print(scene,events,flush=True)
   (P/'o1-schur-diagnostic.json').write_text(json.dumps(dict(rows=rows),indent=2)+'\n')
 gate=any(e.get('accepted')=='1' for r in rows if r['scene']=='final-3068' for e in r['events'] if e['kind']=='O1_SWEEP')
 (P/'o1-schur-diagnostic.json').write_text(json.dumps(dict(rows=rows,gate_passed=gate),indent=2)+'\n')
if __name__=='__main__':main()
