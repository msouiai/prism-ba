#pragma once
__global__ void W5CgXR(double* __restrict__ x,double* __restrict__ r,
                       const double* __restrict__ p,const double* __restrict__ Ap,
                       double alpha,int n){
  int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n){x[i]+=alpha*p[i];r[i]-=alpha*Ap[i];}
}
__global__ void W5CgP(double* __restrict__ p,const double* __restrict__ z,
                      double beta,int n){
  int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)p[i]=z[i]+beta*p[i];
}
