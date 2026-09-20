#!/usr/bin/env python3
"""Validate the actual generated CUDA helper against host double products."""
import pathlib,subprocess
root=pathlib.Path('/workspace/prism-tr-fp32-products/compensated');s=(root/'source.cu').read_text();start=s.index('__device__ __forceinline__ double MFCompensatedProduct');end=s.index('template <int CD, class HT>',start)
source=r'''
#include <cuda_runtime.h>
#include <cmath>
#include <cstdio>
#include <random>
#include <vector>
#include <algorithm>
'''+s[start:end]+r'''
__global__ void test(int n,const float*a,const double*b,double*c){int i=blockDim.x*blockIdx.x+threadIdx.x;if(i<n)c[i]=MFCompensatedProduct(a[i],b[i]);}
int main(){
 const int n=200000;std::mt19937_64 rng(90209);std::uniform_real_distribution<double> u(-1,1);std::uniform_int_distribution<int> e(-40,40);
 std::vector<float>a(n);std::vector<double>b(n),c(n);
 for(int i=0;i<n;++i){a[i]=(float)std::ldexp(u(rng),e(rng));b[i]=std::ldexp(u(rng),e(rng));}
 float*da;double*db,*dc;cudaMalloc(&da,n*sizeof(float));cudaMalloc(&db,n*8);cudaMalloc(&dc,n*8);cudaMemcpy(da,a.data(),n*4,cudaMemcpyHostToDevice);cudaMemcpy(db,b.data(),n*8,cudaMemcpyHostToDevice);
 test<<<(n+255)/256,256>>>(n,da,db,dc);if(cudaDeviceSynchronize()!=cudaSuccess)return 2;cudaMemcpy(c.data(),dc,n*8,cudaMemcpyDeviceToHost);
 double worst=0,naive=0;for(int i=0;i<n;++i){double exact=(double)a[i]*b[i];if(!std::isfinite(c[i]))return 3;worst=std::max(worst,std::abs(c[i]-exact)/std::max(1e-300,std::abs(exact)));naive=std::max(naive,std::abs((double)(a[i]*(float)b[i])-exact)/std::max(1e-300,std::abs(exact)));}
 std::printf("{\"samples\":%d,\"seed\":90209,\"exponent_min\":-40,\"exponent_max\":40,\"compensated_max_relative_error\":%.17g,\"naive_max_relative_error\":%.17g}\n",n,worst,naive);
 cudaFree(da);cudaFree(db);cudaFree(dc);return worst<=5e-14?0:1;
}
'''
p=root/'product-test.cu';p.write_text(source);subprocess.run(['/usr/local/cuda/bin/nvcc','-O3','-arch=sm_89',str(p),'-o',str(root/'product-test')],check=True)
with (root/'product-test.json').open('w') as f:subprocess.run(['flock','/tmp/prism_gpu.lock',str(root/'product-test')],stdout=f,check=True)
print((root/'product-test.json').read_text())
