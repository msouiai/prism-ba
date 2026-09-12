"""O5 native correctness gates; these clocks are never performance evidence."""
from pathlib import Path
import fcntl,hashlib,json,os,re,statistics,subprocess,sys
P=Path(__file__).resolve().parent
sys.path.insert(0,str(P/'o2'))
from validate import audit_state
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 cfg=json.loads((P.parent/'eta2_champion/champion.json').read_text())
 bm=json.loads((P/'o5_build_manifest.json').read_text());binary=P/'build/prism-o5'
 assert sha(binary)==bm['binary_sha256']
 out=P/'o5-validation';out.mkdir(exist_ok=True)
 env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','CERES_'))}
 env.update(cfg['flags']);env.update(OCA_W5_CAUCHY='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
 rows=[]
 with open('/tmp/prism_gpu.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  for label,bal,cap,sanitize,target in [('tiny',P/'o2/build/toy.txt',40,True,0),('partial',P/'o2/build/zero-residual.txt',1,False,1),('cap',P/'o2/build/zero-residual.txt',6,False,1)]:
   log=out/(label+'.log');state=out/(label+'.state');assert not log.exists()
   flags=dict(env)
   if target:flags['OCA_TARGET_COST']=str(target)
   cmd=[str(binary),'--problem',str(bal),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--lam0','.1','--max_iter',str(cap),'--state_out',str(state)]
   if sanitize:cmd=['compute-sanitizer','--tool','memcheck','--error-exitcode','97']+cmd
   with log.open('w') as f:r=subprocess.run(cmd,env=flags,stdout=f,stderr=subprocess.STDOUT,timeout=180)
   text=log.read_text();assert r.returncode==0,text[-2000:]
   if sanitize:assert 'ERROR SUMMARY: 0 errors' in text
   if label=='partial':assert 'TARGET reached' not in text and 'incomplete=1' in text
   if label=='cap':assert 'capped=1' in text and text.index('stage=4')<text.index('TARGET reached')
   cost=audit_state(state,bal);native=float(re.search(r'RESULT.*final_cost=(\S+)',text)[1])
   assert abs(cost-native)<1e-6*max(1,cost)
   rows.append(dict(label=label,command=cmd,input_sha256=sha(bal),log_sha256=sha(log),state_sha256=sha(state),cost=cost,native_cost=native,passed=True))
 comp=json.loads((P/'o5-compatibility-results.json').read_text());smoke=json.loads((P/'o5-smoke-results.json').read_text())[0]
 med={a:statistics.median(x['cost'] for x in comp if x['arm']==a) for a in ['off','original']}
 delta=med['off']/med['original']-1;assert abs(delta)<.0015
 stages=[x for x in smoke['opening_events'] if x['kind']=='W5_STAGE'];assert [int(x['stage']) for x in stages]==[1,2,3,4]
 assert smoke['valid'] and smoke['opening_completed'] and all(int(x['attempts'])>=2 for x in stages)
 result=dict(passed=True,binary_sha256=sha(binary),compatibility_relative_median=delta,rows=rows,kernel_validation_sha256=sha(P/'o5-kernel-validation.json'),scope='native correctness only; no performance inference',opening_stages=[1,2,3,4])
 (P/'o5-native-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':main()
