"""Retain exact gzip-container bytes in verified per-case lossless archives."""
from pathlib import Path
import hashlib,json,lzma,tarfile
P=Path(__file__).resolve().parent
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    ledger=P/'step_archives.json';rows=json.loads(ledger.read_text()) if ledger.exists() else []
    for root in ['witness_proposals','geodesic_analytic','root_validation']:
        for d in sorted((P/root).iterdir()):
            if not d.is_dir():continue
            files=sorted(d.glob('*.step' if root=='root_validation' else '*.step.gz'))
            if not files:continue
            dest=d/'steps.tar.xz'
            if dest.exists():raise RuntimeError('archive already exists with unpacked exports: inspect before modifying')
            hashes={f.name:sha(f) for f in files};size=sum(f.stat().st_size for f in files)
            with lzma.open(dest,'wb',preset=7) as compressed:
                with tarfile.open(fileobj=compressed,mode='w|') as archive:
                    for f in files:archive.add(f,arcname=f.name,recursive=False)
            with tarfile.open(dest,'r:xz') as archive:
                for name,digest in hashes.items():
                    with archive.extractfile(name) as f:assert hashlib.file_digest(f,'sha256').hexdigest()==digest
            rows.append(dict(archive=str(dest),sha256=sha(dest),exact_container_hashes=hashes,
                             packed_bytes=dest.stat().st_size,unpacked_bytes=size,verified=True))
            ledger.write_text(json.dumps(rows,indent=2)+'\n')
            for f in files:
                assert sha(f)==hashes[f.name];f.unlink() # Verified exact bytes retained in archive.
            print('ARCHIVED',d,'saved',size-dest.stat().st_size,flush=True)
if __name__=='__main__':main()
