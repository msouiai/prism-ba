#!/usr/bin/env python3
"""Build the frozen-system GSP screen from checksum-pinned Eta2 source."""
from __future__ import annotations
import hashlib, json, os, pathlib, subprocess

HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PKG=ROOT/'research/eta2_champion'
OUT=pathlib.Path('/tmp/prism-wave6-d11-build')
OUT.mkdir(parents=True,exist_ok=True)
source=(PKG/'source/prism_eta2.cu').read_text()
assert hashlib.sha256(source.encode()).hexdigest()=='22c18359a526526ae0a5b5109187878ab1cef33b453f6bbddc2aa92597a607d8'
manifest=json.loads((PKG/'source_manifest.json').read_text())
assert all(hashlib.sha256((PKG/'source/headers'/name).read_bytes()).hexdigest()==digest
           for name,digest in manifest['headers_sha256'].items())
parts=[]
for start,end in [
    ('__device__ __forceinline__ void MFVinv(', '// GAP-4090 F2'),
    ('__global__ void MFVinvApply(', '// Map camera traversal'),
    ('template <int CD, class HT>\n__global__ void MFPass2(', '__global__ void MFBackSub')]:
    a=source.index(start);b=source.index(end,a);parts.append(source[a:b])
(OUT/'reference.cuh').write_text('\n'.join(parts))
binary=OUT/'gsp_fixed'
CUDSS=pathlib.Path(os.environ.get('D11_CUDSS_ROOT','/tmp/cudss-d11'))
have_cudss=(CUDSS/'include/cudss.h').exists() and (CUDSS/'lib/libcudss.so.0').exists()
command=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',f'-I{OUT}']
if have_cudss:
    command += ['-DD11_HAVE_CUDSS=1',f'-I{CUDSS}/include']
command += [str(HERE/'gsp_fixed.cu'),'-o',str(binary),'-lcublas','-lcusolver','-lcusparse','-lcholmod']
if have_cudss:
    command += [f'-L{CUDSS}/lib','-l:libcudss.so.0','-Xlinker=-rpath',f'-Xlinker={CUDSS}/lib']
with (OUT/'build.log').open('w') as log:
    subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
record={'command':command,'source_sha256':hashlib.sha256((HERE/'gsp_fixed.cu').read_bytes()).hexdigest(),
        'reference_sha256':hashlib.sha256((OUT/'reference.cuh').read_bytes()).hexdigest(),
        'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
        'cudss_enabled':have_cudss}
if have_cudss:
    record.update(cudss_version='0.8.0.10',cudss_sha256=hashlib.sha256((CUDSS/'lib/libcudss.so.0').read_bytes()).hexdigest())
(HERE/'evidence/build_manifest.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
