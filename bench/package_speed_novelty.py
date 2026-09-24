#!/usr/bin/env python3
"""Archive exact audited states and reproducibility sources with verified hashes."""
import gzip
import hashlib
import io
import json
import lzma
import pathlib
import shutil
import struct
import tarfile

ROOT=pathlib.Path('/tmp/prism-speed-novelty')
REPO=pathlib.Path(__file__).resolve().parents[1]
ARCHIVE=pathlib.Path('/tmp/prism-speed-novelty-evidence.tar.xz')

def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    assert (ROOT/'verdict.json').exists() and (ROOT/'late-diagnostic-rows.json').exists()
    expected={}
    raw_states={}
    for p in ROOT.rglob('*.result.json'):
        r=json.loads(p.read_text())
        if r.get('state_sha256'):raw_states[p.with_suffix('').with_suffix('.state')]=r['state_sha256']
    with lzma.open(ARCHIVE,'wb',format=lzma.FORMAT_XZ,
                   filters=[{'id':lzma.FILTER_LZMA2,'preset':6,'dict_size':64<<20}]) as compressed:
        with tarfile.open(fileobj=compressed,mode='w|') as tar:
            for p in sorted(ROOT.rglob('*')):
                if not p.is_file() or '__pycache__' in p.parts:continue
                if 'ceres' in p.parts and 'build' in p.parts and p.name!='ceres_bal':continue
                name='study/'+str(p.relative_to(ROOT))
                if p.name.endswith('.state.gz'):
                    name=name[:-3]
                    with p.open('rb') as f:
                        f.seek(-4,2);size=struct.unpack('<I',f.read(4))[0]
                    info=tarfile.TarInfo(name);info.size=size
                    with gzip.open(p,'rb') as f:tar.addfile(info,f)
                    expected[name]=raw_states[pathlib.Path(str(p)[:-3])]
                else:
                    tar.add(p,arcname=name,recursive=False)
                    expected[name]=digest(p)
            source_files=[REPO/'bench'/n for n in ['build_speed_novelty.py','speed_novelty_study.py',
                'speed_novelty_late.py','report_speed_novelty.py','package_speed_novelty.py','audit_prism_state.py',
                'check_schur_numeric_guard.py']]
            source_files += [REPO/'docs'/n for n in ['speed_novelty_protocol.md','speed_novelty_results.md','curvature_novelty_assessment.md']]
            source_files += list((REPO/'docs/figures/convergence').glob('frozen_new_instances_time_to_target.*'))
            for p in source_files:
                name='repo/'+str(p.relative_to(REPO));tar.add(p,arcname=name,recursive=False);expected[name]=digest(p)
            base=pathlib.Path('/tmp/prism-rl-actor/build')
            for p in [base/'prism-tr',base/'source.cu',base/'manifest.json']+sorted((base/'headers').glob('*')):
                if p.is_file():
                    name='champion/'+str(p.relative_to(base));tar.add(p,arcname=name,recursive=False);expected[name]=digest(p)
            for arm in ['caspar32','caspar64']:
                p=pathlib.Path('/workspace/prism-caspar-current')/arm
                name='baselines/'+arm;tar.add(p,arcname=name,recursive=False);expected[name]=digest(p)
            readme=b'''Frozen Prism speed/curvature confirmation, 2026-09-10.
study/ contains exact inputs, protocol, anchors, raw logs and audited endpoint states.
repo/ contains experiment builders/runners, reports, and the target comparison figure.
champion/ contains the frozen champion binary, source and headers.
baselines/ contains the pinned Caspar32/64 binaries; study/ceres contains its instrumented Ceres driver.
State exports were decompressed from study-local .state.gz containers without changing any state byte.
Their SHA256 must match state_sha256 in the sibling result JSON. compressed_state_sha256 describes
the original local gzip container, not an archived raw state or a newly generated gzip file.
Original absolute paths are preserved in manifests. Relocate inputs/build paths when reproducing
elsewhere; keep hashes, objective, flags, target costs and the interpretation of timers unchanged.
Runtime libraries (CUDA, Ceres 2.2.0, SuiteSparse) are system dependencies, not bundled.
Late diagnostic timings end at stall/cap and must not be treated as time-to-equal-quality.
'''
            info=tarfile.TarInfo('README.txt');info.size=len(readme);tar.addfile(info,io.BytesIO(readme));expected['README.txt']=hashlib.sha256(readme).hexdigest()
    verified={}
    with tarfile.open(ARCHIVE,'r|xz') as tar:
        for item in tar:
            if item.isfile():verified[item.name]=hashlib.file_digest(tar.extractfile(item),'sha256').hexdigest()
    assert verified==expected,'Archive member checksum mismatch'
    result=dict(path=str(ARCHIVE),bytes=ARCHIVE.stat().st_size,sha256=digest(ARCHIVE),
        verified_members=len(verified),verified_states=sum(k.endswith('.state') for k in verified),member_sha256=verified)
    (ROOT/'archive-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    target=pathlib.Path('/workspace/prism-speed-novelty-evidence.tar.xz')
    partial=target.with_suffix(target.suffix+'.partial')
    with ARCHIVE.open('rb') as src,partial.open('xb') as dst:shutil.copyfileobj(src,dst)
    assert digest(partial)==result['sha256']
    partial.replace(target)
    result['persistent_path']=str(target)
    (ROOT/'archive-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='member_sha256'},indent=2))

if __name__=='__main__':main()
