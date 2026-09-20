#pragma once
// Group G adjacent lanes owns one point. W remains camera-major; CSR supplies
// observation slots. Products and sums remain FP64; summation order changes.
template<int CD,int G>
__global__ void MFPass1PointOwned(const float* __restrict__ W,const int* __restrict__ cam,
 const int* __restrict__ poff,const int* __restrict__ slots,const double* __restrict__ v,
 int nobs,int npt,double* __restrict__ t){
 const int tid=blockIdx.x*blockDim.x+threadIdx.x,p=tid/G,lane=tid%G;
 double a=0,b=0,c=0;
 if(p<npt)for(int j=poff[p]+lane;j<poff[p+1];j+=G){
  const int k=slots[j];const double* vc=v+CD*cam[k];double qa=0,qb=0,qc=0;
  for(int i=0;i<CD;++i){double x=vc[i];qa+=(double)W[(size_t)(3*i)*nobs+k]*x;qb+=(double)W[(size_t)(3*i+1)*nobs+k]*x;qc+=(double)W[(size_t)(3*i+2)*nobs+k]*x;}
  a+=qa;b+=qb;c+=qc;
 }
 for(int d=G/2;d;d/=2){a+=__shfl_down_sync(0xffffffff,a,d,G);b+=__shfl_down_sync(0xffffffff,b,d,G);c+=__shfl_down_sync(0xffffffff,c,d,G);}
 if(lane==0&&p<npt){t[3*p]=a;t[3*p+1]=b;t[3*p+2]=c;}
}
// Preserve coalesced W reads; scatter/reduce only three doubles per observation.
template<int CD>
__global__ void MFPass1Local(const float* __restrict__ W,const int* __restrict__ cam,
 const double* __restrict__ v,int nobs,double* __restrict__ products){
 int k=blockIdx.x*blockDim.x+threadIdx.x;if(k>=nobs)return;const double*vc=v+CD*cam[k];
 for(int j=0;j<3;++j){double q=0;for(int i=0;i<CD;++i)q+=(double)W[(size_t)(3*i+j)*nobs+k]*vc[i];products[(size_t)j*nobs+k]=q;}
}
template<int G>
__global__ void MFPass1Reduce(const double* __restrict__ products,const int* __restrict__ poff,
 const int* __restrict__ slots,int nobs,int npt,double* __restrict__ t){
 int tid=blockIdx.x*blockDim.x+threadIdx.x,p=tid/G,lane=tid%G;double a=0,b=0,c=0;
 if(p<npt)for(int j=poff[p]+lane;j<poff[p+1];j+=G){int k=slots[j];a+=products[k];b+=products[(size_t)nobs+k];c+=products[2ul*nobs+k];}
 for(int d=G/2;d;d/=2){a+=__shfl_down_sync(0xffffffff,a,d,G);b+=__shfl_down_sync(0xffffffff,b,d,G);c+=__shfl_down_sync(0xffffffff,c,d,G);}
 if(lane==0&&p<npt){t[3*p]=a;t[3*p+1]=b;t[3*p+2]=c;}
}
