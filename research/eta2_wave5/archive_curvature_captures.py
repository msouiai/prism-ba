#!/usr/bin/env python3
"""Losslessly compact old curvature captures after byte-for-byte verification."""
from pathlib import Path
import hashlib, json, sys

P=Path(__file__).resolve().parent
SOURCE=P.parent/'eta2_curvature_audit/evidence'
DEST=P.parent/'eta2_curvature_audit/evidence_archives'
sys.path.insert(0,str(P.parent/'eta2_wave2'))
import lossless_float_archive as FA


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def main():
    DEST.mkdir(exist_ok=True)
    records=[]
    for index in range(3):
        folder=SOURCE/f'capture-{index}'
        marker=folder/'ARCHIVED.json'
        archive=DEST/f'capture-{index}.xor.tar.xz'
        if marker.exists():
            record=json.loads(marker.read_text());assert sha(archive)==record['archive_sha256']
            FA.verify(archive,record['files']);records.append(record);continue
        files={item.name:item for item in sorted(folder.iterdir()) if item.is_file()}
        if not files:raise RuntimeError(f'No source files in {folder}')
        original_bytes=sum(item.stat().st_size for item in files.values())
        temporary=Path(str(archive)+'.part')
        hashes=FA.pack(temporary,files);FA.verify(temporary,hashes)
        archive_bytes=temporary.stat().st_size
        if archive_bytes>=original_bytes:
            temporary.unlink();raise RuntimeError('Archive did not save space; sources retained')
        temporary.rename(archive)
        record=dict(source=str(folder),archive=str(archive),archive_sha256=sha(archive),
            original_bytes=original_bytes,archive_bytes=archive_bytes,
            saved_bytes=original_bytes-archive_bytes,files=hashes,
            verified_exact=True,
            restore=f'python3 research/eta2_wave2/lossless_float_archive.py {archive} {folder}')
        # Verify once more from the final path before removing any source.
        FA.verify(archive,hashes)
        for item in files.values():item.unlink()
        marker.write_text(json.dumps(record,indent=2)+'\n')
        records.append(record)
        print('ARCHIVED',folder.name,'saved',record['saved_bytes'],flush=True)
    (P/'storage-curvature-captures.json').write_text(json.dumps(records,indent=2)+'\n')


if __name__=='__main__':main()
