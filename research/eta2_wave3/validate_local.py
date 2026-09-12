"""Native primitive checks: inactive slot, f/tz gate, bit-preserving cap, mask."""
from pathlib import Path
import fcntl,json,os,subprocess
P=Path(__file__).resolve().parent
source=r'''
#include <cuda_runtime.h>
#include <cstdio>
#include <vector>
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <cassert>
#include <cstring>
#define CUDA_CHECK(x) do{auto local_cuda_error=(x);if(local_cuda_error!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(local_cuda_error));}while(0)
#include "local_actuators.cuh"
int main(){
 E3Local gate(3,true,0);std::vector<double> b(243,0),e(27,1);
 for(int c=0;c<3;++c)for(int i=0;i<8;++i)b[81*c+10*i]=1;
 // One active f/tz ambiguity; a pose-only null and inactive k2 must not gate.
 double q=.5*(1-1e-8);b[5*9+5]=b[6*9+6]=1-q;b[5*9+6]=b[6*9+5]=-q;
 b[81]=1e-10;
 double *devE,*v;CUDA_CHECK(cudaMalloc(&devE,216));CUDA_CHECK(cudaMalloc(&v,216));
 CUDA_CHECK(cudaMemcpy(devE,e.data(),216,cudaMemcpyHostToDevice));CUDA_CHECK(cudaMemcpy(gate.B,b.data(),1944,cudaMemcpyHostToDevice));
 gate.SetGate(devE,0,0);assert(gate.gates==std::vector<int>({1,0,0}));
 std::vector<double>x(27);for(int i=0;i<27;++i)x[i]=i+.25;auto expected=x;expected[6]=expected[7]=0;
 CUDA_CHECK(cudaMemcpy(v,x.data(),216,cudaMemcpyHostToDevice));gate.Project(v);CUDA_CHECK(cudaMemcpy(x.data(),v,216,cudaMemcpyDeviceToHost));assert(x==expected);
 E3Local cap(3,false,3);x.assign(27,0);x[0]=100;x[9]=1;x[18]=1;expected=x;expected[0]=3;
 CUDA_CHECK(cudaMemcpy(v,x.data(),216,cudaMemcpyHostToDevice));double n=cap.Cap(v,10,0,0);CUDA_CHECK(cudaMemcpy(x.data(),v,216,cudaMemcpyDeviceToHost));
 assert(std::abs(n-std::sqrt(11.))<1e-14);assert(x==expected);
 assert(std::memcmp(x.data()+9,expected.data()+9,18*8)==0);
 cudaFree(devE);cudaFree(v);puts("LOCAL_VALIDATION_PASS");
}'''
b=P/'build';src=b/'validate_local.cu';src.write_text(source)
cmd=['nvcc','-O2','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(P),str(src),'-o',str(b/'validate-local')]
env=os.environ.copy();env['TMPDIR']='/dev/shm'
with (b/'validation-build.log').open('w') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
with open('/tmp/prism_gpu.lock','w') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 out=subprocess.run(['compute-sanitizer','--tool','memcheck','--error-exitcode','99',str(b/'validate-local')],capture_output=True,text=True,check=True)
assert 'LOCAL_VALIDATION_PASS' in out.stdout and 'ERROR SUMMARY: 0 errors' in out.stderr+out.stdout
(P/'local_validation.json').write_text(json.dumps(dict(command=cmd,stdout=out.stdout,stderr=out.stderr,passed=True),indent=2)+'\n')
print('LOCAL VALIDATION PASS')
