"""Pack idle historical raw state exports without changing a single decoded byte."""
from pathlib import Path
import hashlib,json,shutil
import lossless_float_archive as F
P=Path(__file__).resolve().parent;ROOT=Path('/tmp/prism-rl-sustained')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    ledger=P/'storage_xor_archives.json';rows=json.loads(ledger.read_text()) if ledger.exists() else []
    files=sorted((p for p in ROOT.rglob('*.state') if p.is_file() and not p.is_symlink() and not Path(str(p)+'.gz').exists()),key=lambda p:p.stat().st_size)
    destroot=ROOT/'lossless-state-archives';destroot.mkdir(exist_ok=True)
    while files and shutil.disk_usage('/').free<1_500_000_000:
        group=[];size=0
        while files and (not group or size+files[0].stat().st_size<200_000_000):
            p=files.pop(0);group.append(p);size+=p.stat().st_size
        dest=destroot/(str(len(rows))+'.xor.tar.xz');assert not dest.exists()
        hashes=F.pack(dest,{str(p.relative_to(ROOT)):p for p in group});F.verify(dest,hashes)
        rows.append(dict(archive=str(dest),sha256=sha(dest),restore_root=str(ROOT),decoder=str(P/'lossless_float_archive.py'),
          member_sha256=hashes,raw_bytes=size,packed_bytes=dest.stat().st_size,verified=True))
        ledger.write_text(json.dumps(rows,indent=2)+'\n')
        for p in group:
            assert sha(p)==hashes[str(p.relative_to(ROOT))];p.unlink() # Verified raw bytes retained in archive.
        print('FLOAT ARCHIVE',dest,'saved',size-dest.stat().st_size,'free',shutil.disk_usage('/').free,flush=True)
if __name__=='__main__':main()
