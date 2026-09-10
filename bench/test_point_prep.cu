#include <cuda_runtime.h>
#include <cstdio>
#include <cmath>
#include <stdexcept>
using Scalar=double;
#include "reference.cuh"
#include "point_prep_candidate.cuh"
#define CK(x) do{if((x)!=cudaSuccess)throw std::runtime_error("CUDA");}while(0)
int main(){constexpr int np=7,no=np*3;float h[6*no]={};int off[np+1],list[no];for(int p=0;p<=np;++p)off[p]=3*p;for(int o=0;o<no;++o)list[o]=o;
 for(int p=0;p<np;++p){float s=p==0?1e-12f:p==2?1e12f:1.f;h[18*p]=p==5?0:s;h[18*p+4]=(p==3||p==5)?0:2*s;h[18*p+8]=(p==3||p==4||p==5)?0:p==6?1e-12f:3*s;}
 float*bo;int*po,*pl,*flags;double*r;CK(cudaMalloc(&bo,sizeof(h)));CK(cudaMalloc(&po,sizeof(off)));CK(cudaMalloc(&pl,sizeof(list)));CK(cudaMalloc(&flags,np*4));CK(cudaMalloc(&r,np*6*8));CK(cudaMemcpy(bo,h,sizeof(h),cudaMemcpyHostToDevice));CK(cudaMemcpy(po,off,sizeof(off),cudaMemcpyHostToDevice));CK(cudaMemcpy(pl,list,sizeof(list),cudaMemcpyHostToDevice));MFPointFactorGuarded<<<1,256>>>(bo,po,pl,np,r,flags);int hf[np];double hr[np*6];CK(cudaMemcpy(hf,flags,sizeof(hf),cudaMemcpyDeviceToHost));CK(cudaMemcpy(hr,r,sizeof(hr),cudaMemcpyDeviceToHost));
 for(int p=0;p<np;++p){if(hf[p]!=(p>=3))throw std::runtime_error("fallback classification");double want[6]={h[18*p],0,0,h[18*p+4],0,h[18*p+8]};for(int j=0;j<6;++j)if(!std::isfinite(hr[6*p+j])||fabs(hr[6*p+j]-want[j])>1e-14*fmax(1.,fabs(want[j])))throw std::runtime_error("factor");}
 puts("PASS: scaled well-conditioned blocks, rank-one, rank-two, zero and ill-conditioned blocks; expected QR fallback and factors verified.");}
