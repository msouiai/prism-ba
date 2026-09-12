#!/usr/bin/env python3
"""Build, but do not launch, a native-kernel coarse correctness harness."""
import json
from pathlib import Path
import subprocess
from build import F,P,sha

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
    anchors=['__device__ __forceinline__ void MFVinv(',
             'template <int CD, class HT>\n__global__ void MFPass1(',
             '__global__ void MFVinvApply(',
             'template <int CD, class HT>\n__global__ void MFPass2(']
    path=b/'native_primitives.cuh';path.write_text('\n\n'.join(extract(source,a) for a in anchors)+'\n')
    headers=['coarse.cuh','geometry.h','attempt_trace.h'];before={h:sha(P/h) for h in headers}
    cmd=['nvcc','-O2','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(P),'-I'+str(b),str(P/'toy.cu'),'-o',str(b/'coarse-toy'),'-lcublas']
    with (b/'toy-build.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
    assert before=={h:sha(P/h) for h in headers}
    report=dict(command=cmd,source_sha256=sha(P/'toy.cu'),frozen_source_sha256=sha(F/'source/prism_eta2.cu'),
                extracted_native_kernels_sha256=sha(path),local_headers=before,binary_sha256=sha(b/'coarse-toy'))
    (P/'toy_build_manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
