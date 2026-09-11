#!/usr/bin/env python3
"""Seal completed evidence, including lossless states and frozen binaries."""
import datetime
import fcntl
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

P=Path(__file__).resolve().parent
REPO=P.parents[1]


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        audit=json.loads((P/'audit.json').read_text())
        assert audit['all_valid'] and audit['runs']==58
        setup=json.loads((P/'ceres_setup/audit.json').read_text())
        assert setup['passed'] and len(setup['runs'])==15
        assert not subprocess.check_output(['git','status','--porcelain','--',str(P)],cwd=REPO,text=True).strip(), 'Commit the completed study before sealing it.'
        bins={
          'binaries/eta2-champion':('/tmp/prism-rl-actor/build/prism-tr','1e3d2cf22a8a43075114e0ca2024923dad330461e35d0074938d0412cd77ecc0'),
          'binaries/ceres-frozen':('/workspace/prism-novelty/ceres-frozen','6543c8e6f9baa69c421eeda61aef5d1115ca0d825931b71905904f1f53d74837'),
          'binaries/caspar32-frozen':('/workspace/prism-novelty/caspar32-frozen','84e16ac1872115faaac9b3847101c3a59373dab5ad08f1dc1349c2248c1615c6'),
          'binaries/ceres-setup':(str(P/'ceres_setup/build/ceres_setup'),setup['binary_sha256']),
        }
        files={}
        for f in P.rglob('*'):
            if not f.is_file():continue
            parts=f.relative_to(P).parts
            if any(v in ['build','__pycache__'] for v in parts):continue
            if len(parts)==1 and f.suffix=='.log':continue  # Mutable supervisor logs.
            if f.name.endswith('.state'):continue  # Verified lossless gzip files are retained.
            files['eta2_external_coverage/'+str(f.relative_to(P))]=f
        champ=P.parent/'eta2_champion'
        for name in ['champion.json','source_manifest.json','build.py','run.py']:
            f=champ/name
            if f.exists():files['frozen_eta2/'+name]=f
        for f in (champ/'source').rglob('*'):
            if f.is_file():files['frozen_eta2/'+str(f.relative_to(champ))]=f
        for name,(path,expected) in bins.items():
            assert sha(path)==expected,path
            files[name]=Path(path)
        records={name:dict(bytes=f.stat().st_size,sha256=sha(f)) for name,f in sorted(files.items())}
        now=datetime.datetime.now(datetime.timezone.utc)
        manifest=dict(created_utc=now.isoformat(),commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
          files=records,inputs='BAL inputs are referenced by hashes in the protocols; not duplicated.',
          native_binaries='Linux CUDA/Ceres builds; external shared-library dependencies remain necessary.')
        encoded=(json.dumps(manifest,indent=2)+'\n').encode()
        root=Path('/workspace/collab/results')
        target=root/('eta2_external_coverage_'+now.strftime('%Y%m%dT%H%M%SZ')+'.tar.gz')
        partial=Path(str(target)+'.partial')
        assert not target.exists() and not partial.exists()
        print('Sealing',len(files),'files;',sum(r['bytes'] for r in records.values()),'input bytes.',flush=True)
        with tarfile.open(partial,'w:gz',compresslevel=1) as out:
            info=tarfile.TarInfo('ARCHIVE_MANIFEST.json');info.size=len(encoded)
            out.addfile(info,io.BytesIO(encoded))
            for name,f in sorted(files.items()):out.add(f,arcname=name,recursive=False)
        print('Verifying every archived member.',flush=True)
        with tarfile.open(partial,'r:gz') as archive:
            assert set(archive.getnames())==set(records)|{'ARCHIVE_MANIFEST.json'}
            assert archive.extractfile('ARCHIVE_MANIFEST.json').read()==encoded
            for name,r in records.items():
                f=archive.extractfile(name)
                assert archive.getmember(name).size==r['bytes']
                assert hashlib.file_digest(f,'sha256').hexdigest()==r['sha256'],name
        partial.rename(target)
        digest=sha(target)
        Path(str(target)+'.sha256').write_text(digest+'  '+target.name+'\n')
        Path(str(target)+'.manifest.json').write_bytes(encoded)
        print(json.dumps(dict(archive=str(target),sha256=digest,bytes=target.stat().st_size,files=len(records)),indent=2),flush=True)


if __name__=='__main__':main()
