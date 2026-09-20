from pathlib import Path
import subprocess,fcntl,os,time,json,datetime
root=Path('/workspace/multishift_repro');out=root/'codex_evidence'
assert (out/'manifest.json').is_file()
env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))}
with open('/tmp/prism_gpu.lock','w') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 check=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader'],capture_output=True,text=True,check=True)
 (out/'gpu-before.txt').write_text(check.stdout)
 assert not check.stdout.strip(), 'GPU is not idle'
 assert not (root/'repro_codex.csv').exists()
 start=time.monotonic()
 with (out/'runner.log').open('w') as log:
  p=subprocess.Popen(['./run_repro.sh','/workspace/bal','repro_codex.csv'],cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
  for line in p.stdout:
   log.write(line);log.flush();print(line,end='',flush=True)
  code=p.wait()
 (out/'completion.json').write_text(json.dumps({'returncode':code,'process_wall_seconds':time.monotonic()-start,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+'\n')
 assert code==0,code
