#pragma once
// A terminal, read-only descent probe. The original state is never replaced.
template<int CD> __global__ void PrismRelaxCamera(const double*H,const double*g,int nc,double*out){
  int c=blockIdx.x*blockDim.x+threadIdx.x;if(c>=nc)return;
  double largest=0;for(int j=0;j<CD;++j)largest=fmax(largest,H[size_t(c)*CD*CD+j*CD+j]);
  double floor=fmax(1e-32,1e-12*largest);
  for(int j=0;j<CD;++j)out[c*CD+j]=-g[c*CD+j]/fmax(floor,H[size_t(c)*CD*CD+j*CD+j]);
}
__global__ void PrismRelaxPoint(const double*diag,const double*g,int np,double*out){
  int p=blockIdx.x*blockDim.x+threadIdx.x;if(p>=np)return;
  double floor=fmax(1e-32,1e-12*fmax(diag[3*p],fmax(diag[3*p+1],diag[3*p+2])));
  for(int j=0;j<3;++j)out[3*p+j]=-g[3*p+j]/fmax(floor,diag[3*p+j]);
}
