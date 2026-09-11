#!/usr/bin/env python3
"""Capture three fresh failures; times are diagnostic and never benchmarked."""
import fcntl,hashlib,json,os,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;F=P.parent/'eta2_champion'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    champ=json.loads((F/'champion.json').read_text());build=json.loads((P/'build/manifest.json').read_text())
    binary=P/'build/prism-curvature';assert sha(binary)==build['binary_sha256']
    problem=Path('/workspace/bal/venice-52.txt')
    h='7622ddb436323d3080d858a5319025a51cfef232bae0b793b6ef29abc1a3385b';assert sha(problem)==h
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        for rep in range(3):
            folder=P/'evidence'/f'capture-{rep}';folder.mkdir(parents=True,exist_ok=True)
            done=folder/'capture_complete.json'
            if done.exists():continue
            flags=dict(champ['flags'],OCA_DEPTH_DECLIP='1',OCA_CURVATURE_CAPTURE=str(folder),
                       OCA_TARGET_COST='243740.27',OCA_MAX_SECONDS='60')
            env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','MF_DEBUG','CASPAR_','COLMAP_MFREE','CERES_'))}
            env.update(flags)
            cmd=[str(binary),'--problem',str(problem),'--algo','mfree_shifted_cg','--dof9','--zero_k2',
                 '--lam0','0.1','--max_iter','600','--state_out',str(folder/'endpoint.state')]
            (folder/'manifest.json').write_text(json.dumps(dict(command=cmd,flags=flags,input_sha256=h,
                binary_sha256=sha(binary),source_sha256=build['source_sha256'],protocol_sha256=sha(P/'PROTOCOL.md'),
                diagnostic_only=True),indent=2)+'\n')
            print('CAPTURE',rep,flush=True)
            with (folder/'stdout.log').open('w') as out,(folder/'stderr.log').open('w') as err:
                rc=subprocess.run(cmd,env=env,stdout=out,stderr=err,timeout=180).returncode
            text=(folder/'stdout.log').read_text();assert rc==0,rc
            assert 'CURVATURE_AUDIT diagnostic_complete' in text
            assert 'CURVATURE_CAPTURE outer=' in text
            files={f.name:dict(sha256=sha(f),bytes=f.stat().st_size) for f in folder.iterdir() if f.is_file()}
            done.write_text(json.dumps(dict(returncode=rc,files=files),indent=2)+'\n')
            print((folder/'metadata.txt').read_text().strip(),flush=True)
if __name__=='__main__':main()
