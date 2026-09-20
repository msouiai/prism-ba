from pathlib import Path
import subprocess,fcntl,os,time,json,csv,re,hashlib,datetime,socket
root=Path('/workspace/multishift_repro');out=root/'codex_v2_repeats';binary=root/'oca_cuda_v2'
expected='fb76817faae3290a9a815f7a8fce1681d2dc34cfa60b25134b54e72998120698'
assert hashlib.sha256(binary.read_bytes()).hexdigest()==expected
assert not (out/'repro_codex_v2_n10.csv').exists()
flags={'OCA_RHO_LAMBDA':'1','OCA_GRID_DOWN':'2','OCA_RHO_SHIFT':'1','OCA_ALPHA_RHO':'1'}
env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};env.update(flags)
scenes=['dubrovnik-88','venice-52','final-3068']
cli=['--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter','60','--lam0','10.0','--tau_pt','3e-3','--func-tol','1e-6','--max-consec-fail','3']
m=json.loads((root/'codex_evidence/manifest.json').read_text())
protocol={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'host':socket.gethostname(),'binary_sha256':expected,'source_sha256':hashlib.sha256((root/'oca_cuda_v2.cu').read_bytes()).hexdigest(),'flags':flags,'cli':cli,'inputs':{s:m['datasets'][s] for s in scenes},'repetitions':10,'order':'Interleaved scenes; cyclic rotation per repetition. Preselected no outcome-driven reruns.','timeout_per_process_seconds':3600,'scope':'V2 library-settings within-host repeatability only, not a champion A/B or universally calibrated noise floor'}
(out/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
rows=[];start=time.monotonic()
with open('/tmp/prism_gpu.lock','w') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 check=subprocess.run(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],capture_output=True,text=True,check=True)
 assert not check.stdout.strip(),'GPU busy'
 with (out/'repro_codex_v2_n10.csv').open('w') as f:
  fields=['dataset','rep','final_cost','solve_seconds','iters','accepts','rejects','matvecs','returncode','process_wall_seconds'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();f.flush()
  for rep in range(1,11):
   order=scenes[(rep-1)%3:]+scenes[:(rep-1)%3]
   for scene in order:
    assert hashlib.sha256(binary.read_bytes()).hexdigest()==expected,'Binary changed during panel'
    cmd=[str(binary),'--problem',f'/workspace/bal/{scene}.txt',*cli]
    stem=f'{scene}-{rep:02d}';log=out/(stem+'.log');t=time.monotonic()
    with log.open('w') as target:
     try:p=subprocess.run(cmd,env=env,stdout=target,stderr=subprocess.STDOUT,timeout=3600);rc=p.returncode
     except subprocess.TimeoutExpired:rc=124
    text=log.read_text();result=re.search(r'RESULT algo=\S+ iters=(\d+) final_cost=([0-9.eE+-]+) solve_seconds=([0-9.eE+-]+)',text)
    counts=re.search(r'MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)',text)
    row=dict(dataset=scene,rep=rep,final_cost=result[2] if result else 'NA',solve_seconds=result[3] if result else 'NA',iters=result[1] if result else 'NA',accepts=counts[1] if counts else 'NA',rejects=counts[2] if counts else 'NA',matvecs=counts[3] if counts else 'NA',returncode=rc,process_wall_seconds=time.monotonic()-t)
    w.writerow(row);f.flush();rows.append(row);print(json.dumps(row),flush=True)
    (out/(stem+'.json')).write_text(json.dumps({'command':cmd,'flags':flags,**row},indent=2)+'\n')
(out/'completion.json').write_text(json.dumps({'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'process_wall_seconds':time.monotonic()-start,'records':len(rows)},indent=2)+'\n')
print('DONE',flush=True)
