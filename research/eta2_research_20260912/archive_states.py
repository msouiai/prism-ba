#!/usr/bin/env python3
"""Losslessly archive completed campaign endpoint contents to preserve disk space."""
from pathlib import Path
import argparse,gzip,hashlib,json,lzma,os,shutil,tarfile
from grid_common import P,sha,write

ap=argparse.ArgumentParser();ap.add_argument('cohort',choices=['stcg','pi','coarse','predictor','frontload']);a=ap.parse_args()
root=P/'evidence'/a.cohort;files=sorted(root.rglob('endpoint.state.gz'),key=lambda f:(f.parent.name.split('-off-')[0].split('-on-')[0],str(f)))
assert files,'No endpoint containers'
out=P/'evidence_archives';out.mkdir(exist_ok=True)
archive=out/(a.cohort+'-endpoint-contents.tar.xz');manifest=out/(a.cohort+'-endpoint-contents.json')
assert not archive.exists() and not manifest.exists(),'Archive already exists; do not overwrite'
tmp=Path('/dev/shm')/('eta2-'+a.cohort+'-endpoint-contents.tar.xz');assert not tmp.exists()
rows=[]
for f in files:
    result=json.loads((f.parent/'result.json').read_text());assert result['valid']
    assert sha(f)==result['state']['compressed_sha256']
    rows.append(dict(source=str(f.relative_to(P)),member=str(f.relative_to(P))[:-3],
                     bytes=result['state']['bytes'],raw_sha256=result['state']['sha256'],gzip_sha256=sha(f),gzip_bytes=f.stat().st_size))
with lzma.open(tmp,'wb',preset=7) as compressed,tarfile.open(fileobj=compressed,mode='w|') as tar:
    for row,f in zip(rows,files):
        info=tarfile.TarInfo(row['member']);info.size=row['bytes'];info.mode=0o444
        with gzip.open(f,'rb') as src:tar.addfile(info,src)
def verify(path):
    seen=[]
    with tarfile.open(path,'r|xz') as tar:
        for member in tar:
            row=rows[len(seen)];assert member.name==row['member'] and member.size==row['bytes']
            with tar.extractfile(member) as src:assert hashlib.file_digest(src,'sha256').hexdigest()==row['raw_sha256']
            seen.append(member.name)
    assert len(seen)==len(rows)
verify(tmp)
with tmp.open('rb') as src,archive.open('xb') as dst:
    shutil.copyfileobj(src,dst);dst.flush();os.fsync(dst.fileno())
assert sha(archive)==sha(tmp);verify(archive)
write(manifest,dict(archive=str(archive.relative_to(P)),archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,
    scope='Exact numerical endpoint contents preserved. Individual gzip containers are replaced by this verified solid archive; original container hashes remain provenance.',
    restoration='Extract the named .state member into a temporary directory, verify raw_sha256, then use the ordinary independent endpoint auditor.',rows=rows))
for f,row in zip(files,rows):
    assert sha(f)==row['gzip_sha256'];f.unlink()
tmp.unlink()
print('Archived and verified',len(rows),'endpoints; reclaimed',sum(x['gzip_bytes'] for x in rows)-archive.stat().st_size,'bytes',flush=True)
