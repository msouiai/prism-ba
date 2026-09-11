#!/usr/bin/env python3
"""Verify completed result provenance and lossless states; no new solves."""
import fcntl,gzip,hashlib,json,math,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    subprocess.run(['python3',str(P.parent/'eta2_champion/build.py'),'--check-only'],check=True)
    expected={'compatibility':6,'final':20,'venice':20,'screen':30}
    errors=[];count=0;max_error=0
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        inputs=json.loads((P/'inputs.json').read_text())
        for scene,h in inputs.items():assert sha(Path('/workspace/bal')/(scene+'.txt'))==h
        for stage,n in expected.items():
            paths=list((P/'evidence'/stage).glob('*/result.json'));assert len(paths)==n,(stage,len(paths))
            for path in paths:
                r=json.loads(path.read_text());m=json.loads((path.parent/'manifest.json').read_text())
                assert r['valid'] and r['returncode']==0
                assert m['protocol_sha256']==sha(P/'PROTOCOL.md')
                assert m['input_sha256']==inputs[r['scene']]
                assert m['binary_sha256']==sha(Path(m['command'][0]))
                state=path.parent/'endpoint.state.gz'
                assert sha(state)==r['compressed_state_sha256']
                with gzip.open(state,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['state_sha256']
                assert r['audit_relative_error']<1e-6
                max_error=max(max_error,r['audit_relative_error'])
                if r['hit']:assert r['cost']<=r['target'] and r['target_seconds']<=60
                if r['arm'] in ['off','original']:assert not r['probes'] and not r['triggers']
                for p in r['probes']:
                    assert p['cg']<=512
                    if p['accept']:assert p['candidate']<p['cost'] and p['rho']>.1 and p['trunc']==0
                # A rejected de-clipping probe must publish its restored controller.
                assert len(r['restores'])==sum(p['kind']==2 and not p['accept'] for p in r['probes'])
                count+=1
    result=dict(passed=True,rows=count,stage_counts=expected,
                independent_fp64_endpoint_audits=count,max_endpoint_relative_error=max_error,
                verified_lossless_states=count,frozen_parent_headers=44,
                notes=['CPU endpoint costs were computed in each primary run; this audit verifies their recorded errors and exported-state provenance.'])
    (P/'audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
