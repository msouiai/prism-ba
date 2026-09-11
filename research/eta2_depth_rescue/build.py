#!/usr/bin/env python3
"""Derive a default-off research solver without changing the frozen source."""
from pathlib import Path
import fcntl, hashlib, json, subprocess
P = Path(__file__).resolve().parent
F = P.parent / 'eta2_champion'
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def patch(text, old, new):
    assert text.count(old) == 1, (old[:100], text.count(old))
    return text.replace(old, new)
def main():
    subprocess.run(['python3', str(F/'build.py'), '--check-only'], check=True)
    s = (F/'source/prism_eta2.cu').read_text()
    for name in ['state','begin','eta','cap','linear','decision','schedule','summary']:
        spec = json.loads((P/'patches.json').read_text())[name]
        s = patch(s, spec['old'], (P/(name+'.inc')).read_text()+spec['old'] if spec.get('before') else spec['old']+(P/(name+'.inc')).read_text() if spec.get('after') else (P/(name+'.inc')).read_text())
    s = patch(s, 'const bool backtrack_ready=backtrack_on && !backtrack_confirm && n_accept>=3;',
              'const bool backtrack_ready=backtrack_on && !backtrack_confirm && n_accept>=3 && depth_active==0;')
    s = patch(s, 'if(numeric_guard && trunc && numeric_rebuilds<32',
              'if(depth_active==0 && numeric_guard && trunc && numeric_rebuilds<32')
    # The start of the flat-decrease streak is distinct from reject streaks.
    s = patch(s, '    // Two independent reasons to stop early.\n',
              '    if(ftol_streak==0) depth_flat_center=depth_attempt_center;\n    // Two independent reasons to stop early.\n')
    p = P/'build'; p.mkdir(exist_ok=True)
    source=p/'prism_depth.cu'; source.write_text(s)
    cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',
         '-I'+str(F/'source/headers'),str(source),'-o',str(p/'prism-depth'),'-lcublas','-lcusolver']
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        with (p/'build.log').open('w') as log:
            subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
    (p/'manifest.json').write_text(json.dumps(dict(command=cmd,source_sha256=sha(source),
        parent_source_sha256=sha(F/'source/prism_eta2.cu'),binary_sha256=sha(p/'prism-depth'),
        protocol_sha256=sha(P/'PROTOCOL.md')),indent=2)+'\n')
    print('BUILT',sha(p/'prism-depth'),flush=True)
if __name__=='__main__': main()
