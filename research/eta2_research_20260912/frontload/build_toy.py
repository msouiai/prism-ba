#!/usr/bin/env python3
from pathlib import Path
import json,os,subprocess
from build import P,F,sha

def extract(source,anchor):
    assert source.count(anchor)==1,anchor
    start=source.index(anchor);brace=source.index('{',start);depth=0
    for end in range(brace,len(source)):
        if source[end]=='{':depth+=1
        if source[end]=='}':
            depth-=1
            if depth==0:return source[start:end+1]
    raise ValueError(anchor)

def main():
    subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
    source=(F/'source/prism_eta2.cu').read_text();b=P/'build';b.mkdir(exist_ok=True)
    anchors=['__device__ __forceinline__ void MFGivens(', 'template <class HT>\n__global__ void MFPointFactorObs(',
             '__global__ void MFPointFactorTau(', '__device__ __forceinline__ void MFVinv(',
             '__global__ void MFVinvApply(', '__global__ void MFBackSub(']
    path=b/'native_primitives.cuh';path.write_text('\n\n'.join(extract(source,a) for a in anchors)+'\n')
    names=['frontload.cuh','coherent_rows.cuh'];headers={n:sha(P/n) for n in names}
    cmd=['nvcc','-O2','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(P),'-I'+str(b),'-I'+str(F/'source/headers'),str(P/'toy.cu'),'-o',str(b/'frontload-toy'),'-lcublas']
    env=os.environ.copy();env['TMPDIR']='/dev/shm'
    with (b/'toy-build.log').open('w') as log:subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    assert headers=={n:sha(P/n) for n in names}
    report=dict(command=cmd,tmpdir='/dev/shm',source_sha256=sha(P/'toy.cu'),frozen_source_sha256=sha(F/'source/prism_eta2.cu'),
                extracted_native_kernels_sha256=sha(path),local_headers=headers,binary_sha256=sha(b/'frontload-toy'))
    (P/'toy_build_manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
