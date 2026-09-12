"""Losslessly archive old completed gzip states, with exact container restoration.

Store decoded float bytes with the existing XOR/byte-plane encoder. Record gzip
header parameters and VERIFY byte-identical gzip regeneration before replacing
any original file. No numerical rounding. Original compressed SHA remains valid
after restore. Running research binaries and new scored evidence are untouched.
"""
from pathlib import Path
import argparse,gzip,hashlib,io,json,os,struct,sys,tempfile
P=Path(__file__).resolve().parent;sys.path.insert(0,str(P.parent/'eta2_wave2'))
import lossless_float_archive as FA
def digest(b):return hashlib.sha256(b).hexdigest()
def regenerate(raw,meta):
 out=io.BytesIO()
 with gzip.GzipFile(filename=meta['filename'],mode='wb',compresslevel=meta['level'],mtime=meta['mtime'],fileobj=out) as z:z.write(raw)
 return out.getvalue()
def restore(archive):
 blobs=dict(FA.decoded(archive));meta=json.loads(blobs.pop('restore.json'))
 for name,m in meta.items():
  raw=blobs[name];assert digest(raw)==m['raw_sha256'];compressed=regenerate(raw,m);assert digest(compressed)==m['compressed_sha256']
  p=Path(m['original'])
  if p.exists():assert digest(p.read_bytes())==m['compressed_sha256']
  else:p.write_bytes(compressed)
def pack(limit):
 root=Path('/tmp/prism-rl-actor/runs');dest=root.parent/'lossless-endpoint-archives';dest.mkdir(exist_ok=True)
 ledger=P/'old_endpoint_archives.json';records=json.loads(ledger.read_text()) if ledger.exists() else []
 files=sorted(root.glob('*final-13682*/endpoint.state.gz'))[:limit]
 for source in files:
  archive=dest/(source.parent.name+'.xor.tar.xz')
  if archive.exists():continue
  original=source.read_bytes();assert original[:3]==b'\x1f\x8b\x08'
  flags=original[3];assert flags in [0,8]
  mtime=struct.unpack('<I',original[4:8])[0];filename=original[10:original.index(b'\0',10)].decode() if flags==8 else ''
  raw=gzip.decompress(original);level={4:1,2:9,0:6}[original[8]]
  meta=dict(original=str(source),mtime=mtime,filename=filename,level=level,raw_sha256=digest(raw),compressed_sha256=digest(original),original_bytes=len(original))
  assert regenerate(raw,meta)==original,'Cannot exactly regenerate original gzip; no source changed'
  with tempfile.TemporaryDirectory(prefix='gzip-preserve-',dir='/dev/shm') as tmp:
   tmp=Path(tmp);a=tmp/'endpoint.state';a.write_bytes(raw);b=tmp/'restore.json';b.write_text(json.dumps({'endpoint.state':meta})+'\n')
   hashes=FA.pack(archive,{'endpoint.state':a,'restore.json':b});FA.verify(archive,hashes)
  decoded=dict(FA.decoded(archive));assert regenerate(decoded['endpoint.state'],json.loads(decoded['restore.json'])['endpoint.state'])==original
  rec=dict(archive=str(archive),archive_sha256=digest(archive.read_bytes()),**meta,archive_bytes=archive.stat().st_size,verified_exact_gzip=True)
  records.append(rec);ledger.write_text(json.dumps(records,indent=2)+'\n')
  # Both decoded state and exact gzip bytes verified from the durable archive.
  source.unlink()
  print('ARCHIVED',source.parent.name,'saved',rec['original_bytes']-rec['archive_bytes'],'free',os.statvfs('/tmp').f_bavail*os.statvfs('/tmp').f_frsize,flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=1);ap.add_argument('--restore');a=ap.parse_args()
 if a.restore:restore(a.restore)
 else:pack(a.limit)
