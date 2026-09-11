#!/usr/bin/env python3
"""Archive exact same-state evidence with per-file verification."""
import datetime,fcntl,hashlib,io,json,subprocess,tarfile
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1]
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    dest=Path('/workspace/collab/results')/('eta2_curvature_audit_'+stamp+'.tar.gz');temporary=Path(str(dest)+'.part')
    files={str(f.relative_to(ROOT)):f for f in P.rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.name!='archive.json'}
    F=P.parent/'eta2_champion';D=P.parent/'eta2_depth_rescue'
    extra=list((F/'source').rglob('*'))+[F/'source_manifest.json',F/'champion.json',F/'build.py',F/'bench/audit_prism_state.py',
          D/'build/prism_depth.cu',D/'provenance/build_manifest.json']
    for f in extra:
        if f.is_file():files[str(f.relative_to(ROOT))]=f
    print('ARCHIVING',dest,'files',len(files),flush=True)
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        manifest=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            files={k:dict(sha256=sha(f),bytes=f.stat().st_size) for k,f in sorted(files.items())})
        data=(json.dumps(manifest,indent=2)+'\n').encode()
        with tarfile.open(temporary,'w:gz',compresslevel=1) as t:
            for name,f in sorted(files.items()):t.add(f,arcname=name,recursive=False)
            info=tarfile.TarInfo('ARCHIVE_MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
        print('VERIFYING archive members',flush=True)
        with tarfile.open(temporary,'r:gz') as t:
            checked=0
            for member in t:
                if member.name=='ARCHIVE_MANIFEST.json':assert t.extractfile(member).read()==data;continue
                with t.extractfile(member) as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
                assert actual==manifest['files'][member.name]['sha256'],member.name
                checked+=1
            assert checked==len(files)
        temporary.rename(dest);h=sha(dest)
        Path(str(dest)+'.sha256').write_text(h+'  '+dest.name+'\n');Path(str(dest)+'.manifest.json').write_bytes(data)
    result=dict(path=str(dest),sha256=h,bytes=dest.stat().st_size,files=len(files),commit=manifest['commit'],verified=True)
    (P/'archive.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':main()
