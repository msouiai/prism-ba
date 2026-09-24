#pragma once
#include <math_constants.h>
// At a fixed camera state, the objective separates by whole point tracks.
// One warp per point: no per-observation or per-point temporary allocation.
__device__ double PrismTrackObservation(int o,int point,const int* ci,const double* uv,
    const double* R,const double* t,const double* X,const double* f,
    const double* k1,const double* k2,const double* delta=nullptr,double scale=0){
  int c=ci[o];const double* r=R+9*c;const double* x=X+3*point;double adjusted[3];
  if(scale!=0){for(int j=0;j<3;++j)adjusted[j]=x[j]+scale*delta[3*point+j];x=adjusted;}
  double qx=r[0]*x[0]+r[1]*x[1]+r[2]*x[2]+t[3*c];
  double qy=r[3]*x[0]+r[4]*x[1]+r[5]*x[2]+t[3*c+1];
  double qz=r[6]*x[0]+r[7]*x[1]+r[8]*x[2]+t[3*c+2];
  double u=-qx/qz,v=-qy/qz,s=u*u+v*v;
  double factor=f[c]*(1+k1[c]*s+k2[c]*s*s);
  double a=factor*u-uv[2*o],b=factor*v-uv[2*o+1];
  double cost=.5*(a*a+b*b);return isfinite(cost)?cost:CUDART_INF;
}
__global__ void MFPointSafeguard(const int* offsets,const int* order,const int* ci,
    const double* uv,const double* R,const double* t,const double* oldX,
    const double* fullX,const double* f,const double* k1,const double* k2,
    int np,int nc,double* step,unsigned long long* frozen,double keep_scale){
  int lane=threadIdx.x%32,point=(blockIdx.x*blockDim.x+threadIdx.x)/32;
  if(point>=np)return;double keep=0,move=0;
  for(int j=offsets[point]+lane;j<offsets[point+1];j+=32){int o=order[j];
    keep+=PrismTrackObservation(o,point,ci,uv,R,t,oldX,f,k1,k2,step+9*nc,keep_scale);
    move+=PrismTrackObservation(o,point,ci,uv,R,t,fullX,f,k1,k2);
  }
  for(int k=16;k;k>>=1){keep+=__shfl_down_sync(0xffffffff,keep,k);move+=__shfl_down_sync(0xffffffff,move,k);}
  // Strict comparison keeps the original direction for ties/unseen points.
  // If both tracks are nonfinite retain full: the global full-cost audit rejects it.
  if(lane==0 && keep<move){for(int j=0;j<3;++j)step[9*nc+3*point+j]=keep_scale==0?0:keep_scale*step[9*nc+3*point+j];atomicAdd(frozen,1ULL);}
}
struct PrismPointSafeguard {
  unsigned long long* frozen=nullptr;
  PrismPointSafeguard(){CUDA_CHECK(cudaMalloc(&frozen,sizeof(*frozen)));}
  ~PrismPointSafeguard(){cudaFree(frozen);}
  PrismPointSafeguard(const PrismPointSafeguard&)=delete;
  unsigned long long Choose(const DeviceProblem& p,const DeviceState& old,
      const DeviceState& full,double* step,double keep_scale=0){
    CUDA_CHECK(cudaMemset(frozen,0,sizeof(*frozen)));
    MFPointSafeguard<<<(p.npt+7)/8,256>>>(p.point_obs_offsets,p.point_obs_list,p.cam_idx,
      p.uv,full.R,full.t,old.X,full.X,INTR_F(p,full),INTR_K1(p,full),INTR_K2(p,full),p.npt,p.ncam,step,frozen,keep_scale);
    unsigned long long count=0;CUDA_CHECK(cudaMemcpy(&count,frozen,sizeof(count),cudaMemcpyDeviceToHost));return count;
  }
};
