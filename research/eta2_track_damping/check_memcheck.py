#!/usr/bin/env python3
"""Native mixed-track toy under compute-sanitizer, with independent objective audit."""
import fcntl,json,os,re,subprocess,tempfile
from pathlib import Path
from run import P,G

def main():
    src=P/'evidence/toy/toy_mixed-on-0'
    m=json.loads((src/'manifest.json').read_text())
    out=P/'evidence/correctness/mixed-toy-memcheck';out.mkdir(parents=True,exist_ok=True)
    cmd=m['command'].copy();cmd[cmd.index('--csv')+1]=str(out/'curve.csv')
    flags=dict(m['flags'],OCA_STCG_ATTEMPTS=str(out/'attempts.json'))
    env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','CERES_','COLMAP_MFREE','MF_DEBUG'))};env.update(flags)
    with tempfile.TemporaryDirectory(prefix='eta2-track-check-',dir='/dev/shm') as temp:
        state=Path(temp)/'endpoint.state';cmd[cmd.index('--state_out')+1]=str(state)
        cmd=['/usr/local/cuda/bin/compute-sanitizer','--tool','memcheck','--error-exitcode','91']+cmd
        G.write(out/'manifest.json',dict(command=cmd,flags=flags,source_manifest=m))
        with open('/tmp/prism_gpu.lock','a') as lock,(out/'stdout.log').open('w') as log:
            fcntl.flock(lock,fcntl.LOCK_EX)
            r=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=120)
        text=(out/'stdout.log').read_text();match=re.search(r'RESULT .*?final_cost=(\S+)',text)
        assert r.returncode==0 and 'ERROR SUMMARY: 0 errors' in text and match
        cost=G.audit(state,*G.observations(cmd[cmd.index('--problem')+1]))
        relative=abs(cost-float(match[1]))/max(1,cost)
        assert relative<1e-8
        G.write(out/'result.json',dict(passed=True,returncode=r.returncode,sanitizer_zero_errors=True,
           cost=cost,audit_relative_error=relative,state_sha256=G.sha(state),
           scope='Auxiliary memory-check endpoint audited and hashed; scored grid states retained separately.'))
    print('MEMCHECK PASS',flush=True)
if __name__=='__main__':main()
