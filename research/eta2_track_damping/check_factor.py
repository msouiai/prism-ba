#!/usr/bin/env python3
"""Actual GPU augmentation versus dense FP64 energy, with boundary track lengths."""
import ctypes,hashlib,json,os,subprocess
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent
def main():
    b=P/'build';b.mkdir(exist_ok=True)
    frozen=(P.parent/'eta2_champion/source/prism_eta2.cu').read_text()
    a=frozen.index('__device__ __forceinline__ void MFGivens(')
    givens=frozen[a:frozen.index('// s2.4 augmented QR:',a)]
    a=frozen.index('__global__ void MFPointFactorTau(')
    uniform=frozen[a:frozen.index('__device__ __forceinline__ void MFVinv',a)]
    source='''#include <cuda_runtime.h>
#include <cmath>
using Scalar=double;
'''+givens+uniform+'\n#include "track_factor.cuh"\n'+'''
extern "C" int factor(const double* cd,const double* r,const int* off,int n,double tau,int on,double* out){
 double *d,*q,*f;int *o,*ok;
 #define CK(x) do{int e=(int)(x);if(e)return e;}while(0)
 CK(cudaMalloc(&d,24ul*n));CK(cudaMalloc(&q,48ul*n));CK(cudaMalloc(&f,48ul*n));
 CK(cudaMalloc(&o,4ul*(n+1)));CK(cudaMalloc(&ok,4ul*n));
 CK(cudaMemcpy(d,cd,24ul*n,cudaMemcpyHostToDevice));CK(cudaMemcpy(q,r,48ul*n,cudaMemcpyHostToDevice));
 CK(cudaMemcpy(o,off,4ul*(n+1),cudaMemcpyHostToDevice));
 if(on)MFPointFactorTauTrack<<<(n+255)/256,256>>>(d,q,o,tau,n,f,ok);
 else MFPointFactorTau<<<(n+255)/256,256>>>(d,q,tau,n,f,ok);
 CK(cudaGetLastError());CK(cudaMemcpy(out,f,48ul*n,cudaMemcpyDeviceToHost));
 CK(cudaFree(d));CK(cudaFree(q));CK(cudaFree(f));CK(cudaFree(o));CK(cudaFree(ok));return 0;
}
'''
    cu=b/'factor_test.cu';cu.write_text(source)
    cmd=['nvcc','-O3','-std=c++17','-arch=sm_89','--shared','-Xcompiler','-fPIC','-I'+str(P),str(cu),'-o',str(b/'factor_test.so')]
    env=os.environ.copy();env['TMPDIR']='/dev/shm';subprocess.run(cmd,env=env,check=True)
    dll=ctypes.CDLL(str(b/'factor_test.so'));fn=dll.factor
    ptr=ctypes.c_void_p;fn.argtypes=[ptr,ptr,ptr,ctypes.c_int,ctypes.c_double,ctypes.c_int,ptr];fn.restype=ctypes.c_int
    rng=np.random.default_rng(20260912);n=257
    lengths=np.resize(np.array([1,2,3,4,5,6,7,12,50],dtype=np.int32),n)
    off=np.r_[0,np.cumsum(lengths)].astype(np.int32)
    q=np.triu(rng.normal(size=(n,3,3)));q[:,range(3),range(3)]=10**rng.uniform(-8,3,(n,3))
    cd=np.sum(q*q,axis=1);packed=np.ascontiguousarray(q[:,[0,0,0,1,1,2],[0,1,2,1,2,2]])
    errors=[];short_bitwise=True;different_long=0
    for tau in [1e-14,1e-9,1e-4,.1,1.,1e3]:
        outputs=[]
        for on in [0,1]:
            out=np.empty_like(packed)
            assert fn(cd.ctypes.data,packed.ctypes.data,off.ctypes.data,n,tau,on,out.ctypes.data)==0
            R=np.zeros_like(q);R[:,[0,0,0,1,1,2],[0,1,2,1,2,2]]=out
            fac=tau*np.where((lengths>=6)&bool(on),.3,1.)
            fl=np.maximum(fac*cd.sum(axis=1)/3,1e-32)
            damp=np.maximum(fac[:,None]*cd,1e-3*fl[:,None])
            expected=q.transpose(0,2,1)@q
            expected[:,range(3),range(3)]+=damp
            relative=np.linalg.norm(R.transpose(0,2,1)@R-expected,axis=(1,2))/np.maximum(np.linalg.norm(expected,axis=(1,2)),1e-300)
            errors.append(float(relative.max()));assert relative.max()<5e-13
            outputs.append(out)
        short_bitwise &= np.array_equal(outputs[0][lengths<6],outputs[1][lengths<6])
        different_long+=int(np.any(outputs[0][lengths>=6]!=outputs[1][lengths>=6]))
    assert short_bitwise and different_long>0
    result=dict(passed=True,blocks_per_call=n,calls=12,relative_energy_errors=errors,
                short_track_factors_bitwise_identical=short_bitwise,long_tracks_changed=True,
                counts=list(map(int,lengths)),tau_values=[1e-14,1e-9,1e-4,.1,1.,1e3],
                source_sha256=hashlib.sha256(source.encode()).hexdigest(),command=cmd)
    (P/'factor_verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print('FACTOR PASS',max(errors),flush=True)
if __name__=='__main__':main()
