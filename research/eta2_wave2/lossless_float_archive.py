"""Lossless XOR/byte-plane tar.xz for repeated FP64 exports; raw SHA is authoritative.

Each member's first byte is R (raw) or X (XOR against previous same basename/size,
then transpose the eight byte planes). Entries are ordered by basename and path.
No floating-point arithmetic or quantisation. Decoding returns original bytes.
"""
from pathlib import Path
import hashlib,io,lzma,tarfile
import numpy as np
def _key(name,length):return (Path(name).name,length)
def pack(destination,files):
    previous={};hashes={}
    with lzma.open(destination,'wb',preset=3) as z:
        with tarfile.open(fileobj=z,mode='w|') as tf:
            for name,path in sorted(files.items(),key=lambda x:(Path(x[0]).name,x[0])):
                raw=Path(path).read_bytes();hashes[name]=hashlib.sha256(raw).hexdigest()
                if name.endswith(('.f64','.state')) and len(raw)%8==0:
                    a=np.frombuffer(raw,dtype=np.uint8);key=_key(name,len(raw));old=previous.get(key)
                    delta=a if old is None else np.bitwise_xor(a,old)
                    encoded=b'X'+delta.reshape(-1,8).T.tobytes();previous[key]=a.copy()
                else:encoded=b'R'+raw
                member=tarfile.TarInfo(name);member.size=len(encoded);tf.addfile(member,io.BytesIO(encoded))
    return hashes
def decoded(path):
    previous={}
    with tarfile.open(path,'r|xz') as tf:
        for member in tf:
            with tf.extractfile(member) as f:payload=f.read()
            if payload[:1]==b'X':
                delta=np.frombuffer(payload[1:],dtype=np.uint8).reshape(8,-1).T.copy().ravel();key=_key(member.name,len(delta))
                if key in previous:delta^=previous[key]
                previous[key]=delta.copy();raw=delta.tobytes()
            else:
                assert payload[:1]==b'R';raw=payload[1:]
            yield member.name,raw
def verify(path,hashes):
    seen=set()
    for name,raw in decoded(path):
        assert name not in seen;seen.add(name);assert hashlib.sha256(raw).hexdigest()==hashes[name]
    assert seen==set(hashes)
def restore(path,directory):
    root=Path(directory).resolve()
    for name,raw in decoded(path):
        p=(root/name).resolve();assert p.is_relative_to(root)
        if p.exists():assert p.read_bytes()==raw
        else:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('archive');a.add_argument('destination');args=a.parse_args();restore(args.archive,args.destination)
