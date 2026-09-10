#!/usr/bin/env python3
"""Lossless byte-plane/XOR packing of repeated audited states; verify every byte."""
import gzip
import hashlib
import io
import json
import lzma
import pathlib
import shutil
import tarfile
import numpy as np

ROOT=pathlib.Path('/tmp/prism-speed-novelty')
FULL=pathlib.Path('/tmp/prism-speed-novelty-evidence.tar.xz')
COMPACT=pathlib.Path('/tmp/prism-speed-novelty-evidence-compact.tar.xz')

def sha(b):return hashlib.sha256(b).hexdigest()

RESTORE='''#!/usr/bin/env python3
"""Run from the extracted bundle root; restores exact original .state exports."""
import hashlib,json,pathlib
import numpy as np
root=pathlib.Path(__file__).resolve().parent
manifest=json.loads((root/'state-codec.json').read_text())
for name,info in manifest.items():
    packed=(root/name).read_bytes()
    raw=np.frombuffer(packed,dtype=np.uint8).reshape(8,-1).T.copy().reshape(-1)
    if info['reference']:
        ref=(root/info['reference']).read_bytes()
        raw ^= np.frombuffer(ref,dtype=np.uint8)
    data=raw.tobytes()
    assert hashlib.sha256(data).hexdigest()==info['sha256'],name
    target=root/info['original_name']
    if target.exists():assert target.read_bytes()==data
    else:target.write_bytes(data)
print('Restored and verified',len(manifest),'exact endpoint states.')
'''

def main():
    expected=json.loads((ROOT/'archive-manifest.json').read_text())['member_sha256']
    base={};codec={};new_hashes={}
    with lzma.open(COMPACT,'wb',filters=[{'id':lzma.FILTER_LZMA2,'preset':6,'dict_size':64<<20}]) as stream:
        with tarfile.open(fileobj=stream,mode='w|') as dest,tarfile.open(FULL,'r|xz') as src:
            for info in src:
                if not info.isfile():continue
                data=src.extractfile(info).read();assert sha(data)==expected[info.name]
                if info.name.endswith('.state'):
                    original=info.name
                    group=original.rsplit('-',1)[0]
                    arr=np.frombuffer(data,dtype=np.uint8)
                    if group not in base:
                        base[group]=(original,data);reference=None;delta=arr
                    else:
                        reference,ref=base[group];assert len(ref)==len(data)
                        delta=arr^np.frombuffer(ref,dtype=np.uint8)
                    info=tarfile.TarInfo(original+'.sbd');info.size=len(data)
                    data=delta.reshape(-1,8).T.copy().tobytes()
                    codec[info.name]=dict(original_name=original,reference=reference,sha256=expected[original])
                dest.addfile(info,io.BytesIO(data));new_hashes[info.name]=sha(data)
            additions={'restore_states.py':RESTORE.encode(),
                'state-codec.json':(json.dumps(codec,indent=2)+'\n').encode(),
                'COMPACT_README.txt':b'This is a lossless compact form of the full verified experiment archive.\nRun python3 restore_states.py from the extracted directory to restore every exact .state.\nThe codec groups the eight byte planes of each 64-bit word after XOR against the first\nstate in the same phase/scene/arm group. It introduces no quantization or loss.\nstate-codec.json records every reference and original SHA256. NumPy is required.\n',
                'repo/bench/compact_speed_novelty.py':pathlib.Path(__file__).read_bytes()}
            for name,data in additions.items():
                info=tarfile.TarInfo(name);info.size=len(data);dest.addfile(info,io.BytesIO(data));new_hashes[name]=sha(data)
    decoded={};checked={};seen=set()
    with tarfile.open(COMPACT,'r|xz') as src:
        for info in src:
            data=src.extractfile(info).read();assert sha(data)==new_hashes[info.name];seen.add(info.name)
            if info.name in codec:
                spec=codec[info.name]
                arr=np.frombuffer(data,dtype=np.uint8).reshape(8,-1).T.copy().reshape(-1)
                if spec['reference']:arr ^= np.frombuffer(decoded[spec['reference']],dtype=np.uint8)
                original=arr.tobytes();assert sha(original)==spec['sha256']
                decoded[spec['original_name']]=original
                checked[spec['original_name']]=sha(original)
            elif info.name in expected:
                checked[info.name]=sha(data)
    assert seen==set(new_hashes)
    assert checked==expected,'Not all full-archive members reconstructed'
    with COMPACT.open('rb') as f:archive_sha=hashlib.file_digest(f,'sha256').hexdigest()
    result=dict(path=str(COMPACT),sha256=archive_sha,bytes=COMPACT.stat().st_size,
        full_archive_bytes=FULL.stat().st_size,verified_original_members=len(checked),
        verified_exact_states=len(codec),codec='byteplane8 XOR against phase/scene/arm reference; lossless',
        full_archive_sha256=json.loads((ROOT/'archive-manifest.json').read_text())['sha256'])
    (ROOT/'compact-archive-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    target=pathlib.Path('/workspace/prism-speed-novelty-evidence.tar.xz')
    partial=target.with_suffix(target.suffix+'.partial')
    with COMPACT.open('rb') as src,partial.open('xb') as dest:shutil.copyfileobj(src,dest)
    with partial.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==archive_sha
    partial.replace(target)
    result['persistent_path']=str(target)
    (ROOT/'compact-archive-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
