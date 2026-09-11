#!/usr/bin/env python3
"""Verify the separate setup study without merging it into the primary ledger."""
import fcntl
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

P=Path(__file__).resolve().parent
sys.path.insert(0,str(P.parent))
import run_eta2 as common


def main():
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        reg=json.loads((P/'registration.json').read_text())
        for file,key in [('PROTOCOL.md','protocol_sha256'),('ceres_bal.cc','source_sha256'),('run.py','driver_sha256')]:
            assert common.sha(P/file)==reg[key],file
        build=json.loads((P/'build-manifest.json').read_text())
        assert common.sha(P/'build/ceres_setup')==build['binary_sha256']
        assert common.sha(P/'CMakeLists.txt')==build['cmake_sha256']
        oldlibs=json.loads((P.parent/'ceres-shared-libraries.json').read_text())
        ldd=subprocess.check_output(['ldd',str(P/'build/ceres_setup')],text=True)
        linked={str(Path(p).resolve()) for p in re.findall(r'=> (/\S+)',ldd)}
        libraries=[]
        for entry in oldlibs['libraries']:
            resolved=entry['resolved']
            if 'ld-linux' in resolved:
                continue
            assert resolved in linked,('missing frozen dependency',resolved)
            assert common.sha(Path(resolved))==entry['sha256'],resolved
            libraries.append(entry)
        assert any('libceres.so' in e['path'] for e in libraries)
        results=json.loads((P/'results.json').read_text())
        assert len(results)==15
        assert {(r['arm'],r['rep']) for r in results}=={(a,r) for a in reg['arms'] for r in range(3)}
        problem=Path('/workspace/bal/final-3068.txt')
        dims,obs=common.observations(problem)
        input_sha=common.sha(problem)
        checked=[]
        for row in results:
            folder=P/row['source'];m=json.loads((folder/'manifest.json').read_text())
            assert m['input_sha256']==input_sha and m['target']==reg['target']
            assert m['binary_sha256']==build['binary_sha256']
            assert m['source_sha256']==reg['source_sha256']
            assert m['protocol_sha256']==reg['protocol_sha256']
            for key,value in reg['arms'][row['arm']].items():
                assert m['flags'][key]==value
            assert row['valid'],row
            assert row['actual_options']['normalize']==int(reg['arms'][row['arm']]['CERES_NORMALIZE'])
            assert row['actual_options']['strict']==int(reg['arms'][row['arm']]['CERES_STRICT_STOP'])
            assert row['actual_options']['eta']==float(reg['arms'][row['arm']].get('CERES_INNER_ETA','.1'))
            gz=folder/'endpoint.state.gz'
            assert common.sha(gz)==row['compressed_state_sha256']
            with tempfile.TemporaryDirectory(prefix='ceres-setup-audit-') as tmp:
                state=Path(tmp)/'endpoint.state'
                with gzip.open(gz,'rb') as src,state.open('wb') as dst:shutil.copyfileobj(src,dst)
                assert common.sha(state)==row['state_sha256']
                cost=common.audit(state,dims,obs)
            rel=abs(cost-row['cost'])/max(1,abs(cost));assert rel<1e-12
            crossing=next((t['seconds'] for t in row['trace'] if t['accepted'] and t['cost']<=reg['target']),None)
            assert crossing==row['target_seconds']
            assert row['hit']==(crossing is not None and crossing<=60 and cost<=reg['target'])
            checked.append(dict(arm=row['arm'],rep=row['rep'],state_relative_error=rel,hit=row['hit']))
        control=json.loads((P/'control-validation.json').read_text());assert control['passed']
        out=dict(passed=True,runs=checked,shared_libraries_match_old_frozen=True,libraries=libraries,
                 protocol_sha256=reg['protocol_sha256'],binary_sha256=build['binary_sha256'])
        (P/'audit.json').write_text(json.dumps(out,indent=2)+'\n')
        print('Verified all 15 states, target outcomes, flags, source hashes, and frozen Ceres dependencies.')


if __name__=='__main__':main()
