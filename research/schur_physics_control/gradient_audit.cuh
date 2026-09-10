#pragma once
#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <cmath>
#include <cstdio>
#include <stdexcept>
template<int CD> __global__ void PrismGradientCamera(const double*H,const double*g,int nc,double*out){
  int c=blockIdx.x*blockDim.x+threadIdx.x;if(c>=nc)return;
  double largest=0;for(int j=0;j<CD;++j)largest=fmax(largest,H[size_t(c)*CD*CD+j*CD+j]);
  double floor=fmax(1e-32,1e-12*largest);
  for(int j=0;j<CD;++j)out[c*CD+j]=g[c*CD+j]/sqrt(fmax(floor,H[size_t(c)*CD*CD+j*CD+j]));
}
__global__ void PrismGradientPoint(const double*diag,const double*g,int np,double*out){
  int p=blockIdx.x*blockDim.x+threadIdx.x;if(p>=np)return;
  double largest=fmax(diag[3*p],fmax(diag[3*p+1],diag[3*p+2]));
  double floor=fmax(1e-32,1e-12*largest);
  for(int j=0;j<3;++j)out[3*p+j]=g[3*p+j]/sqrt(fmax(floor,diag[3*p+j]));
}
template<int CD> void PrismLogGradient(cublasHandle_t h,const double*H,const double*diag,
    const double*bc,const double*bp,int nc,int np,double*wc,double*wp,
    const char*phase,int outer,double cost,double lambda,double tau){
  PrismGradientCamera<CD><<<(nc+255)/256,256>>>(H,bc,nc,wc);
  PrismGradientPoint<<<(np+255)/256,256>>>(diag,bp,np,wp);
  double gc,gp,rawc,rawp;
  auto ck=[](cublasStatus_t s){if(s!=CUBLAS_STATUS_SUCCESS)throw std::runtime_error("gradient audit cuBLAS");};
  ck(cublasDnrm2(h,CD*nc,wc,1,&gc));ck(cublasDnrm2(h,3*np,wp,1,&gp));
  ck(cublasDnrm2(h,CD*nc,bc,1,&rawc));ck(cublasDnrm2(h,3*np,bp,1,&rawp));
  printf("GRAD_AUDIT phase=%s outer=%d cost=%.17g lambda=%.17g tau=%.17g scaled_camera=%.17g scaled_point=%.17g raw_camera=%.17g raw_point=%.17g normalized_gradient_energy=%.17g\n",
    phase,outer,cost,lambda,tau,gc,gp,rawc,rawp,(gc*gc+gp*gp)/fmax(2*cost,1e-300));
}
